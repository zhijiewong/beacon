# Beacon Protocol — Formal Specification

> Audit-oriented statement of what the on-chain system *must* guarantee, independent of
> implementation. Pairs with [`phase2-onchain-oracle-design.md`](phase2-onchain-oracle-design.md)
> (design + build log), [`security-review.md`](security-review.md) (Slither triage + findings),
> and [`audit-scope.md`](audit-scope.md) (audit boundary).
>
> **Status: Base Sepolia testnet, unaudited.** A professional audit is the non-negotiable gate
> before any mainnet deployment or real value. This document is written to be that audit's spec.

## 1. System overview

Three contracts plus a read interface form the trust boundary:

| Contract | Role | Trust held |
|----------|------|-----------|
| `BeaconToken` | Fixed-supply ERC-20 (test token) | None beyond standard ERC-20 |
| `BeaconStaking` | Oracle Integrity Staking: self-stake/delegation, unbonding, slashing, rewards | Custodies all staked BEACON and owed reward-token |
| `BeaconOracleV2` | Stake-weighted-median feed + deviation slashing | Authorized `slasher` on `BeaconStaking` |
| `IBeaconOracle` | Read surface integrators settle against | — |

Data flow: eligible publishers `postFeed` per round → anyone `finalizeRound` → a stake-weighted
median is published to `latestValue` and deviating publishers are slashed via `BeaconStaking.slash`.

## 2. Actors & trust model

- **Owner** (governance; migrating to a multisig — see [`ownership-transfer-runbook.md`](ownership-transfer-runbook.md)).
  Trusted to set parameters within hard-coded bounds, fund rewards, pause, and rescue
  non-protocol tokens. **Cannot** touch staked principal or owed rewards, raise a slash above
  `MAX_SLASH_BPS`, repoint the reward token once set, or mint tokens. Two-step (`Ownable2Step`).
- **Slasher** (the oracle, or address(0)). May call `slash` within the same `MAX_SLASH_BPS` cap;
  nothing else. Owner can always slash regardless.
- **Publishers** — self-stake ≥ `MIN_PUBLISHER_STAKE` to post feeds; bear slashing on bad data.
- **Delegators** — stake to a publisher's pool; share rewards and slashing risk pro-rata.
- **Integrators** — read `latestValue`; trusted only to apply their own staleness check.

Trust assumption on the staked asset: BEACON is a standard, non-rebasing, non-fee-on-transfer,
non-hook ERC-20. The reentrancy guards + CEI ordering hold even if this were violated, but the
accounting assumes 1 token in = 1 unit of assets.

## 3. State-transition rules

### 3.1 BeaconStaking (shares/assets vault, one pool per publisher)

- **`selfStake` / `delegate`** mint pool shares for assets at the current rate
  (`newShares = supply==0||assets==0 ? amount : amount*supply/assets`). Pulls BEACON via
  `safeTransferFrom`. Blocked when paused. `delegate` requires the pool to already exist.
- **`requestUnstake`** burns shares for `amount` assets *immediately*, moves the assets to the
  unbonding queue (still slashable), and starts a `UNBOND_PERIOD` cooldown. A second request
  re-bases the prior pending amount to the current haircut factor, then resets the cooldown on
  the whole pending amount. **Not** pausable — exits are always available.
- **`withdraw`** after cooldown returns `amount * scaleNow / scaleAtRequest` (net of slashes taken
  while unbonding) and clears the position. **Not** pausable.
- **`slash(publisher, bps)`** (owner or slasher, `0 < bps ≤ MAX_SLASH_BPS`) cuts active stake
  pro-rata (lower `poolStake`, shares unchanged) *and* unbonding stake (multiply `unbondScale`
  down). Slashed tokens go to `slashTreasury`. **Not** pausable.
- **Rewards** — `distributeRewards` (owner) pulls reward-token, takes publisher commission off the
  top, accrues the rest per-share (MasterChef accumulator), capped per `REWARD_EPOCH`. `claim`
  pays a staker's settled rewards. `_settle` runs before every share-balance change.

### 3.2 BeaconOracleV2 (per-round, per-feed)

- **`postFeed(id, value)`** — eligible publisher records/overwrites its value; a *new* publisher
  past `maxPublishersPerRound` is rejected ("round full"). `value > 0`.
- **`finalizeRound(id)`** — requires `freshCount ≥ minPublishers ∧ n > 0`. Computes the
  stake-weighted lower median (per-pool weight capped at `maxWeightBps` of round total), publishes
  it, then **clears the entire round before any external call** (CEI), then slashes fresh
  deviators (`|v−m|/m > maxDeviationBps`). `nonReentrant`.
- Stale submissions (older than `maxStaleness`, when non-zero) are excluded from both the median
  and slashing.

## 4. Invariants

Each invariant names how it is enforced. `[F]` = Foundry invariant test, `[U]` = Hardhat unit
test, `[C]` = guaranteed by construction/modifier.

### Staking solvency
- **S1 — Solvency.** `beacon.balanceOf(staking) ≥ Σ_pools (poolStake + totalUnbonding)` at all
  times. `[F invariant_solvent]`
- **S2 — No over-claim.** For each pool, `Σ_stakers stakeOf(p, s) ≤ poolStake(p)` (+dust from
  floor division). `[F invariant_noOverclaim]`
- **S3 — Share conservation.** `Σ_stakers sharesOf(p, s) == totalShares(p)` for every pool. `[C]`
  (only `_stake`/`requestUnstake` mint/burn, always updating both sides.)
- **S4 — Slash bound.** A single `slash` removes at most `MAX_SLASH_BPS` (5%) of active and of
  unbonding stake; it can never make `poolStake` or `totalUnbonding` negative. `[U][C require bps ≤ MAX_SLASH_BPS]`
- **S5 — Principal protection.** `rescueTokens` reverts for `beacon` and `rewardToken`; no owner
  path transfers staked principal or owed rewards out. `[U][C]`
- **S6 — Reward-token immutability.** `setRewardToken` succeeds at most once. `[U][C require rewardToken == 0]`
- **S7 — Reward solvency.** The contract holds at least the reward-token it owes,
  `rewardToken.balanceOf(staking) ≥ Σ_pools Σ_stakers pendingRewards`, up to bounded
  floor-division dust (≤1 wei per settle). `[F invariant_rewardSolvent + test_rewardSolvency_concrete]`

### Oracle integrity
- **O1 — Eligibility gate.** Only `isEligiblePublisher` accounts can `postFeed`. `[U][C]`
- **O2 — Quorum.** `finalizeRound` reverts unless `freshCount ≥ minPublishers ∧ n > 0`. `[U][C]`
- **O3 — Weight cap.** No single pool's weight exceeds `maxWeightBps` of the round total in the
  median; below 50% no pool alone reaches the median threshold (Finding 1). `[U]`
- **O4 — Sybil resistance.** Median influence tracks `poolStake`, not publisher count, so
  spinning up many minimally-staked publishers cannot move the rate. `[U]`
- **O5 — Deviation slashing.** Every fresh submission with `|v−m|/m > maxDeviationBps` is slashed
  exactly `deviationSlashBps`; submissions within tolerance and stale submissions are never
  slashed. `[U]`
- **O6 — CEI / reentrancy.** The round is fully cleared before any `staking.slash` call, and
  `finalizeRound` is `nonReentrant`. `[C]`
- **O7 — Slash-cap consistency.** `deviationSlashBps ≤ DEVIATION_SLASH_BPS_CAP == staking.MAX_SLASH_BPS`,
  so `finalizeRound` can never revert from an over-large slash. `[U][C]`

### Access control
- **A1.** Parameter setters are `onlyOwner`; `slash` is owner-or-slasher; ownership transfer is
  two-step. `[U][C]`

## 5. Parameters

| Parameter | Where | Default | Bound | Governable |
|-----------|-------|---------|-------|-----------|
| `MIN_PUBLISHER_STAKE` | Staking | 1000e18 | constant | no |
| `UNBOND_PERIOD` | Staking | 7 days | constant | no |
| `MAX_SLASH_BPS` | Staking | 500 (5%) | constant | no |
| `MAX_FEE_BPS` | Staking | 2000 (20%) | constant | no |
| `REWARD_EPOCH` | Staking | 7 days | constant | no |
| `slashTreasury` | Staking | owner | non-zero | yes |
| `slasher` | Staking | unset | any (0 = none) | yes |
| `rewardToken` | Staking | unset | non-zero, **set-once** | once |
| `maxRewardPerEpoch` | Staking | 0 (no cap) | — | yes |
| `publisherFeeBps` | Staking | 0 | ≤ MAX_FEE_BPS | publisher |
| `maxDeviationBps` | Oracle | 1000 (10%) | > 0 | yes |
| `deviationSlashBps` | Oracle | 500 (5%) | ≤ DEVIATION_SLASH_BPS_CAP (500) | yes |
| `minPublishers` | Oracle | 1 | > 0 | yes |
| `maxStaleness` | Oracle | 0 (off) | — | yes |
| `maxPublishersPerRound` | Oracle | 64 | > 0 | yes |
| `maxWeightBps` | Oracle | 5000 (50%) | 0 < bps ≤ 10000 | yes |

## 6. Known limitations (in scope for audit, accepted for testnet)

- **Single publisher today.** `minPublishers` defaults to 1 and the live feed is self-published,
  so O3/O4 are *latent* protections until ≥2 independent publishers stake. This is the central
  go-live gap, tracked as a recruitment task, not a code defect.
- **Owner is an EOA** until the multisig migration completes (`ownership-transfer-runbook.md`).
- **Rewards unfunded.** No reward-token is set on the live deployment; the reward paths are dormant.
- **Deviation slashing is symmetric and median-relative** — a coordinated majority could move the
  median and slash an honest minority. Mitigated by `maxWeightBps` + stake-weighting, not eliminated;
  economic, not cryptographic, security.

## 7. Test coverage map

- `onchain/test/*.test.js` (token, staking, slashing, rewards, oracle v2, consumer) — Hardhat
  unit + integration (`npx hardhat test`).
- `onchain/test/foundry/BeaconStaking.invariant.t.sol` — vault solvency, no-over-claim, and
  reward-solvency invariants + a deterministic reward companion (`forge test`), fuzzing
  stake/delegate/unstake/withdraw/slash/distribute/claim across 4 actors / 2 publishers.
- `.github/workflows/ci.yml` — runs Python, Hardhat+Foundry, and Slither on every push.
