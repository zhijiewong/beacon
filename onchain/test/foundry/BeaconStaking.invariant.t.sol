// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Test} from "forge-std/Test.sol";
import {BeaconStaking} from "../../contracts/BeaconStaking.sol";
import {BeaconToken} from "../../contracts/BeaconToken.sol";
import {StakingHandler} from "./StakingHandler.sol";

/// @notice Invariant tests for the BeaconStaking vault accounting — the highest-risk code.
///         Random sequences of stake/delegate/unstake/withdraw/slash must always preserve:
///           1. solvency — the contract holds at least what it accounts as owed;
///           2. no over-claim — stakers can't collectively claim more than their pool holds.
contract BeaconStakingInvariant is Test {
    BeaconStaking internal staking;
    BeaconToken internal token;
    BeaconToken internal reward;
    StakingHandler internal handler;

    address[] internal actors;
    address[] internal pubs;

    uint256 internal constant MIN = 1000e18; // MIN_PUBLISHER_STAKE
    uint256 internal constant FUND = 100_000e18;

    function setUp() public {
        token = new BeaconToken(address(this)); // mints full supply to this test
        staking = new BeaconStaking(token);
        reward = new BeaconToken(address(this)); // reward token; supply to owner (this)
        staking.setRewardToken(address(reward));
        reward.approve(address(staking), type(uint256).max); // owner funds distributions

        // 4 actors; the first two are also publishers with live pools.
        actors = [address(0xA0), address(0xA1), address(0xA2), address(0xA3)];
        pubs = [address(0xA0), address(0xA1)];

        for (uint256 i = 0; i < actors.length; i++) {
            token.transfer(actors[i], FUND);
            vm.prank(actors[i]);
            token.approve(address(staking), type(uint256).max);
        }
        for (uint256 i = 0; i < pubs.length; i++) {
            vm.prank(pubs[i]);
            staking.selfStake(MIN); // create the pool + become eligible
        }

        handler = new StakingHandler(staking, token, reward, address(this), actors, pubs);
        staking.setSlasher(address(handler)); // let the handler exercise slashing

        targetContract(address(handler));
    }

    /// The vault must always hold at least the active + unbonding stake it owes.
    function invariant_solvent() public view {
        uint256 owed;
        for (uint256 i = 0; i < pubs.length; i++) {
            owed += staking.poolStake(pubs[i]) + staking.totalUnbonding(pubs[i]);
        }
        assertGe(token.balanceOf(address(staking)), owed, "insolvent: balance < owed");
    }

    /// Per pool, the sum of every staker's claimable stake can't exceed the pool's assets.
    function invariant_noOverclaim() public view {
        for (uint256 i = 0; i < pubs.length; i++) {
            address p = pubs[i];
            uint256 sum;
            for (uint256 j = 0; j < actors.length; j++) {
                sum += staking.stakeOf(p, actors[j]);
            }
            // floor-rounded shares can only undershoot; allow 1 wei/staker of dust.
            assertLe(sum, staking.poolStake(p) + actors.length, "over-claim: stakers > pool");
        }
    }

    /// The contract must always hold at least the reward-token it owes — the sum of every
    /// staker's pending (accrued + settled-unclaimed) rewards across all pools, which also
    /// covers publisher commission (banked in the publisher's own claimable balance).
    /// Allowance: MasterChef-style accounting floors `accrued - rewardDebt` on every settle,
    /// which can over-bank ≤1 wei each; the cumulative over-owe is therefore bounded by the
    /// number of mutating interactions (`mutations` wei) — negligible dust, never material
    /// under-collateralization.
    function invariant_rewardSolvent() public view {
        uint256 owed;
        for (uint256 i = 0; i < pubs.length; i++) {
            for (uint256 j = 0; j < actors.length; j++) {
                owed += staking.pendingRewards(pubs[i], actors[j]);
            }
        }
        assertGe(
            reward.balanceOf(address(staking)) + handler.mutations(),
            owed,
            "reward-insolvent: balance + dust < owed"
        );
    }

    /// Deterministic companion proving the reward path the fuzzer exercises is real: a pool with
    /// a publisher + delegator receives a distribution, the held reward-token equals exactly what
    /// is owed, and after a partial claim the relation still holds. Guards against the fuzzed
    /// invariant being vacuously satisfied if reward distributions ever stop firing.
    function test_rewardSolvency_concrete() public {
        address pub = pubs[0];
        address del = actors[2]; // not a publisher
        vm.prank(del);
        staking.delegate(pub, 1000e18); // pool now 2000 assets: 1000 pub + 1000 delegator

        staking.distributeRewards(pub, 100e18); // owner funds 100 reward-token to the pool

        uint256 owed = staking.pendingRewards(pub, pub) + staking.pendingRewards(pub, del);
        assertEq(reward.balanceOf(address(staking)), 100e18);
        assertApproxEqAbs(owed, 100e18, 2, "owed != distributed");

        vm.prank(del);
        uint256 got = staking.claim(pub);
        assertApproxEqAbs(got, 50e18, 1, "delegator's half"); // equal stake -> ~half
        uint256 owedAfter = staking.pendingRewards(pub, pub) + staking.pendingRewards(pub, del);
        assertGe(reward.balanceOf(address(staking)) + 2, owedAfter, "insolvent after claim");
    }
}
