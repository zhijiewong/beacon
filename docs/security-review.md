# Beacon — internal security review (pre-audit)

> **Scope:** `onchain/contracts/BeaconStaking.sol`, `BeaconOracleV2.sol`, and their consumers,
> as of commit on `main`. **This is a self-review, not a professional audit** — it exists to
> surface issues early, document known/by-design risks, and shorten the paid audit. A
> professional audit remains the non-negotiable gate before any mainnet deployment or real value.
> Reviewer: project author (adversarial self-review). Testnet (Base Sepolia), unaudited.

Severity = impact × likelihood under the intended trust model (owner = trusted governance key;
BEACON + rewardToken = trusted standard ERC-20s set at deploy/governance time).

---

## Summary table

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Honest-majority-by-stake: >50% pool stake controls the rate **and** can slash honest minority | High (inherent) | By design — document + mitigate operationally |
| 2 | `minPublishers = 1` (current live config) ⇒ no real economic security; single publisher = trust | High (config) | Open — raise to ≥2 once independent publishers exist |
| 3 | Share-inflation / first-depositor vault attack | — | **Mitigated** (verified) |
| 4 | Changing `rewardToken` strands unclaimed rewards in the old token; old token then rescuable | Medium | Fix before mainnet |
| 5 | `finalizeRound` makes external `slash` calls before clearing round state | Low (non-exploitable w/ non-hook token) | Harden before mainnet (CEI / `nonReentrant`) |
| 6 | `finalizeRound` unbounded loop over publishers | Low | Add max-publishers cap before mainnet |
| 7 | Rounding dust in unbonding (`totalUnbonding` vs per-staker scale) | Low | Add invariant tests |
| 8 | Owner is a single highly-privileged key (slash, pause, params, distribute) | Informational | Multisig + timelock before mainnet |
| 9 | Slasher has no per-time rate limit (5%/call, repeatable) | Informational | Acceptable; document |

---

## Findings

### 1. Honest-majority-by-stake assumption (High, inherent to the design)
`BeaconOracleV2._aggregate` returns the **stake-weighted** median. A publisher controlling
> 50% of total pool stake on a feed *is* the median: cumulative weight crosses half at their
value (`2*cum >= total`). Two consequences:
- They unilaterally set the published rate.
- Their own submission can never be slashed (deviation from itself is 0), while honest minority
  publishers whose correct values now "deviate" from the manipulated median **get slashed** —
  the classic >50% oracle attack, here weaponized against dissenters.

This is the foundational Pyth-OIS trust assumption (security = honest majority *by stake*), not
a bug, but it must be stated loudly. **Mitigations (operational, pre-mainnet):**
- Recruit independent publishers with *comparable* stake — no single pool near 50%.
- Governance caps per-pool stake weight, or uses a trimmed/clamped aggregation, before real value.
- Until then, the rate is only as trustworthy as the dominant staker. See Finding 2.

### 2. `minPublishers = 1` gives no economic security today (High, configuration)
With the current live `minPublishers = 1`, a round finalizes on a **single** submission: the
"median" is that one value, and deviation slashing is vacuous (nothing to deviate from). The
live feed is therefore *single-publisher trust*, not an economically-secured median — which
matches reality (only the treasury publishes today). **This is the core "people problem":** the
security properties only switch on with ≥2 independent, comparably-staked publishers.
**Action:** raise `minPublishers` to ≥2 (ideally ≥3) the moment real publishers exist, and don't
market the feed as "secured" before then. The README/onboarding already carry the testnet caveat;
keep that honest.

### 3. Share-inflation / first-depositor attack — MITIGATED (verified)
The shares/assets vault (`_stake`) is the usual home of the ERC-4626 first-depositor /
donation-inflation attack. **It is not exploitable here**, for two structural reasons:
- **No donation path.** `poolStake` is internal accounting updated only by stake/unstake/slash —
  *not* `beacon.balanceOf(this)`. An attacker cannot inflate a pool's assets by transferring
  tokens in, so they cannot manipulate the share price out from under a victim depositor.
- **Asset/share ratio ≤ 1 always.** Pools mint 1:1 initially; slashing only *lowers* assets
  relative to shares. So `newShares = amount * supply / assets ≥ amount` and round-down can't
  zero out a normal deposit.

Verified by reading every writer of `poolStake`/`totalShares`. Recommend an explicit invariant
test (`poolStake ≤ totalShares` in asset terms; no-donation assertion) to lock this in.

### 4. Changing `rewardToken` strands unclaimed rewards (Medium) — fix before mainnet
`claimable[publisher][staker]` balances are denominated in whatever `rewardToken` was set when
`distributeRewards` ran. If governance calls `setRewardToken(B)` while users still hold unclaimed
rewards in token A:
- `claim` pays out in the *new* token B (wrong asset / may underpay or revert).
- `rescueTokens` no longer treats A as protected, so the owner could withdraw the A balance that
  backs those owed rewards.

Owner-trusted and testnet, so not urgent, but it's a real foot-gun. **Fix options:** forbid
changing `rewardToken` once set (simplest), or make rewards per-token (escrow the distributed
token and pin each `claimable` to its token). Add a test asserting owed rewards survive a token change.

### 5. `finalizeRound` external calls before clearing state (Low) — harden before mainnet
`finalizeRound` calls `staking.slash(...)` (which does `beacon.safeTransfer`) inside the slashing
loop, *before* the round is cleared (clearing happens after). Standard checks-effects-interactions
would clear first. **Not exploitable today:** BEACON is a plain OZ ERC-20 with no transfer hook,
`staking`/`beacon` are immutable trusted contracts, and `slashTreasury` is governance-set — so no
reentrant callback exists. Still, defense-in-depth before mainnet: add `nonReentrant` to
`finalizeRound` (and/or snapshot submissions → clear round → then slash), so the contract stays
safe even if the staked token is ever swapped for a hook-bearing one.

### 6. Unbounded `finalizeRound` loop (Low)
`feedPublishers[id]` grows with each unique publisher and `finalizeRound` loops it twice. Gas
griefing is bounded by the **1000-BEACON eligibility cost per publisher** (`postFeed` requires
`isEligiblePublisher`), so spamming distinct publishers is economically expensive. Still, add a
`MAX_PUBLISHERS_PER_ROUND` cap (reject `postFeed` beyond it) before mainnet to bound finalize gas
deterministically.

### 7. Rounding dust in unbonding accounting (Low)
`totalUnbonding[publisher]` is decremented by the *scaled* `net` on `withdraw` and by `pendingCut`
on `slash`, while each position's payout is recomputed from the shared `unbondScale`. With multiple
unbonding stakers and integer division, `totalUnbonding` can drift by wei-level dust, which a later
slash would scale into a negligibly-wrong `pendingCut` (bounded, clamped to 0 on withdraw, can't
underflow). No meaningful loss, but add an invariant/fuzz test:
`sum(per-staker net) ≤ totalUnbonding` and contract BEACON balance ≥ `Σ poolStake + Σ unbonding`.

### 8. Owner is a single highly-privileged key (Informational)
The owner can `slash` any pool (≤5%), `pause`, set the slasher, set reward params, and
`distributeRewards`. `Ownable2Step` prevents fat-finger transfer, and `pause` is correctly scoped
(never traps exits, never disables slashing). But it's one key. **Before mainnet:** move ownership
to a multisig + timelock; consider splitting the `slasher` (operational) from the `owner`
(governance) roles, which the code already supports (`setSlasher`).

### 9. Slasher rate limit (Informational)
`slash` caps each call at `MAX_SLASH_BPS` (5%) but has no per-time limit, so a compromised
owner/slasher could slash repeatedly. The oracle slashes at most once per `finalizeRound` per
publisher, so under normal operation this is bounded. Acceptable for now; revisit alongside the
multisig (Finding 8). The cap matching `DEVIATION_SLASH_BPS_CAP` correctly guarantees
`staking.slash` can never revert from an over-large oracle slash — good.

---

## Positive assurances (things checked and found sound)
- **No reentrancy on the value-moving paths:** `_stake`, `withdraw`, `claim` are `nonReentrant`;
  `requestUnstake` makes no external call.
- **Reward accumulator can't underflow:** `_settle` runs before every share change and resets
  `rewardDebt`; `accRewardPerShare` is monotonic; slashing leaves reward accounting untouched, so
  `accrued ≥ rewardDebt` always holds.
- **Slash solvency:** `cut = activeCut + pendingCut` are both floor-divided, so `cut ≤ active +
  pending`, and the contract holds ≥ that in BEACON; the transfer to treasury can't over-draw.
- **Unbonding stake stays slashable** through the cooldown (closes the unstake-to-dodge-slash gap).
- **`rescueTokens`** hard-protects BEACON and the current reward token (subject to Finding 4).
- **Eligibility is live-checked** at `postFeed`, so a pool slashed below the minimum can't keep posting.
- **51 Solidity tests pass**, covering slashing (incl. unbonding + split), rewards, staleness,
  stake-weighting, two-step ownership, pause, and rescue.

## Pre-mainnet checklist (blocking)
- [ ] **Professional third-party audit** (non-negotiable).
- [ ] Raise `minPublishers` ≥ 2 (≥3 preferred) with independent, comparably-staked publishers (Finding 2).
- [ ] Per-pool stake-weight cap or trimmed aggregation so no pool approaches 50% (Finding 1).
- [ ] Resolve `rewardToken`-change handling (Finding 4).
- [ ] `nonReentrant`/CEI on `finalizeRound` (Finding 5) + `MAX_PUBLISHERS_PER_ROUND` (Finding 6).
- [ ] Ownership → multisig + timelock; split slasher/owner roles (Finding 8).
- [ ] Add invariant/fuzz tests for share ratio, unbonding accounting, and reward solvency (3, 7).
