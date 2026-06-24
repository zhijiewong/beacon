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
| 1 | Honest-majority-by-stake: >50% pool stake controls the rate **and** can slash honest minority | High (inherent) | **Mitigation lever added** — governable `maxWeightBps` per-pool weight cap (in source) |
| 2 | `minPublishers = 1` (current live config) ⇒ no real economic security; single publisher = trust | High (config) | Open — raise to ≥2 once independent publishers exist |
| 3 | Share-inflation / first-depositor vault attack | — | **Mitigated** (verified + regression test) |
| 4 | Changing `rewardToken` strands unclaimed rewards in the old token; old token then rescuable | Medium | **Fixed in source** (set-once) — redeploy pending |
| 5 | `finalizeRound` makes external `slash` calls before clearing round state | Low (non-exploitable w/ non-hook token) | **Fixed + deployed** (CEI + `nonReentrant`) |
| 6 | `finalizeRound` unbounded loop over publishers | Low | **Fixed in source** (`maxPublishersPerRound` cap) — redeploy pending |
| 7 | Rounding dust in unbonding (`totalUnbonding` vs per-staker scale) + reward accounting | Low | **Addressed** — Foundry invariants bound the dust (≤1 wei/settle, never material under-collateralization) |
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
a bug, but it must be stated loudly. **Mitigation lever added (in source):** `BeaconOracleV2`
now has a governable **`maxWeightBps`** — each pool's weight in the stake-weighted median is
capped at that fraction of the round's total stake. It defaults to **5000 (50%)**, which is a
no-op for normal rounds but caps a true super-majority; governance should **tighten it (e.g.
4000)** once ≥3 independent publishers exist, at which point no single pool's weight reaches half
the total and it can no longer dictate the rate (regression-tested: a 60%-stake pool stops
determining the median once the cap is set to 40%). Remaining operational mitigations:
- Recruit independent publishers with *comparable* stake — no single pool near 50%.
- Until publishers + a tightened cap exist, the rate is only as trustworthy as the dominant
  staker. See Finding 2.

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

> **Resolution note:** Findings 3, 4, 5, and 6 are addressed in source with tests (54 Solidity
> tests green) **and shipped live** in a coordinated hardening redeploy on Base Sepolia
> (2026-06-14): BeaconStaking `0x23783C0F305dA38Ee57baE4fe507ea078Bd52602`, BeaconOracleV2
> `0x7bA170f7e156cCCDeDcf5757233b0d65fF3C497C` (re-wired as slasher), BeaconConsumer
> `0x60ED1326A7FCB132CFceD2C4f407cD30D8FE5ef7` (re-verified reading the live rate). The
> `onchain/*-deployed.json` records are the source of truth.

### 4. Changing `rewardToken` strands unclaimed rewards (Medium) — FIXED IN SOURCE (set-once)
`claimable[publisher][staker]` balances are denominated in whatever `rewardToken` was set when
`distributeRewards` ran. If governance calls `setRewardToken(B)` while users still hold unclaimed
rewards in token A:
- `claim` pays out in the *new* token B (wrong asset / may underpay or revert).
- `rescueTokens` no longer treats A as protected, so the owner could withdraw the A balance that
  backs those owed rewards.

Owner-trusted and testnet, so not urgent, but it's a real foot-gun. **Fix applied:**
`setRewardToken` now reverts with `"already set"` if the reward token is non-zero — it's settable
once and then frozen, so it can never be repointed out from under owed rewards. Regression test:
*"freezes the reward token after it is first set."*

### 5. `finalizeRound` external calls before clearing state (Low) — FIXED + DEPLOYED
`finalizeRound` previously called `staking.slash(...)` inside the slashing loop *before* the round
was cleared. **Not exploitable today** (BEACON is a plain OZ ERC-20 with no transfer hook;
`staking`/`beacon` are immutable; `slashTreasury` is governance-set), but fixed for defense in
depth. **Fix applied + deployed:** `finalizeRound` now snapshots deviators into memory, fully
clears the round (effects), and only then calls `staking.slash` (interactions) — strict
checks-effects-interactions — and the function is `nonReentrant`. Verified by the existing slash +
round-clearing tests staying green after the refactor.

### 6. Unbounded `finalizeRound` loop (Low) — FIXED IN SOURCE (publisher cap)
`feedPublishers[id]` grows with each unique publisher and `finalizeRound` loops it twice. Gas
griefing was already bounded by the **1000-BEACON eligibility cost per publisher** (`postFeed`
requires `isEligiblePublisher`), so spamming distinct publishers is economically expensive.
**Fix applied:** added a governable `maxPublishersPerRound` (default 64); `postFeed` rejects a
*new* publisher past the cap (`"round full"`) while existing submitters can still overwrite.
Finalize gas is now deterministically bounded. Regression test: *"caps the number of distinct
publishers in a round."*

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

## Static analysis (Slither 0.11.5)

Ran `slither . --filter-paths "node_modules|test/|mocks/"` against the core contracts. Triage of
every result (all reviewed; one fixed, the rest intentional/bounded):

| Detector | Where | Verdict |
|----------|-------|---------|
| `missing-inheritance` | `BeaconOracleV2` should implement `IBeaconOracle` | **Fixed** — `BeaconOracleV2 is …, IBeaconOracle` with `latestValue` marked `override`, so the consumer-facing signature is now compiler-enforced. (Still flags retired v1 `BeaconOracle` — out of scope.) |
| `missing-zero-check` | `setSlasher(slasher_)` | **Intentional** — `address(0)` deliberately *disables* the automated slasher (owner can still slash); documented in NatSpec. |
| `calls-loop` | `_aggregate` → `staking.poolStake(p)`; `finalizeRound` → `staking.slash(p)` | **Bounded / acceptable** — both loops are capped by `maxPublishersPerRound` (Finding 6); `_aggregate` is a view; `slash` can't revert in-loop (deviators are eligible publishers with `poolStake ≥ MIN > 0`, and the slash bps is hard-capped at staking's max). |
| `timestamp` | staleness / unbond cooldown / reward epoch / consumer `maxAge` | **Acceptable** — all windows are hours-to-days; sub-second sequencer timestamp drift on an L2 can't meaningfully game them. |

No high/medium issues. Re-run Slither after any contract change before the audit.

## Pre-mainnet checklist (blocking)
- [ ] **Professional third-party audit** (non-negotiable).
- [ ] Raise `minPublishers` ≥ 2 (≥3 preferred) with independent, comparably-staked publishers (Finding 2).
- [x] Per-pool stake-weight cap (`maxWeightBps`) added (Finding 1) — in source; tighten to <50% once ≥3 publishers exist.
- [x] Resolve `rewardToken`-change handling (Finding 4) — set-once, deployed.
- [x] `nonReentrant`/CEI on `finalizeRound` (Finding 5) — deployed.
- [x] `maxPublishersPerRound` cap (Finding 6) — deployed.
- [x] **Coordinated hardening redeploy** done on Base Sepolia (Findings 4/5/6 live; slasher
      re-wired; consumer redeployed + re-verified).
- [ ] Ownership → multisig + timelock; split slasher/owner roles (Finding 8).
- [x] Foundry invariant/fuzz suite for the staking vault — **solvency**, **no-over-claim**, and
      **reward-solvency** (held reward-token ≥ Σ pending, up to ≤1 wei/settle floor dust) hold
      across 8,192 randomized stake/unstake/withdraw/slash/distribute/claim calls
      (`onchain/test/foundry/`), plus a deterministic reward companion test.
- [x] Static analysis (Slither) pass — triaged; 1 fixed (interface inheritance), rest intentional/bounded (see above).
