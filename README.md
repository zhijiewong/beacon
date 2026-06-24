# Beacon

[![CI](https://github.com/zhijiewong/beacon/actions/workflows/ci.yml/badge.svg)](https://github.com/zhijiewong/beacon/actions/workflows/ci.yml)

> Working codename — name TBD.

**A neutral, capability-normalized reference rate for LLM inference — published on-chain as an
economically-secured oracle.** The "SOFR / Brent of AI tokens." Web2 dashboards tell a *human*
what AI costs; Beacon gives a *contract* a trustless price to settle against.

Beacon measures what a fixed unit of AI *intelligence* actually costs across providers —
normalized for capability so the headline rate isn't just "prices fell again" — and publishes
it on-chain where agents, x402 payments, and (later) inference derivatives can reference it.

> [!IMPORTANT]
> **Status: Base Sepolia testnet, unaudited, no token launch.** The on-chain pieces are live
> for demonstration and testing only. BEACON is a valueless test token, rewards are not funded,
> and a professional audit is the non-negotiable gate before any mainnet or real value.

## Why Beacon is different

Plain price dashboards already exist (Artificial Analysis, Epoch AI, inferencepriceindex.com).
Beacon's distinction is two things they structurally can't offer:

1. **Capability-normalized, rules-based construction** — not raw $/token (which only falls and
   isn't quality-comparable), but the cheapest credible price to reach a fixed capability tier,
   hedonic-indexed the way BLS does CPI for computers and Epoch does for LLMs.
2. **On-chain economic security** — the rate is an oracle secured by staking + slashing (Pyth
   Oracle Integrity Staking blueprint), so it's *settlement-grade*: a contract can trust it
   without trusting a publisher.

## What's live

**Phase 1 — the public index** (pure data + software, no crypto dependency):
- Capability-normalized index: frontier / strong / GPT-4-class tiers + cross-provider spread,
  from live OpenRouter prices joined to GPQA-Diamond capability scores.
- Reproduces published LLMflation curves on an acceptance test (validated vs. Epoch / a16z).
- **Live dashboard:** https://zhijiewong.github.io/beacon-index/ (refreshes daily, autonomously).
- 54 stdlib `unittest` tests, zero dependencies.

**Phase 2 — the on-chain oracle** (live on Base Sepolia, 51 Solidity tests):
- `BeaconOracleV2` — eligible publishers submit per round; a **stake-weighted median** is
  published and any submission deviating past tolerance is **auto-slashed**. Staleness window,
  governable thresholds.
- `BeaconStaking` — Pyth-OIS-style self-stake + delegation, capped slashing (incl. unbonding
  stake), stablecoin reward accumulator, two-step ownership, pause guard, token rescue.
- `BeaconToken` — fixed-supply ERC-20 (test token; distribution deferred).
- `BeaconConsumer` — reference integration: an external contract that reads the rate, rejects
  stale/missing values, and settles a sample quote against it.
- The autonomous daily collector publishes the index through oracle v2 (the same secured feed
  the consumer reads).

### Live addresses (Base Sepolia)

| Contract | Address |
|----------|---------|
| BEACON token | [`0x7848eAD4459C8334854B015C49F10dFb02B5dC83`](https://sepolia.basescan.org/address/0x7848eAD4459C8334854B015C49F10dFb02B5dC83) |
| BeaconStaking | [`0x23783C0F305dA38Ee57baE4fe507ea078Bd52602`](https://sepolia.basescan.org/address/0x23783C0F305dA38Ee57baE4fe507ea078Bd52602) |
| BeaconOracleV2 | [`0x7bA170f7e156cCCDeDcf5757233b0d65fF3C497C`](https://sepolia.basescan.org/address/0x7bA170f7e156cCCDeDcf5757233b0d65fF3C497C) |
| BeaconConsumer | [`0x60ED1326A7FCB132CFceD2C4f407cD30D8FE5ef7`](https://sepolia.basescan.org/address/0x60ED1326A7FCB132CFceD2C4f407cD30D8FE5ef7) |

The `onchain/*-deployed.json` records are the source of truth (addresses change on redeploy).

## Become a publisher

Beacon's median is only as real as its publisher set. Turning the self-demo into a genuine
multi-source feed needs **independent publishers** — and the bar is low: ~10 minutes to start.
See **[`docs/publisher-onboarding.md`](docs/publisher-onboarding.md)** for the runbook (fund →
self-stake → post the open-source index). Testnet, unaudited, nothing to earn yet — you'd be an
early publisher of record, not a yield farmer.

## Quickstart

```bash
# Phase 1 — the index (standard library only, no pip install)
python3 -m unittest discover -s tests -t .   # 54 tests, all green
python3 -m beacon.collector                  # fetch live prices -> data/snapshots/<date>.json
python3 -m beacon.analyze                    # join + per-tier index report
python3 -m beacon.feeds                       # shape the index into on-chain feeds (JSON)

# Phase 2 — the on-chain oracle (Base Sepolia)
cd onchain && npm install
npx hardhat test                              # 51 Solidity tests
cp .env.example .env                          # add a THROWAWAY testnet key (never real funds)
```

## Repo layout

| Path | What |
|------|------|
| `beacon/` | Phase-1 index pipeline (collect, normalize, compute, shape feeds) — stdlib only |
| `data/` | Real daily price snapshots + calibrated GPQA-Diamond benchmarks |
| `onchain/` | Hardhat project: token, staking, oracle v2, consumer + deploy/publish scripts |
| `web/` | Next.js + Tremor dashboard (static export → GitHub Pages) |
| `docs/` | [methodology](docs/methodology.md), [Phase-2 design + build log](docs/phase2-onchain-oracle-design.md), [publisher onboarding](docs/publisher-onboarding.md), [outreach](docs/publisher-outreach.md) |

## Read first

- [`docs/methodology.md`](docs/methodology.md) — how every published number is constructed.
- [`docs/phase2-onchain-oracle-design.md`](docs/phase2-onchain-oracle-design.md) — the on-chain
  design, security model, and §13 testnet build log.
- [`docs/spec.md`](docs/spec.md) — formal spec: invariants, trust model, state transitions, and
  the parameter table (the audit's reference document).
- [`data/README.md`](data/README.md) — what's real (prices) vs. scaffold (benchmarks).

## The honest framing

On-chain demand for an inference oracle is **latent today** — the derivatives don't exist yet
and agents mostly pay spot. This is a deliberate picks-and-shovels bet on a *forming* future
(agentic settlement + inference derivatives), which is why Phase 1 is built to stand on its own
as a credible public index meanwhile. Sequenced, not hyped: the token launches behind real
adoption, and real value waits on an audit.
