// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title BeaconOracle
/// @notice Minimal push-based price oracle for the Beacon AI-inference reference rate.
///         A single authorized publisher posts named feeds (one per capability tier);
///         anyone can read them. v1 is intentionally tiny and trust-minimized later by
///         Oracle Integrity Staking (see docs/phase2-onchain-oracle-design.md §7).
/// @dev    `value` is USD per 1M tokens in 8-decimal fixed point (Chainlink convention).
contract BeaconOracle {
    struct Feed {
        int256 value;              // $/Mtok, 8-decimal fixed point
        uint64 updatedAt;          // block timestamp of last post
        uint32 methodologyVersion; // e.g. v0.1 -> 10 (integer hundredths)
        bytes8 snapshotDate;       // ASCII provenance, e.g. "20260606"
    }

    address public publisher;
    mapping(bytes32 => Feed) private _feeds;

    event FeedPosted(bytes32 indexed id, int256 value, uint64 updatedAt, bytes8 snapshotDate);
    event PublisherChanged(address indexed from, address indexed to);

    modifier onlyPublisher() {
        require(msg.sender == publisher, "not publisher");
        _;
    }

    constructor() {
        publisher = msg.sender;
    }

    /// @notice Post (create or overwrite) a feed's latest value.
    function postFeed(bytes32 id, int256 value, uint32 methodologyVersion, bytes8 snapshotDate)
        external
        onlyPublisher
    {
        Feed storage f = _feeds[id];
        f.value = value;
        f.updatedAt = uint64(block.timestamp);
        f.methodologyVersion = methodologyVersion;
        f.snapshotDate = snapshotDate;
        emit FeedPosted(id, value, f.updatedAt, snapshotDate);
    }

    /// @notice Full feed record. Unknown ids return a zeroed struct.
    function getFeed(bytes32 id) external view returns (Feed memory) {
        return _feeds[id];
    }

    /// @notice Convenience reader; consumers MUST check `updatedAt` for staleness.
    function latestValue(bytes32 id) external view returns (int256 value, uint64 updatedAt) {
        Feed storage f = _feeds[id];
        return (f.value, f.updatedAt);
    }

    /// @notice Rotate the authorized publisher.
    function setPublisher(address newPublisher) external onlyPublisher {
        require(newPublisher != address(0), "zero address");
        emit PublisherChanged(publisher, newPublisher);
        publisher = newPublisher;
    }
}
