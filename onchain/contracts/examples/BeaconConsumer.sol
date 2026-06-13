// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IBeaconOracle} from "../IBeaconOracle.sol";

/// @title BeaconConsumer — reference integration: settle against the Beacon rate
/// @notice Shows the right way for a downstream contract to consume the on-chain rate:
///         read `latestValue`, reject a missing or stale value, then price something
///         against it. This is the demand side the whole project is premised on — any
///         contract or agent can settle money against a neutral, economically-secured
///         price. Example only; not deployed as protocol infrastructure.
contract BeaconConsumer {
    IBeaconOracle public immutable oracle;
    /// Reject any published value older than this (seconds) — the consumer's own
    /// staleness guard, independent of the oracle's internal one.
    uint256 public immutable maxAge;

    constructor(IBeaconOracle oracle_, uint256 maxAge_) {
        require(address(oracle_) != address(0), "zero oracle");
        require(maxAge_ > 0, "zero maxAge");
        oracle = oracle_;
        maxAge = maxAge_;
    }

    /// @notice Current rate for a feed (8-decimal $/Mtok), reverting if missing or stale.
    function readRate(bytes32 id) public view returns (uint256 value) {
        (uint256 v, uint256 ts) = oracle.latestValue(id);
        require(v > 0, "no rate");
        require(block.timestamp - ts <= maxAge, "stale rate");
        return v;
    }

    /// @notice Example settlement: cost to settle `tokensMtok` million-tokens of a
    ///         capability tier at the current iso-quality rate. Returns 8-decimal USD
    ///         (rate is 8-decimal $/Mtok × an integer count of millions of tokens).
    function quote(bytes32 id, uint256 tokensMtok) external view returns (uint256 costUsd) {
        return readRate(id) * tokensMtok;
    }
}
