// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Test} from "forge-std/Test.sol";
import {BeaconStaking} from "../../contracts/BeaconStaking.sol";
import {BeaconToken} from "../../contracts/BeaconToken.sol";

/// @notice Drives BeaconStaking with bounded random stake/unstake/withdraw/slash
///         sequences for invariant testing. Acts as each of a small set of pre-funded
///         actors; is wired as the staking `slasher` so it can exercise slashing too.
contract StakingHandler is Test {
    BeaconStaking public staking;
    BeaconToken public token;
    address[] public actors; // stakers (pre-funded + approved in the test setUp)
    address[] public pubs; // publishers with a live pool (self-staked in setUp)

    constructor(BeaconStaking s_, BeaconToken t_, address[] memory actors_, address[] memory pubs_) {
        staking = s_;
        token = t_;
        actors = actors_;
        pubs = pubs_;
    }

    function _actor(uint256 seed) internal view returns (address) {
        return actors[seed % actors.length];
    }

    function _pub(uint256 seed) internal view returns (address) {
        return pubs[seed % pubs.length];
    }

    function delegate(uint256 aSeed, uint256 pSeed, uint256 amount) external {
        address a = _actor(aSeed);
        address p = _pub(pSeed);
        uint256 bal = token.balanceOf(a);
        if (bal == 0) return;
        amount = bound(amount, 1, bal);
        vm.prank(a);
        try staking.delegate(p, amount) {} catch {}
    }

    function selfStakeMore(uint256 pSeed, uint256 amount) external {
        address p = _pub(pSeed);
        uint256 bal = token.balanceOf(p);
        if (bal == 0) return;
        amount = bound(amount, 1, bal);
        vm.prank(p);
        try staking.selfStake(amount) {} catch {}
    }

    function requestUnstake(uint256 aSeed, uint256 pSeed, uint256 amount) external {
        address a = _actor(aSeed);
        address p = _pub(pSeed);
        uint256 staked = staking.stakeOf(p, a);
        if (staked == 0) return;
        amount = bound(amount, 1, staked);
        vm.prank(a);
        try staking.requestUnstake(p, amount) {} catch {}
    }

    function withdraw(uint256 aSeed, uint256 pSeed) external {
        address a = _actor(aSeed);
        address p = _pub(pSeed);
        vm.prank(a);
        try staking.withdraw(p) {} catch {}
    }

    function slash(uint256 pSeed, uint256 bps) external {
        address p = _pub(pSeed);
        bps = bound(bps, 1, 500); // <= MAX_SLASH_BPS
        try staking.slash(p, bps) {} catch {}
    }

    function warp(uint256 secs) external {
        secs = bound(secs, 1, 8 days); // span the 7-day unbond cooldown
        vm.warp(block.timestamp + secs);
    }
}
