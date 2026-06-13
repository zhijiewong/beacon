// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title BeaconStaking — Oracle Integrity Staking (Pyth-style) for the Beacon rate
/// @notice Publishers self-stake BEACON to back the accuracy of the feeds they post;
///         delegators stake to a publisher's pool to share in (future) rewards and
///         in slashing risk. Slashing cuts a pool pro-rata when its feed is bad.
/// @dev    Each pool uses a shares/assets model (like an ERC-4626 vault) so a slash
///         is O(1): it lowers the pool's total assets, which proportionally lowers
///         every staker's claim without iterating over them. `stakeOf` returns the
///         asset value of a position; `poolStake` is the pool's total assets.
///         TESTNET ONLY — unaudited; needs a professional audit before any real value.
///         Staking pulls BEACON via transferFrom (stakers pre-approve this contract).
contract BeaconStaking is ReentrancyGuard, Ownable {
    using SafeERC20 for IERC20;

    IERC20 public immutable beacon;

    /// Minimum self-stake (in assets) for a publisher to be eligible to post feeds.
    uint256 public constant MIN_PUBLISHER_STAKE = 1000e18;
    /// Cooldown between requesting an unstake and being able to withdraw.
    uint256 public constant UNBOND_PERIOD = 7 days;
    /// Maximum fraction of a pool that a single slash can remove (5%, in basis points).
    uint256 public constant MAX_SLASH_BPS = 500;

    /// Where slashed tokens are sent (governance / insurance fund). Defaults to owner.
    address public slashTreasury;

    /// publisher => total assets backing that publisher (self + delegated, net of slashing).
    mapping(address => uint256) public poolStake;
    /// publisher => total shares issued by that pool.
    mapping(address => uint256) public totalShares;
    /// publisher => staker => shares held by the staker in that pool.
    mapping(address => mapping(address => uint256)) public sharesOf;

    struct Unbond {
        uint256 amount; // assets released from the pool, awaiting withdrawal
        uint256 readyAt; // timestamp the tokens become withdrawable
    }
    /// publisher => staker => pending unbond for that (publisher, staker) position.
    mapping(address => mapping(address => Unbond)) public unbonding;

    event SelfStaked(address indexed publisher, uint256 amount);
    event Delegated(address indexed publisher, address indexed delegator, uint256 amount);
    event UnstakeRequested(address indexed publisher, address indexed staker, uint256 amount, uint256 readyAt);
    event Withdrawn(address indexed publisher, address indexed staker, uint256 amount);
    event Slashed(address indexed publisher, uint256 amount, uint256 bps);
    event SlashTreasurySet(address indexed treasury);

    constructor(IERC20 beacon_) Ownable(msg.sender) {
        require(address(beacon_) != address(0), "zero token");
        beacon = beacon_;
        slashTreasury = msg.sender;
    }

    // --- views -------------------------------------------------------------

    /// @notice Asset value of a staker's position in a publisher's pool.
    function stakeOf(address publisher, address staker) public view returns (uint256) {
        uint256 shares = totalShares[publisher];
        if (shares == 0) return 0;
        return (sharesOf[publisher][staker] * poolStake[publisher]) / shares;
    }

    /// @notice Whether a publisher meets the minimum self-stake to post feeds.
    function isEligiblePublisher(address publisher) external view returns (bool) {
        return stakeOf(publisher, publisher) >= MIN_PUBLISHER_STAKE;
    }

    // --- staking -----------------------------------------------------------

    /// @notice Publisher self-stakes BEACON into its own pool.
    function selfStake(uint256 amount) external nonReentrant {
        _stake(msg.sender, msg.sender, amount);
        emit SelfStaked(msg.sender, amount);
    }

    /// @notice Delegator stakes BEACON to back an existing publisher's pool.
    /// @dev A publisher is anyone with a non-zero self-stake; eligibility to *post*
    ///      additionally requires MIN_PUBLISHER_STAKE (see isEligiblePublisher).
    function delegate(address publisher, uint256 amount) external nonReentrant {
        require(stakeOf(publisher, publisher) > 0, "not a publisher");
        _stake(publisher, msg.sender, amount);
        emit Delegated(publisher, msg.sender, amount);
    }

    /// @dev Mints pool shares to `staker` for `amount` assets at the current rate.
    function _stake(address publisher, address staker, uint256 amount) internal {
        require(amount > 0, "zero amount");
        beacon.safeTransferFrom(msg.sender, address(this), amount);
        uint256 supply = totalShares[publisher];
        uint256 assets = poolStake[publisher];
        // First deposit (or a fully-slashed pool) mints 1:1; otherwise pro-rata.
        uint256 newShares = (supply == 0 || assets == 0) ? amount : (amount * supply) / assets;
        sharesOf[publisher][staker] += newShares;
        totalShares[publisher] = supply + newShares;
        poolStake[publisher] = assets + amount;
    }

    // --- unbonding ---------------------------------------------------------

    /// @notice Begin unstaking: burns shares for `amount` assets immediately and
    ///         starts the cooldown. A second request resets the cooldown on the
    ///         whole pending amount.
    function requestUnstake(address publisher, uint256 amount) external {
        require(amount > 0, "zero amount");
        require(stakeOf(publisher, msg.sender) >= amount, "insufficient stake");
        // Burn the shares corresponding to `amount` assets at the current rate.
        uint256 burnShares = (amount * totalShares[publisher]) / poolStake[publisher];
        sharesOf[publisher][msg.sender] -= burnShares;
        totalShares[publisher] -= burnShares;
        poolStake[publisher] -= amount;

        Unbond storage u = unbonding[publisher][msg.sender];
        u.amount += amount;
        u.readyAt = block.timestamp + UNBOND_PERIOD;
        emit UnstakeRequested(publisher, msg.sender, amount, u.readyAt);
    }

    /// @notice After the cooldown, return the unbonded tokens to the staker.
    function withdraw(address publisher) external nonReentrant {
        Unbond storage u = unbonding[publisher][msg.sender];
        uint256 amount = u.amount;
        require(amount > 0, "nothing to withdraw");
        require(block.timestamp >= u.readyAt, "cooling down");
        delete unbonding[publisher][msg.sender];
        beacon.safeTransfer(msg.sender, amount);
        emit Withdrawn(publisher, msg.sender, amount);
    }

    // --- slashing ----------------------------------------------------------

    /// @notice Slash a publisher's pool by `bps` basis points (capped at MAX_SLASH_BPS).
    ///         Lowers the pool's assets, cutting every staker pro-rata, and sends the
    ///         slashed tokens to the slash treasury. Governance-gated (owner) for now;
    ///         a deviation-triggered automatic path lands with the v2 median oracle.
    function slash(address publisher, uint256 bps) external onlyOwner {
        require(bps > 0, "zero bps");
        require(bps <= MAX_SLASH_BPS, "slash too large");
        uint256 assets = poolStake[publisher];
        require(assets > 0, "empty pool");
        uint256 cut = (assets * bps) / 10_000;
        poolStake[publisher] = assets - cut; // shares unchanged -> pro-rata haircut
        beacon.safeTransfer(slashTreasury, cut);
        emit Slashed(publisher, cut, bps);
    }

    /// @notice Set the destination for slashed tokens (owner only).
    function setSlashTreasury(address treasury) external onlyOwner {
        require(treasury != address(0), "zero treasury");
        slashTreasury = treasury;
        emit SlashTreasurySet(treasury);
    }
}
