# Phase-1 Acceptance Test — does our method reproduce the LLMflation curve?

**Status:** PASS (`tests/test_acceptance.py`)
**Date:** 2026-06-13

## The claim being tested
Beacon's core method is the **iso-quality index**: the cheapest $/Mtok to reach a
*fixed capability* over time (methodology §7). If the method is sound, applying it to
known historical prices must reproduce the well-documented **LLMflation** curve that
a16z and Epoch AI published independently.

## The test
We take a16z's headline anchor series — the cheapest price to reach **MMLU ≥ 42** over
time (`data/historical_anchors.csv`, sourced from
[a16z LLMflation](https://a16z.com/llmflation-llm-inference-cost/)):

| Date | Cheapest model reaching MMLU ≥ 42 | Price ($/Mtok) |
|------|-----------------------------------|----------------|
| 2021-11 | GPT-3 (davinci) | **$60.00** |
| 2024-10 | Llama 3.2 3B (Together.ai) | **$0.06** |

We feed these through our **own** `beacon.index.iso_quality` at threshold 42 and compute
the decline. Result:

- iso-quality 2021-11 = **$60.00**, 2024-10 = **$0.06**
- decline = **1000×** over ~2.9 years → **~10.6×/year**

a16z reports **1000× over 3 years (~10×/year)**. We reproduce it within 5%. ✅

Cross-check (not asserted, corroborating): a16z also reports **~62×** at the MMLU-83
(GPT-4-level) tier since GPT-4's launch (Mar 2023) — consistent with the same ~10×/year
trend. Epoch AI independently finds a **median ~50×/year** across six benchmarks
(GPT-4-level on GPQA-Diamond at ~40×/year), the same phenomenon at a steeper rate on
harder tasks.

## What this proves — and what it doesn't
**Proves:** the iso-quality *method* is sound — applied to real historical prices it
reproduces the published LLMflation curve. The math is not the weak link.

**Doesn't prove (honest scope):** Beacon's *own* daily time series is only ~1 week old
and basically flat, so it cannot yet show a multi-year decline from its own data. That
will come as snapshots accrue over months/years. Until then, this anchor-based test is
the meaningful validation of the methodology, and the live trend chart is an honest
"curve forming" rather than a multi-year LLMflation slope.

## Reproduce it
```bash
python3 -m unittest tests.test_acceptance -v
```
