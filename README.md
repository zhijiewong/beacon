# Beacon

> Working codename — name TBD.

**A neutral, capability-normalized price reference rate for LLM inference** — "the SOFR/Brent of AI
tokens." Beacon measures what AI inference *actually costs* across providers, normalized for capability
so the headline rate isn't just "prices fell again."

Phase 1 (current): a credible, transparent, **public** index — pure data + software, no crypto.
Later phases publish it on-chain as an economically-secured oracle and add a token that secures its
accuracy. See the full roadmap at `~/.claude/plans/i-am-brainstorm-to-majestic-coral.md`.

## Why Beacon is different
Plain price dashboards already exist (Artificial Analysis, Epoch AI, inferencepriceindex.com). Beacon's
distinction is **rules-based, reproducible, capability-normalized construction** designed to become a
*settlement-grade reference rate* — not a marketing comparison page.

## Status
- [x] `docs/methodology.md` — index methodology (v0.1 draft)
- [x] data collector — live OpenRouter prices → daily JSON snapshot (`beacon/collector.py`)
- [x] price normalization — $/Mtok, blended 3:1 (`beacon/pricing.py`)
- [x] index computation — iso-quality / spread / outlier guard (`beacon/index.py`)
- [x] join + tier report — prices ↔ capability (`beacon/analyze.py`)
- [x] test suite — 35 stdlib `unittest` tests, no dependencies
- [x] `data/benchmarks.csv` — 18 models calibrated on GPQA-Diamond (verified, sourced)
- [ ] `tiers.json` — formalize capability tier thresholds (provisional in `analyze.py`)
- [ ] Phase-1 acceptance test vs. Epoch/a16z curves (needs a time series of snapshots)

## Quickstart
```bash
python3 -m unittest discover -s tests -t .   # run tests (35, all green)
python3 -m beacon.collector                  # fetch live prices -> data/snapshots/<date>.json
python3 -m beacon.analyze                    # join + per-tier index report
```
No `pip install` needed — standard library only.

## Read first
- [`docs/methodology.md`](docs/methodology.md) — how every published number is constructed.
- [`data/README.md`](data/README.md) — what's real (prices) vs. scaffold (benchmarks).
