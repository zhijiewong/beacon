// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title IBeaconOracle — the read interface integrators settle against
/// @notice Minimal surface a downstream contract or agent needs to consume the Beacon
///         reference rate. `value` is the capability-normalized price in 8-decimal fixed
///         point ($/million-tokens); `timestamp` is when that value was last published,
///         for the consumer's own staleness checks.
interface IBeaconOracle {
    /// @param id keccak256("<benchmark>:<tier>"), e.g. keccak256("GPQA-Diamond:frontier")
    /// @return value 8-decimal $/Mtok (0 if the feed has never been finalized)
    /// @return timestamp unix time the value was last published
    function latestValue(bytes32 id) external view returns (uint256 value, uint256 timestamp);
}
