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
    StakingHandler internal handler;

    address[] internal actors;
    address[] internal pubs;

    uint256 internal constant MIN = 1000e18; // MIN_PUBLISHER_STAKE
    uint256 internal constant FUND = 100_000e18;

    function setUp() public {
        token = new BeaconToken(address(this)); // mints full supply to this test
        staking = new BeaconStaking(token);

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

        handler = new StakingHandler(staking, token, actors, pubs);
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
}
