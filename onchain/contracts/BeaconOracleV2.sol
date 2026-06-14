// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";

/// @notice Subset of BeaconStaking the oracle needs: gate submissions on eligibility
///         and trigger deviation slashing.
interface IBeaconStaking {
    function isEligiblePublisher(address publisher) external view returns (bool);
    function slash(address publisher, uint256 bps) external;
    function poolStake(address publisher) external view returns (uint256);
}

/// @title BeaconOracleV2 — multi-publisher, stake-weighted-median, self-policing feed
/// @notice Eligible publishers (those meeting the staking minimum) submit a value per
///         feed id during a round. `finalizeRound` aggregates by a stake-weighted median
///         (influence tracks skin in the game, so the rate resists sybil/low-stake
///         manipulation), publishes the result, and auto-slashes any publisher whose
///         submission deviated beyond MAX_DEVIATION_BPS from that median — closing the
///         loop between "stake on accuracy" and "inaccuracy costs you". Replaces v1.
///         An optional staleness window excludes un-refreshed submissions from both the
///         median and slashing, so a publisher isn't judged on data it didn't restate.
/// @dev    TESTNET ONLY — unaudited. Round model: submissions accumulate until anyone
///         (subject to a quorum) finalizes; finalizing clears the round.
contract BeaconOracleV2 is Ownable2Step {
    IBeaconStaking public immutable staking;

    /// Hard cap on the configurable slash — equals staking's MAX_SLASH_BPS so that
    /// `staking.slash` can never revert from too-large a value. Not governable.
    uint256 public constant DEVIATION_SLASH_BPS_CAP = 500;

    /// Max deviation from the round median before a submission is slashed (default 10%).
    uint256 public maxDeviationBps = 1000;
    /// Slash applied to a deviating publisher's pool (default 5%; ≤ cap).
    uint256 public deviationSlashBps = 500;
    /// Minimum submissions required to finalize a round (governance-settable).
    uint256 public minPublishers = 1;
    /// Submissions older than this (seconds) are excluded from aggregation and not
    /// slashed. 0 = disabled (no staleness filtering). Governance-settable.
    uint256 public maxStaleness = 0;
    /// Max distinct publishers per round, so finalize gas stays bounded. Governance-settable.
    uint256 public maxPublishersPerRound = 64;

    // --- current round state, per feed id ---
    mapping(bytes32 => address[]) private feedPublishers; // who submitted this round
    mapping(bytes32 => mapping(address => uint256)) public submission; // latest value
    mapping(bytes32 => mapping(address => uint256)) public submittedAt;
    mapping(bytes32 => mapping(address => bool)) public hasSubmitted;

    // --- last finalized aggregate, per feed id ---
    mapping(bytes32 => uint256) public latestAggregate;
    mapping(bytes32 => uint256) public latestAggregateAt;

    event Submitted(bytes32 indexed id, address indexed publisher, uint256 value);
    event RoundFinalized(bytes32 indexed id, uint256 median, uint256 publishers);
    event PublisherSlashed(bytes32 indexed id, address indexed publisher, uint256 value, uint256 median);
    event MinPublishersSet(uint256 minPublishers);
    event MaxDeviationBpsSet(uint256 bps);
    event DeviationSlashBpsSet(uint256 bps);
    event MaxStalenessSet(uint256 seconds_);
    event MaxPublishersPerRoundSet(uint256 n);

    constructor(IBeaconStaking staking_) Ownable(msg.sender) {
        require(address(staking_) != address(0), "zero staking");
        staking = staking_;
    }

    // --- submission -------------------------------------------------------

    /// @notice Eligible publisher posts (or overwrites) its value for this round.
    function postFeed(bytes32 id, uint256 value) external {
        require(staking.isEligiblePublisher(msg.sender), "not eligible");
        require(value > 0, "zero value");
        if (!hasSubmitted[id][msg.sender]) {
            require(feedPublishers[id].length < maxPublishersPerRound, "round full");
            hasSubmitted[id][msg.sender] = true;
            feedPublishers[id].push(msg.sender);
        }
        submission[id][msg.sender] = value;
        submittedAt[id][msg.sender] = block.timestamp;
        emit Submitted(id, msg.sender, value);
    }

    // --- views ------------------------------------------------------------

    /// @notice Stake-weighted median of the current round's submissions (0 if none).
    function median(bytes32 id) public view returns (uint256) {
        uint256 n = feedPublishers[id].length;
        if (n == 0) return 0;
        return _aggregate(id, n);
    }

    /// @notice Last finalized aggregate value and its timestamp (consumer read).
    function latestValue(bytes32 id) external view returns (uint256 value, uint256 timestamp) {
        return (latestAggregate[id], latestAggregateAt[id]);
    }

    /// @notice Number of submissions in the current (unfinalized) round.
    function roundSize(bytes32 id) external view returns (uint256) {
        return feedPublishers[id].length;
    }

    // --- finalization -----------------------------------------------------

    /// @notice Aggregate the round by median, publish it, slash deviators, and clear the
    ///         round. Permissionless but quorum-gated.
    function finalizeRound(bytes32 id) external {
        address[] storage pubs = feedPublishers[id];
        uint256 n = pubs.length;
        require(_freshCount(id, n) >= minPublishers && n > 0, "quorum");

        uint256 m = _aggregate(id, n);
        latestAggregate[id] = m;
        latestAggregateAt[id] = block.timestamp;

        // Slash any fresh publisher whose submission deviated beyond the threshold.
        // Stale submissions are excluded from the median, so they aren't judged here.
        for (uint256 i = 0; i < n; i++) {
            address p = pubs[i];
            if (!_isFresh(id, p)) continue;
            uint256 v = submission[id][p];
            uint256 diff = v > m ? v - m : m - v;
            if (m > 0 && (diff * 10_000) / m > maxDeviationBps) {
                staking.slash(p, deviationSlashBps);
                emit PublisherSlashed(id, p, v, m);
            }
        }
        emit RoundFinalized(id, m, n);

        // Clear the round for a fresh start.
        for (uint256 i = 0; i < n; i++) {
            address p = pubs[i];
            delete submission[id][p];
            delete submittedAt[id][p];
            delete hasSubmitted[id][p];
        }
        delete feedPublishers[id];
    }

    // --- governance -------------------------------------------------------

    function setMinPublishers(uint256 n) external onlyOwner {
        require(n > 0, "zero quorum");
        minPublishers = n;
        emit MinPublishersSet(n);
    }

    /// @notice Tune the deviation tolerance (bps) before a submission is slashed.
    function setMaxDeviationBps(uint256 bps) external onlyOwner {
        require(bps > 0, "zero deviation");
        maxDeviationBps = bps;
        emit MaxDeviationBpsSet(bps);
    }

    /// @notice Tune the slash applied to deviators (bps), capped so staking never reverts.
    function setDeviationSlashBps(uint256 bps) external onlyOwner {
        require(bps > 0, "zero slash");
        require(bps <= DEVIATION_SLASH_BPS_CAP, "slash too high");
        deviationSlashBps = bps;
        emit DeviationSlashBpsSet(bps);
    }

    /// @notice Set the staleness window (seconds); 0 disables staleness filtering.
    function setMaxStaleness(uint256 seconds_) external onlyOwner {
        maxStaleness = seconds_;
        emit MaxStalenessSet(seconds_);
    }

    /// @notice Cap the distinct publishers allowed per round (bounds finalize gas).
    function setMaxPublishersPerRound(uint256 n) external onlyOwner {
        require(n > 0, "zero cap");
        maxPublishersPerRound = n;
        emit MaxPublishersPerRoundSet(n);
    }

    // --- internal ---------------------------------------------------------

    /// @dev Stake-weighted median of the current submissions for `id`. Each publisher's
    ///      submission is weighted by its pool stake, so the rate can't be swayed by
    ///      spinning up many minimally-staked publishers — influence tracks skin in the
    ///      game. Returns the lower weighted median (first value where cumulative weight
    ///      reaches half of total). With equal stakes this reduces to the plain median.
    ///      Insertion sort over a memory copy — publisher counts are small.
    function _aggregate(bytes32 id, uint256 n) internal view returns (uint256) {
        address[] storage pubs = feedPublishers[id];
        uint256[] memory vals = new uint256[](n);
        uint256[] memory wts = new uint256[](n);
        uint256 k = 0; // number of fresh submissions
        uint256 total = 0;
        for (uint256 i = 0; i < n; i++) {
            address p = pubs[i];
            if (!_isFresh(id, p)) continue; // stale submissions don't count
            vals[k] = submission[id][p];
            uint256 w = staking.poolStake(p);
            wts[k] = w;
            total += w;
            k++;
        }
        if (k == 0) return 0;
        // Degenerate case (no stake recorded): fall back to equal weights.
        if (total == 0) {
            for (uint256 i = 0; i < k; i++) wts[i] = 1;
            total = k;
        }
        // Insertion sort the first k (value, weight) pairs by value ascending.
        for (uint256 i = 1; i < k; i++) {
            uint256 kv = vals[i];
            uint256 kw = wts[i];
            uint256 j = i;
            while (j > 0 && vals[j - 1] > kv) {
                vals[j] = vals[j - 1];
                wts[j] = wts[j - 1];
                j--;
            }
            vals[j] = kv;
            wts[j] = kw;
        }
        uint256 cum = 0;
        for (uint256 i = 0; i < k; i++) {
            cum += wts[i];
            if (2 * cum >= total) return vals[i];
        }
        return vals[k - 1]; // unreachable: cumulative always reaches total
    }

    /// @dev Whether a publisher's submission is within the staleness window.
    function _isFresh(bytes32 id, address p) internal view returns (bool) {
        if (maxStaleness == 0) return true;
        return block.timestamp - submittedAt[id][p] <= maxStaleness;
    }

    /// @dev Count of fresh submissions in the current round.
    function _freshCount(bytes32 id, uint256 n) internal view returns (uint256) {
        if (maxStaleness == 0) return n;
        address[] storage pubs = feedPublishers[id];
        uint256 k = 0;
        for (uint256 i = 0; i < n; i++) {
            if (_isFresh(id, pubs[i])) k++;
        }
        return k;
    }
}
