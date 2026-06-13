// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";

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
contract BeaconStaking is ReentrancyGuard, Ownable2Step {
    using SafeERC20 for IERC20;

    IERC20 public immutable beacon;

    /// Minimum self-stake (in assets) for a publisher to be eligible to post feeds.
    uint256 public constant MIN_PUBLISHER_STAKE = 1000e18;
    /// Cooldown between requesting an unstake and being able to withdraw.
    uint256 public constant UNBOND_PERIOD = 7 days;
    /// Maximum fraction of a pool that a single slash can remove (5%, in basis points).
    uint256 public constant MAX_SLASH_BPS = 500;
    /// Maximum publisher commission on rewards (20%, in basis points).
    uint256 public constant MAX_FEE_BPS = 2000;
    /// Window over which the per-pool reward cap is measured.
    uint256 public constant REWARD_EPOCH = 7 days;
    /// Fixed-point precision for the reward-per-share accumulator.
    uint256 private constant ACC_PRECISION = 1e30;
    /// Unity for the unbonding haircut factor (1.0 in 1e18 fixed-point).
    uint256 private constant ONE = 1e18;

    /// Where slashed tokens are sent (governance / insurance fund). Defaults to owner.
    address public slashTreasury;
    /// Automated slasher (e.g. the median oracle's deviation trigger); 0 = none.
    /// Can call slash() in addition to the owner.
    address public slasher;

    /// Stablecoin rewards are paid in this token (e.g. USDC). Set by governance.
    IERC20 public rewardToken;
    /// Max reward (in reward-token units) distributable to one pool per epoch. 0 = no cap.
    uint256 public maxRewardPerEpoch;

    /// publisher => commission (bps) the publisher keeps off the top of its pool's rewards.
    mapping(address => uint256) public publisherFeeBps;
    /// publisher => accumulated reward-token per share, scaled by ACC_PRECISION.
    mapping(address => uint256) public accRewardPerShare;
    /// publisher => staker => reward-per-share already accounted for (MasterChef debt).
    mapping(address => mapping(address => uint256)) public rewardDebt;
    /// publisher => staker => settled-but-unclaimed rewards.
    mapping(address => mapping(address => uint256)) public claimable;
    /// publisher => start of the current reward epoch.
    mapping(address => uint256) public rewardEpochStart;
    /// publisher => rewards distributed to this pool in the current epoch.
    mapping(address => uint256) public rewardedThisEpoch;

    /// publisher => total assets backing that publisher (self + delegated, net of slashing).
    mapping(address => uint256) public poolStake;
    /// publisher => total shares issued by that pool.
    mapping(address => uint256) public totalShares;
    /// publisher => staker => shares held by the staker in that pool.
    mapping(address => mapping(address => uint256)) public sharesOf;

    struct Unbond {
        uint256 amount; // assets released from the pool, awaiting withdrawal
        uint256 readyAt; // timestamp the tokens become withdrawable
        uint256 scaleAtRequest; // unbondScale snapshot when requested (for slash haircuts)
    }
    /// publisher => staker => pending unbond for that (publisher, staker) position.
    mapping(address => mapping(address => Unbond)) public unbonding;
    /// publisher => total assets currently unbonding (still slashable during cooldown).
    mapping(address => uint256) public totalUnbonding;
    /// publisher => cumulative unbonding haircut factor (ONE = untouched). A slash multiplies
    /// it down so every pending unbond in that pool is cut pro-rata. 0 is treated as ONE.
    mapping(address => uint256) public unbondScale;

    event SelfStaked(address indexed publisher, uint256 amount);
    event Delegated(address indexed publisher, address indexed delegator, uint256 amount);
    event UnstakeRequested(address indexed publisher, address indexed staker, uint256 amount, uint256 readyAt);
    event Withdrawn(address indexed publisher, address indexed staker, uint256 amount);
    event Slashed(address indexed publisher, uint256 amount, uint256 bps);
    event SlashTreasurySet(address indexed treasury);
    event SlasherSet(address indexed slasher);
    event RewardTokenSet(address indexed token);
    event MaxRewardPerEpochSet(uint256 amount);
    event PublisherFeeSet(address indexed publisher, uint256 bps);
    event RewardsDistributed(address indexed publisher, uint256 amount, uint256 fee);
    event RewardsClaimed(address indexed publisher, address indexed staker, uint256 amount);

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

    /// @notice Reward-token amount a staker can currently claim from a pool.
    function pendingRewards(address publisher, address staker) public view returns (uint256) {
        uint256 accrued = (sharesOf[publisher][staker] * accRewardPerShare[publisher]) / ACC_PRECISION;
        return claimable[publisher][staker] + accrued - rewardDebt[publisher][staker];
    }

    /// @dev Move a staker's freshly-accrued rewards into `claimable` and reset their debt.
    ///      Must be called before any change to the staker's share balance.
    function _settle(address publisher, address staker) internal {
        uint256 accrued = (sharesOf[publisher][staker] * accRewardPerShare[publisher]) / ACC_PRECISION;
        claimable[publisher][staker] += accrued - rewardDebt[publisher][staker];
        rewardDebt[publisher][staker] = accrued;
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
        _settle(publisher, staker); // bank rewards earned on the existing balance first
        beacon.safeTransferFrom(msg.sender, address(this), amount);
        uint256 supply = totalShares[publisher];
        uint256 assets = poolStake[publisher];
        // First deposit (or a fully-slashed pool) mints 1:1; otherwise pro-rata.
        uint256 newShares = (supply == 0 || assets == 0) ? amount : (amount * supply) / assets;
        sharesOf[publisher][staker] += newShares;
        totalShares[publisher] = supply + newShares;
        poolStake[publisher] = assets + amount;
        rewardDebt[publisher][staker] = (sharesOf[publisher][staker] * accRewardPerShare[publisher]) / ACC_PRECISION;
    }

    // --- unbonding ---------------------------------------------------------

    /// @notice Begin unstaking: burns shares for `amount` assets immediately and
    ///         starts the cooldown. A second request resets the cooldown on the
    ///         whole pending amount.
    function requestUnstake(address publisher, uint256 amount) external {
        require(amount > 0, "zero amount");
        require(stakeOf(publisher, msg.sender) >= amount, "insufficient stake");
        _settle(publisher, msg.sender); // bank rewards before shares change
        // Burn the shares corresponding to `amount` assets at the current rate.
        uint256 burnShares = (amount * totalShares[publisher]) / poolStake[publisher];
        sharesOf[publisher][msg.sender] -= burnShares;
        totalShares[publisher] -= burnShares;
        poolStake[publisher] -= amount;
        rewardDebt[publisher][msg.sender] = (sharesOf[publisher][msg.sender] * accRewardPerShare[publisher]) / ACC_PRECISION;

        // Move the assets into the unbonding queue, where they stay slashable until
        // withdrawal. A prior pending unbond is re-based to the current haircut factor
        // (locking in slashes it already took) before the new amount is added.
        uint256 s = _unbondScale(publisher);
        Unbond storage u = unbonding[publisher][msg.sender];
        if (u.amount > 0) {
            u.amount = (u.amount * s) / u.scaleAtRequest;
        }
        u.amount += amount;
        u.scaleAtRequest = s;
        u.readyAt = block.timestamp + UNBOND_PERIOD;
        totalUnbonding[publisher] += amount;
        emit UnstakeRequested(publisher, msg.sender, amount, u.readyAt);
    }

    /// @dev Current unbonding haircut factor for a pool (ONE if never slashed).
    function _unbondScale(address publisher) internal view returns (uint256) {
        uint256 s = unbondScale[publisher];
        return s == 0 ? ONE : s;
    }

    /// @notice After the cooldown, return the unbonded tokens to the staker — net of any
    ///         slashing that hit the pool while the stake was unbonding.
    function withdraw(address publisher) external nonReentrant {
        Unbond storage u = unbonding[publisher][msg.sender];
        require(u.amount > 0, "nothing to withdraw");
        require(block.timestamp >= u.readyAt, "cooling down");
        // Apply any haircut taken since the request: net = amount * scaleNow / scaleAtRequest.
        uint256 net = (u.amount * _unbondScale(publisher)) / u.scaleAtRequest;
        delete unbonding[publisher][msg.sender];
        // Keep the pool's unbonding total consistent (clamp for integer-division dust).
        uint256 pending = totalUnbonding[publisher];
        totalUnbonding[publisher] = pending > net ? pending - net : 0;
        beacon.safeTransfer(msg.sender, net);
        emit Withdrawn(publisher, msg.sender, net);
    }

    // --- slashing ----------------------------------------------------------

    /// @notice Slash a publisher's pool by `bps` basis points (capped at MAX_SLASH_BPS).
    ///         Cuts BOTH active stake and stake that is unbonding — so a publisher can't
    ///         dodge a slash by requesting an unstake first. Active stakers are cut
    ///         pro-rata via the shares model; unbonding positions via the haircut factor.
    ///         Slashed tokens go to the slash treasury. Owner or authorized slasher.
    function slash(address publisher, uint256 bps) external {
        require(msg.sender == owner() || msg.sender == slasher, "not authorized");
        require(bps > 0, "zero bps");
        require(bps <= MAX_SLASH_BPS, "slash too large");
        uint256 active = poolStake[publisher];
        uint256 pending = totalUnbonding[publisher];
        require(active + pending > 0, "empty pool");

        uint256 activeCut = (active * bps) / 10_000;
        poolStake[publisher] = active - activeCut; // shares unchanged -> pro-rata haircut

        uint256 pendingCut = 0;
        if (pending > 0) {
            pendingCut = (pending * bps) / 10_000;
            totalUnbonding[publisher] = pending - pendingCut;
            // Multiply the haircut factor so every pending unbond is cut pro-rata on withdraw.
            unbondScale[publisher] = (_unbondScale(publisher) * (10_000 - bps)) / 10_000;
        }

        uint256 cut = activeCut + pendingCut;
        beacon.safeTransfer(slashTreasury, cut);
        emit Slashed(publisher, cut, bps);
    }

    /// @notice Set the destination for slashed tokens (owner only).
    function setSlashTreasury(address treasury) external onlyOwner {
        require(treasury != address(0), "zero treasury");
        slashTreasury = treasury;
        emit SlashTreasurySet(treasury);
    }

    /// @notice Authorize an automated slasher (e.g. the median oracle), owner only.
    ///         Pass address(0) to disable. The owner can always slash regardless.
    function setSlasher(address slasher_) external onlyOwner {
        slasher = slasher_;
        emit SlasherSet(slasher_);
    }

    // --- rewards -----------------------------------------------------------

    /// @notice Distribute reward-token (e.g. USDC) to a publisher's pool. The publisher
    ///         keeps its commission off the top; the remainder accrues pro-rata to every
    ///         staker by shares. Governance-funded (owner) from protocol fees; capped per
    ///         epoch to bound APY and deter reward-gaming.
    function distributeRewards(address publisher, uint256 amount) external onlyOwner {
        require(address(rewardToken) != address(0), "reward token unset");
        require(amount > 0, "zero amount");
        uint256 supply = totalShares[publisher];
        require(supply > 0, "empty pool");

        if (maxRewardPerEpoch > 0) {
            if (block.timestamp >= rewardEpochStart[publisher] + REWARD_EPOCH) {
                rewardEpochStart[publisher] = block.timestamp;
                rewardedThisEpoch[publisher] = 0;
            }
            require(rewardedThisEpoch[publisher] + amount <= maxRewardPerEpoch, "epoch cap");
            rewardedThisEpoch[publisher] += amount;
        }

        rewardToken.safeTransferFrom(msg.sender, address(this), amount);
        uint256 fee = (amount * publisherFeeBps[publisher]) / 10_000;
        if (fee > 0) claimable[publisher][publisher] += fee;
        uint256 distributable = amount - fee;
        accRewardPerShare[publisher] += (distributable * ACC_PRECISION) / supply;
        emit RewardsDistributed(publisher, amount, fee);
    }

    /// @notice Claim accrued reward-token from a publisher's pool.
    function claim(address publisher) external nonReentrant returns (uint256 amount) {
        _settle(publisher, msg.sender);
        amount = claimable[publisher][msg.sender];
        if (amount > 0) {
            claimable[publisher][msg.sender] = 0;
            rewardToken.safeTransfer(msg.sender, amount);
        }
        emit RewardsClaimed(publisher, msg.sender, amount);
    }

    /// @notice Publisher sets its commission (bps) on its pool's rewards (capped).
    function setPublisherFee(uint256 bps) external {
        require(bps <= MAX_FEE_BPS, "fee too high");
        publisherFeeBps[msg.sender] = bps;
        emit PublisherFeeSet(msg.sender, bps);
    }

    /// @notice Set the reward token (e.g. USDC), owner only.
    function setRewardToken(address token) external onlyOwner {
        require(token != address(0), "zero token");
        rewardToken = IERC20(token);
        emit RewardTokenSet(token);
    }

    /// @notice Cap reward-token distributable to one pool per epoch (0 = no cap), owner only.
    function setMaxRewardPerEpoch(uint256 amount) external onlyOwner {
        maxRewardPerEpoch = amount;
        emit MaxRewardPerEpochSet(amount);
    }
}
