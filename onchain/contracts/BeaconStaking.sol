// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title BeaconStaking — Oracle Integrity Staking (Pyth-style) for the Beacon rate
/// @notice Publishers self-stake BEACON to back the accuracy of the feeds they post;
///         delegators stake to a publisher's pool to share in (future) rewards and
///         (future) slashing. Stage 1: stake / delegate / unbond with a cooldown.
///         Slashing + USDC rewards land in Stage 2.
/// @dev    TESTNET ONLY — unaudited; needs a professional audit before any real value.
///         Staking pulls BEACON via transferFrom (stakers pre-approve this contract).
contract BeaconStaking is ReentrancyGuard {
    using SafeERC20 for IERC20;

    IERC20 public immutable beacon;

    /// Minimum self-stake for a publisher to be eligible to post feeds.
    uint256 public constant MIN_PUBLISHER_STAKE = 1000e18;
    /// Cooldown between requesting an unstake and being able to withdraw.
    uint256 public constant UNBOND_PERIOD = 7 days;

    /// publisher => total active stake backing that publisher (self + delegated).
    mapping(address => uint256) public poolStake;
    /// publisher => staker => active stake the staker has in that publisher's pool.
    mapping(address => mapping(address => uint256)) public stakeOf;

    struct Unbond {
        uint256 amount; // tokens released from active stake, awaiting withdrawal
        uint256 readyAt; // timestamp the tokens become withdrawable
    }
    /// publisher => staker => pending unbond for that (publisher, staker) position.
    mapping(address => mapping(address => Unbond)) public unbonding;

    event SelfStaked(address indexed publisher, uint256 amount);
    event Delegated(address indexed publisher, address indexed delegator, uint256 amount);
    event UnstakeRequested(address indexed publisher, address indexed staker, uint256 amount, uint256 readyAt);
    event Withdrawn(address indexed publisher, address indexed staker, uint256 amount);

    constructor(IERC20 beacon_) {
        require(address(beacon_) != address(0), "zero token");
        beacon = beacon_;
    }

    /// @notice Publisher self-stakes BEACON into its own pool.
    function selfStake(uint256 amount) external nonReentrant {
        require(amount > 0, "zero amount");
        beacon.safeTransferFrom(msg.sender, address(this), amount);
        stakeOf[msg.sender][msg.sender] += amount;
        poolStake[msg.sender] += amount;
        emit SelfStaked(msg.sender, amount);
    }

    /// @notice Delegator stakes BEACON to back an existing publisher's pool.
    /// @dev A publisher is anyone with a non-zero self-stake; eligibility to *post*
    ///      additionally requires MIN_PUBLISHER_STAKE (see isEligiblePublisher).
    function delegate(address publisher, uint256 amount) external nonReentrant {
        require(amount > 0, "zero amount");
        require(stakeOf[publisher][publisher] > 0, "not a publisher");
        beacon.safeTransferFrom(msg.sender, address(this), amount);
        stakeOf[publisher][msg.sender] += amount;
        poolStake[publisher] += amount;
        emit Delegated(publisher, msg.sender, amount);
    }

    /// @notice Begin unstaking: removes tokens from active stake immediately and
    ///         starts the cooldown. A second request resets the cooldown on the
    ///         whole pending amount.
    function requestUnstake(address publisher, uint256 amount) external {
        require(amount > 0, "zero amount");
        require(stakeOf[publisher][msg.sender] >= amount, "insufficient stake");
        stakeOf[publisher][msg.sender] -= amount;
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

    /// @notice Whether a publisher meets the minimum self-stake to post feeds.
    function isEligiblePublisher(address publisher) external view returns (bool) {
        return stakeOf[publisher][publisher] >= MIN_PUBLISHER_STAKE;
    }
}
