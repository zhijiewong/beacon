# Phase 2 Design — On-Chain Oracle, Token & Staking

**Version:** 0.1 (DRAFT — design only, no implementation yet)
**Date:** 2026-06-07
**Status:** for study/review; build gated on Phase 1 traction
**Prereq:** Phase 1 (the public index + daily collector) — built and running.

> This is a **design document**, not a build order to execute now. It exists so the
> on-chain stack is fully thought through before any contract is written, and so the
> token is sequenced correctly (see §1). The first *buildable* sub-project is the
> on-chain oracle (§4); the token (§6) and staking (§7) come later.

---

## 1. Sequencing (the non-negotiable constraint)

The Phase 1 spec and the token-launch research are explicit: **launch the token only
after the product has real traction** (the Hyperliquid pattern; ~85% of early-launched
2025 tokens crashed). As of now Phase 1 has ~1 day of data and no users. Therefore:

- **Build now (when ready):** the on-chain oracle on **testnet** — free, no token, no real money.
- **Build after the oracle works AND Phase 1 has usage:** the token, staking, distribution.
- **Never:** mint a live token to chase momentum before the rate has consumers.

This document covers all of Phase 2 for completeness, but the **dependency order** is:
oracle → (traction) → token → staking → distribution.

---

## 2. Goals & non-goals

**Goal:** make the Beacon rate readable by smart contracts, agents, and (Phase 3)
derivatives — i.e., turn the off-chain index into an on-chain, consumable reference rate,
and eventually secure it economically with a staked token.

**Non-goals (Phase 2):** running a derivatives venue (Phase 3), high-frequency updates
(Beacon is daily), and any mainnet deployment before a security audit.

---

## 3. Chain & tooling decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Chain | **Base** (Ethereum L2) | EVM = most tooling/learning material; fees in cents; x402/USDC-native (aligns with Phase 3); strong ecosystem. |
| Testnet | **Base Sepolia** | Free test ETH; identical to mainnet for development. |
| Oracle pattern | **Push-based** (publisher writes value) | Beacon updates daily, so push is simpler/cheaper than Pyth-style pull/attestation (which suits high-frequency feeds). |
| Contract language | **Solidity** + **Foundry** | Industry-standard, fast tests, best learning resources. |
| Publisher | **Python + web3.py** | Reuses the Phase 1 pipeline; web3.py is isolated to the publisher and does NOT touch the zero-dependency core. |
| Value encoding | **int256, 8-decimal fixed point** | Chainlink convention; `$1.368/Mtok` → `136_800_000`. Signed to allow future signed metrics. |

---

## 4. Sub-project A — the on-chain oracle (FIRST, buildable)

### 4.1 Contract: `BeaconOracle.sol`
A minimal, auditable store of named feeds. v1 has a single authorized publisher (the
project); §7 later replaces that with staked multi-publisher aggregation.

```solidity
struct Feed {
    int256  value;             // price $/Mtok, 8-decimal fixed point
    uint64  updatedAt;         // block timestamp of last post
    uint32  methodologyVersion;// from docs/methodology.md
    bytes8  snapshotDate;      // e.g. "20260607" — provenance back to a snapshot
}

mapping(bytes32 => Feed) private feeds;        // id => latest value
address public publisher;                       // authorized writer (v1)

event FeedPosted(bytes32 indexed id, int256 value, uint64 updatedAt, bytes8 snapshotDate);

function postFeed(bytes32 id, int256 value, uint32 mver, bytes8 date) external; // onlyPublisher
function getFeed(bytes32 id) external view returns (Feed memory);
function latestValue(bytes32 id) external view returns (int256 value, uint64 updatedAt);
```

- **Feed IDs:** `keccak256(abi.encodePacked("GPQA-Diamond", tier))`, where tier ∈
  {`frontier`, `strong`, `gpt-4-class`, `spread`}. A small published registry maps
  human names → IDs.
- **Consumer contract** reads `latestValue(id)` and MUST check `updatedAt` for staleness
  (e.g., reject if older than 48h) — the standard oracle-consumer safety pattern.
- **Access control:** `onlyPublisher` (Ownable-style) in v1. Keep the contract tiny and
  free of upgradeable-proxy complexity initially; if upgradeability is needed, prefer a
  new deployment + registry pointer over an in-place proxy until audited.

### 4.2 Publisher (off-chain → on-chain bridge): `beacon/publisher.py`
After the Phase 1 pipeline computes the daily index, the publisher:
1. Loads the latest snapshot's iso-quality values per tier (reuses `beacon.analyze`).
2. Encodes each to 8-decimal fixed point.
3. Sends `postFeed` transactions to `BeaconOracle` (web3.py), signed by the publisher key.
4. Logs tx hashes; non-fatal (a failed post never breaks collection).

Cadence: once daily, after collection. Cost on Base mainnet: a few small txns ≈ cents/day.

### 4.3 Build milestones (testnet-first, when ready)
1. `BeaconOracle.sol` + Foundry unit tests (local `anvil`, free).
2. `publisher.py` posts to local `anvil`; round-trip read verifies value integrity.
3. Deploy to **Base Sepolia**; publish a real testnet rate; read it from a separate
   consumer call. **Acceptance:** the value read on-chain equals the index computed off-chain.
4. (later) wire a tiny example "consumer" contract that reads + staleness-checks the feed.

---

## 5. Security & risk (oracle)
- **Manipulation:** v1 trusts one publisher (acceptable on testnet / pre-token). The
  trust-minimized version is §7 (staked multi-publisher median + slashing).
- **Stale data:** consumers enforce freshness via `updatedAt`. Publisher monitors for
  missed posts.
- **Key management:** publisher key in a dedicated env/secret, never in the repo; testnet
  key is throwaway. Mainnet later uses a hardware/managed signer.
- **Audit:** required before mainnet and before any token. No exceptions.

---

## 6. Sub-project B — the token `BEACON` (LATER, gated)
- **Standard:** ERC-20 on Base.
- **Job (from Phase 1 spec):** secure the oracle + capture fees + govern — NOT a unit of
  account (settlement stays in USDC).
- **Value accrual:** stakers earn a share of protocol fees (data licensing + Phase 3
  settlement), **paid in USDC**, not inflation (GMX/dYdX lesson).
- **Distribution:** no/minimal VC; community-first; **points → airdrop** to real Phase 1
  contributors (data publishers, early feed consumers); **modest FDV, honest vesting,
  real float** (avoid the low-float/high-FDV pattern that crashed 85% of 2025 launches).

## 7. Sub-project C — Oracle Integrity Staking (LATER, hardest)
Replaces the single-publisher trust model with Pyth-style economic security:
- **Publishers self-stake** BEACON to be eligible to post feeds and earn rewards.
- **Delegators** stake to back trustworthy publishers' pools.
- **Aggregation:** the on-chain feed value becomes the **median** of staked publishers'
  submissions (manipulation-resistant; the SOFR "deep, honest inputs" lesson).
- **Slashing** (capped, e.g. ≤5% per event, à la Pyth) on pools that post bad data.
- **Rewards** funded from protocol fees, capped per epoch, USDC-denominated.
- **Governance:** token-holders set the feed registry, methodology parameters, slashing
  caps, fee splits.

## 8. Sub-project D — distribution (LATER)
Points program during Phase 1 → genesis airdrop at token launch. Tracks real
contribution (running a publisher, consuming feeds, contributing verified benchmark
data), not capital. Quality over quantity (Hyperliquid: ~94k real users, not 1M farmers).

---

## 9. Phase 3 hooks (design the oracle to be consumed)
The oracle interface in §4 is deliberately consumption-ready so Phase 3 needs no redesign:
- **x402 agents** reference `latestValue` to sanity-check/settle inference payments.
- **HIP-3 inference-price perp** (Hyperliquid) cash-settles against a Beacon feed.
- **FinOps/procurement licensing** reads feeds (a fee source for §6 rewards).

---

## 10. Costs
| Item | Cost |
|------|------|
| Testnet (all of §4 dev) | **$0** (free Base Sepolia ETH) |
| Daily mainnet posting (later) | a few feeds × small gas ≈ **cents/day** |
| Security audit (before mainnet/token) | **real** (budget for it; non-optional) |
| Token deploy | small gas; the audit is the real cost |

---

## 11. Open questions (resolve during build, not now)
1. Final feed taxonomy/IDs and the human-name → `bytes32` registry format.
2. Fixed-point decimals (8 proposed) and how `spread` (a ratio, not a price) is encoded.
3. Staleness threshold for consumers (48h proposed).
4. Publisher key management for mainnet (managed signer vs hardware).
5. Depth of governance at token launch (minimal multisig → progressive decentralization).
6. Audit timing and budget.

---

## 12. What "done" means for this design
This document is the agreed Phase-2 picture. The **only** thing to build first, and only
when you choose to, is §4 (the testnet oracle + publisher). Token/staking/distribution
(§6–8) are documented but explicitly deferred until the oracle works and Phase 1 has
real usage. Each sub-project will get its own implementation plan when its time comes.
