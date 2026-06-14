# Beacon — smart-contract audit scope package

> Prepared for prospective audit firms to scope and quote an engagement. Beacon is an
> on-chain, economically-secured reference rate (oracle) for LLM-inference prices, with a
> Pyth-style Oracle Integrity Staking layer. **Currently Base Sepolia testnet, unaudited —
> this audit is the gate before any mainnet deployment or real value.**

## 1. At a glance

| | |
|---|---|
| **Audit target commit** | `a4ad688` (branch `main`) — pin the engagement to this SHA |
| **Repo** | https://github.com/zhijiewong/beacon (public) |
| **Language / compiler** | Solidity `0.8.28`, `evmVersion: cancun` |
| **Framework** | Hardhat |
| **Dependencies** | OpenZeppelin Contracts `5.6.1` (Ownable2Step, ReentrancyGuard, Pausable, SafeERC20, ERC20, ERC20Permit) — no other third-party libs |
| **Target chain** | Base (L2, OP-stack). Live on Base Sepolia; mainnet = Base |
| **Tests** | 54 passing (Hardhat/Chai), `onchain/test/` |
| **Prior review** | Internal pre-audit self-review: [`docs/security-review.md`](./security-review.md) |
| **Existing tooling run** | Unit tests only. No prior Slither/Foundry-fuzz/formal pass — green-field for the firm |

## 2. Scope

### In scope (core — primary risk)
| File | LoC | What it is |
|------|-----|-----------|
| `contracts/BeaconStaking.sol` | 347 | OIS staking vault: self-stake/delegate, shares/assets accounting, unbonding, capped slashing (active + unbonding), MasterChef-style stablecoin rewards, pause, rescue |
| `contracts/BeaconOracleV2.sol` | 257 | Multi-publisher round oracle: stake-weighted median aggregation, deviation auto-slash, staleness window, publisher cap |

These two contracts (~604 LoC) hold all the economic logic and are where audit effort should concentrate.

### In scope (supporting — low complexity)
| File | LoC | What it is |
|------|-----|-----------|
| `contracts/BeaconToken.sol` | 22 | Fixed-supply ERC-20 + ERC20Permit (thin OZ wrapper) |
| `contracts/IBeaconOracle.sol` | 14 | Read interface integrators depend on |
| `contracts/examples/BeaconConsumer.sol` | 39 | Reference integration (reads rate, staleness-guards, settles a quote). Example, not protocol infra — review for "is this safe guidance to publish?" |

### Out of scope
- `contracts/mocks/MockERC20.sol` (test-only).
- `contracts/BeaconOracle.sol` (v1, 63 LoC) — legacy single-publisher oracle, superseded by V2. Can be included on request, but it is being retired.
- Off-chain Python index pipeline (`beacon/`) and the Next.js dashboard (`web/`) — not on-chain, but the **data-integrity trust boundary** between them and the oracle is in scope conceptually (see §5).
- Deployment/publish scripts (`onchain/scripts/`) — review optional.

## 3. Architecture (how value flows)

```
publishers/delegators ──stake BEACON──▶ BeaconStaking (shares/assets vault, per publisher)
                                              │ isEligiblePublisher / poolStake / slash
                                              ▼
off-chain index ──postFeed(value)──▶ BeaconOracleV2 ──finalizeRound──▶ stake-weighted median
                                              │                          + auto-slash deviators
                                              ▼
                                       latestValue(id) ──read──▶ BeaconConsumer / integrators
```

- Each publisher's pool is an **ERC-4626-style shares/assets vault** so a slash is O(1): lower
  pool assets → every staker cut pro-rata, no iteration. Pool assets are **internal accounting**
  (`poolStake`), deliberately *not* `balanceOf` (blocks donation/inflation attacks).
- `finalizeRound` is permissionless but quorum-gated; it aggregates by **stake-weighted lower
  median**, publishes, and calls `BeaconStaking.slash` on fresh deviators (CEI-ordered, `nonReentrant`).
- Slashing cuts **active stake** (via shares) **and unbonding stake** (via a multiplicative
  `unbondScale` haircut factor) so a publisher can't dodge a slash by unstaking first.
- Rewards are a separate stablecoin (e.g. USDC), MasterChef per-share accumulator, capped per epoch,
  independent of slashing.

## 4. Privileged roles & trust model

| Role | Powers | Current holder (testnet) |
|------|--------|--------------------------|
| `owner` (Ownable2Step) | `slash` (≤5%), `pause`/`unpause`, `setSlasher`, `setRewardToken` (once), `setMaxRewardPerEpoch`, `setSlashTreasury`, `distributeRewards`, `rescueTokens`; on oracle: all `set*` params | single EOA (treasury) |
| `slasher` | `slash` (≤5%) — intended to be the oracle | BeaconOracleV2 |
| publisher | `postFeed` (if eligible), `setPublisherFee` | open (stake ≥ 1000 BEACON) |
| anyone | `finalizeRound` (quorum-gated), `delegate`, `requestUnstake`, `withdraw`, `claim` | — |

**Trust assumptions to validate against:** `owner` is trusted governance (pre-mainnet: migrate to
multisig + timelock — flagged, not yet done). `beacon` and `rewardToken` are trusted standard
ERC-20s (no transfer hooks/fee-on-transfer/rebasing). Oracle security rests on **honest-majority
*by stake*** among publishers.

## 5. What we most want the audit to scrutinize

1. **Shares/assets accounting** in `BeaconStaking` across stake → slash → unbond → withdraw
   interleavings: rounding direction, dust, and the `unbondScale` haircut math (does
   `totalUnbonding` stay consistent; can any staker withdraw more/less than owed; can slashing ever
   pull from another pool's principal?).
2. **Reward accounting** (MasterChef accumulator): can `_settle` under/over-credit across
   stake-change + slash + distribute orderings? Dust trapping? Epoch-cap edge cases?
3. **Stake-weighted median** (`_aggregate`): manipulation by a >50%-stake publisher (sets the rate
   *and* slashes honest minority — known, see §6), low-stake/sybil resistance, lower-median
   correctness, and behavior when `poolStake` is 0.
4. **Deviation slashing** in `finalizeRound`: CEI/reentrancy (now guarded), the cap vs staking's
   `MAX_SLASH_BPS` (so `slash` can't revert), and griefing via the publisher loop.
5. **The off-chain→on-chain trust boundary** (§2 out-of-scope note): `postFeed` accepts any value
   from an eligible publisher; is the median + slashing economically sufficient given the threat model?
6. **Privileged-role abuse / rug surface**: `rescueTokens` protections, `pause` scoping (must never
   trap exits or disable slashing), reward-token handling, owner powers.

## 6. Known issues (already identified — please confirm/expand, don't just re-report)

From the internal self-review ([`docs/security-review.md`](./security-review.md)):
- **Resolved + deployed:** share-inflation/first-depositor attack (mitigated by internal accounting,
  regression-tested); `setRewardToken` set-once (Finding 4); `finalizeRound` CEI + `nonReentrant`
  (Finding 5); `maxPublishersPerRound` cap (Finding 6).
- **Open / by-design (want auditor's view on severity + mitigation):** honest-majority-by-stake — a
  >50% pool can set the rate and slash the honest minority (Finding 1); `minPublishers = 1` gives no
  real economic security until ≥2 independent comparably-staked publishers exist (Finding 2);
  single-key owner pre-multisig (Finding 8); unbonding-accounting rounding dust (Finding 7).

We're explicitly interested in whether the firm considers Findings 1/2 acceptable for a launch with
operational mitigations (stake-weight caps, publisher vetting) or contract-level blockers.

## 7. Logistics

- **Deliverable wanted:** standard report (severity-rated findings + remediation), a remediation
  re-review pass, and a public summary we can cite for the rate's credibility.
- **Engagement size estimate:** ~600 LoC core, modest complexity, well-documented + 54 tests — we
  expect a small-to-medium engagement; please quote duration + cost against commit `a4ad688`.
- **Access:** public repo; we can walk through the design doc
  ([`docs/phase2-onchain-oracle-design.md`](./phase2-onchain-oracle-design.md)) and methodology on a call.
- **Timeline:** flexible; mainnet is gated on this audit, so it's on the critical path but not rushed.
- **Open question for the firm:** do you also offer economic/mechanism review (the OIS staking
  game-theory), or only code-level? Findings 1–2 are as much mechanism as code.

## 8. Pre-audit checklist we'd run first (firm may advise)
- [ ] Slither / static analysis pass (none run yet).
- [ ] Foundry invariant/fuzz suite for the staking vault accounting (Finding 7).
- [ ] Freeze scope at a tagged release; no feature changes during the audit window.
- [ ] Decide multisig + timelock for `owner` before mainnet (independent of audit).
