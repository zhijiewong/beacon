# Audit-firm outreach (cover email + shortlist)

> Send the cover email below with [`docs/audit-scope.md`](./audit-scope.md) attached (or linked).
> Nothing here has been sent — these are drafts for you. The scope doc pins the engagement to
> contract commit `a4ad688`.

---

## Cover email

**Subject:** Audit quote request — ~600 LoC oracle + staking (Solidity, Base), commit-pinned

Hi <firm / name>,

I'm looking for a security audit of **Beacon**, an on-chain economically-secured reference rate
(oracle) for AI-inference prices with a Pyth-style Oracle Integrity Staking layer. It's a small,
self-contained codebase and I'd like a quote (duration + cost) and your earliest availability.

The essentials:
- **Scope:** ~604 LoC core — `BeaconStaking.sol` (staking vault: shares/assets accounting,
  unbonding, capped slashing, stablecoin rewards) and `BeaconOracleV2.sol` (multi-publisher
  stake-weighted-median oracle with deviation auto-slash). ~75 LoC supporting (ERC-20, interface,
  reference consumer).
- **Stack:** Solidity 0.8.28, OpenZeppelin 5.6.1 only, Hardhat, 54 passing tests. No prior
  static-analysis/fuzz/formal pass — green-field.
- **Pinned commit:** `a4ad688`, public repo: https://github.com/zhijiewong/beacon
- **Full scope package:** attached (`docs/audit-scope.md`) — architecture, privileged roles, trust
  model, the specific areas I want scrutinized, and known issues from my own pre-audit review.

One specific question: a couple of my open issues are **mechanism / game-theory** (honest-majority
*by stake*; whether a single dominant staker can both set the rate and slash honest minority
publishers). **Do you cover economic/mechanism review, or code-level only?** If only code-level,
I'd appreciate a pointer to who you'd pair with for the mechanism side.

Context: this is testnet today and the audit is the gate before any mainnet/real value, so it's on
my critical path but not rushed. Happy to do a walkthrough call.

Thanks,
<your name>
<contact>

---

## Firm shortlist

> **Caveat (knowledge cutoff Jan 2026):** verify each firm's current offerings, availability, and
> that they still fit — this is a starting set, not an endorsement, and the space moves fast. For a
> solo/early budget, the audit *contest* platforms are often the most cost-effective first pass.

**Code + mechanism (best fit for the honest-majority-by-stake questions):**
- **Trail of Bits** — deep Solidity + can reason about protocol/economic design; thorough, premium.
- **Spearbit / Cantina** — reviewer marketplace; can assemble a team incl. mechanism-savvy auditors.
- **Certora** — formal verification; ideal for the vault-accounting *invariants* (Finding 7) — a
  strong complement to a manual audit rather than a replacement.

**Strong code-level Solidity (pair with a mechanism reviewer if needed):**
- **OpenZeppelin** — you already use their libs; solid DeFi/staking experience.
- **Zellic**, **ChainSecurity**, **Sigma Prime**, **Trust Security**, **Macro** — all reputable
  for DeFi/oracle/staking code.

**Economic / mechanism specialists (for Findings 1–2 specifically):**
- **Gauntlet**, **Chaos Labs** — economic-risk / mechanism modeling for staking & oracle systems.

**Budget-friendly first pass (solo-appropriate):**
- **Code4rena**, **Sherlock**, **Cantina** competitions — crowd-sourced audit contests; often the
  best value for a small codebase before (or instead of) a full private engagement. Sherlock also
  bundles coverage; Cantina spans both contest and private.

**Suggested play for a solo builder:** run a free **Slither** pass + add **Foundry invariant tests**
yourself first (cheap, catches the obvious), then a **contest** (Code4rena/Sherlock/Cantina) for
breadth at low cost, and reserve a **private firm** (Trail of Bits / Spearbit / Certora-for-invariants)
for the final pre-mainnet sign-off once publishers and real value are actually near.

## Process notes
- Quote against the **pinned commit** and freeze scope during the window (no feature changes).
- Ask for: severity-rated report + a **remediation re-review** pass + a public summary you can cite.
- Independent of the audit, do the **owner → multisig + timelock** migration (see
  [`docs/ownership-transfer-runbook.md`](./ownership-transfer-runbook.md)) — auditors will flag the
  single-key owner otherwise.
