# Beacon Inference Rate — Index Methodology

**Version:** 0.1 (DRAFT)
**Status:** Phase 1 working draft — open for review
**Last updated:** 2026-06-07
**Codename:** "Beacon" (name is a placeholder)

> This document specifies how the Beacon inference price indices are constructed. It is the
> reference-rate credibility artifact: the index is only as trustworthy as this methodology is
> transparent, rules-based, and reproducible. Every number Beacon publishes must be derivable by a
> third party from this document plus the published input data. (Lesson borrowed directly from how
> SOFR earned its standing — rules-based construction over a transparent data base.)

---

## 1. Purpose & scope

**Purpose.** Provide a neutral, transparent, capability-normalized measure of *what LLM inference
actually costs* across providers over time — a reference rate, not a marketing dashboard.

**In scope (Phase 1).**
- Hosted, commercially-available **text LLM inference** priced per token via public APIs.
- Both **first-party** APIs (OpenAI, Anthropic, Google, xAI, DeepSeek, Mistral, …) and **third-party
  hosts** of open-weight models (OpenRouter, Together, Fireworks, …).

**Out of scope (Phase 1).**
- GPU/hardware rental rates and DRAM (covered by CME/Silicon Data, ICE/Ornn — explicitly *not* us).
- Training cost, fine-tuning, batch/cached-pricing tiers, image/audio/video modalities, embeddings.
- On-chain publication, tokenomics, and derivatives — those are Phase 2 / Phase 3 (see roadmap spec).

**Non-goals.** Beacon does not rank "best" models, does not give buying advice, and does not predict
prices. It measures.

---

## 2. Design principles

1. **Rules-based.** Every value follows from fixed rules in this document; no discretionary overrides.
2. **Reproducible.** Inputs (raw price snapshots, benchmark scores) are published; computation is
   open-source. Anyone can recompute and get the same number.
3. **Capability-normalized.** We never headline raw "$/million tokens" (it only falls and conflates
   quality). We measure the price of a *fixed unit of capability*.
4. **Manipulation-resistant.** Median-based aggregation, minimum-source requirements, outlier
   trimming, and published provenance. (Phase-1 inputs are *quoted* list prices — a known
   limitation; transaction-grounding is a Phase 2/3 problem, see §11.)
5. **Neutral & versioned.** No provider is favored. Methodology changes go through documented version
   control (§10); historical values are never silently restated.

---

## 3. Definitions

| Term | Definition |
|------|-----------|
| **Token** | One LLM input or output token as billed by the provider's public API. |
| **Provider** | An entity that sells inference for a model via a public, per-token-priced API. |
| **Model** | A specific named model version (e.g., `claude-opus-4-8`, `gpt-x`, `deepseek-v…`). |
| **Listing** | A (provider, model) pair with a published input price and output price. |
| **Blended price** | A single $/1M-token figure combining input and output prices (§5.2). |
| **Capability** | A model's measured score on a defined public benchmark (§6). |
| **Tier** | A fixed capability threshold the index is anchored to (e.g., "GPT-4-class"). |
| **Iso-quality index** | The cheapest blended price to *achieve a fixed capability tier* over time. |
| **Spread** | The dispersion of blended prices among listings that meet the *same* tier. |
| **Snapshot** | A timestamped record of all observed listings + benchmark scores for a date. |

---

## 4. Data sources & collection

### 4.1 Price data
- **First-party API price pages / pricing endpoints** — authoritative for each provider's own models.
- **Third-party hosts** (OpenRouter, Together, Fireworks, etc.) — for open-weight models and as
  cross-checks.
- **Historical backfill:** Artificial Analysis price history and Internet Archive (Wayback) snapshots
  of provider pricing pages, to extend the series backward.

For each listing we record: `provider, model, input_usd_per_mtok, output_usd_per_mtok,
context_window, observed_at (UTC), source_url, source_type {first_party | host | archive}`.

### 4.2 Capability data
- Public benchmark leaderboards and provider/Epoch/Artificial Analysis reported scores for:
  **GPQA-Diamond** (knowledge/reasoning), **AIME 2024–2025** (math), **SWE-bench Verified** (coding),
  **MMLU** (general; retained for long-run historical comparability).
- For each model we record the score, the benchmark version, and the source.

### 4.3 Cadence
- **Daily** snapshot of all listings and any benchmark updates (UTC date stamp).
- Prices change irregularly; benchmark scores change rarely. Daily cadence captures both without
  implying more precision than exists.

### 4.4 Inclusion rules (a listing enters the index only if)
1. It is a **public, per-token** text-inference price (no "contact sales", no committed-spend tiers).
2. Both input and output prices are available (or the provider bills a single blended rate).
3. The model has **at least one** qualifying benchmark score (§6) — else it can appear in raw price
   data but cannot enter a capability tier.
4. The listing has a verifiable `source_url`.

---

## 5. Price normalization

### 5.1 Units & currency
All prices are normalized to **USD per 1,000,000 tokens** (`$/Mtok`). Non-USD prices are converted at
the daily reference FX rate recorded in the snapshot.

### 5.2 Blended price (input:output)
Following the Epoch AI convention, the blended price weights input and output **3:1** (reflecting that
typical workloads consume ~3× more input than output tokens):

```
blended_price = (3 × input_usd_per_mtok + 1 × output_usd_per_mtok) / 4
```

- The 3:1 weight is a **published, fixed parameter** (`W_io = 3:1`) and is governance-controlled (§10).
- If a provider bills a single rate (no input/output split), that rate is used directly as the blended
  price and flagged `single_rate = true`.
- Cached-input, batch, and discounted tiers are **excluded** from the headline series (they may be
  tracked as separate, clearly-labeled experimental series later).

---

## 6. Capability measurement

A model's capability is a **vector** of benchmark scores, not a single number. For v1 the benchmark
set `B` is:

| Domain | Benchmark | Why |
|--------|-----------|-----|
| Knowledge/reasoning | GPQA-Diamond | Hard, frontier-discriminating, widely reported |
| Math | AIME 2024–2025 | Reasoning depth, low saturation |
| Coding | SWE-bench Verified | Real-world agentic coding, economically meaningful |
| General (legacy) | MMLU | Long history → enables multi-year iso-quality curves |

**Tier qualification.** A tier `T` is defined by a **threshold vector** over a chosen primary
benchmark (and optional secondary gates). A listing's model *qualifies for tier T* if its score on the
tier's primary benchmark ≥ the tier threshold (and meets any secondary gates). Example tiers:

| Tier name | Primary gate (illustrative — finalized in v1 calibration) |
|-----------|-----------------------------------------------------------|
| `Frontier` | Top decile of currently-available models on the primary benchmark |
| `GPT-4-class` | GPQA-D ≥ X₁ (and MMLU ≥ Y₁ for back-compat) |
| `GPT-3.5-class` | MMLU ≥ Y₂ |

> Exact thresholds are deliberately **not hard-coded here**; they are set in a separate, versioned
> `tiers.yaml` during v1 calibration and changed only via the §10 process. This keeps the *method*
> stable while allowing the *calibration* to be transparent and auditable.

---

## 7. Index construction

Beacon publishes **three families** of indices, not one number. This is the core of the
capability-normalization that makes the rate stable and meaningful.

### 7.1 Iso-quality index (the LLMflation curve)
For a fixed tier `T` at date `t`:

```
IsoQ(T, t) = min { blended_price(listing, t) : listing qualifies for tier T at t }
```

Published as an index normalized to a base date `t₀`:

```
IsoQ_index(T, t) = 100 × IsoQ(T, t) / IsoQ(T, t₀)
```

Interpretation: "the cheapest way to buy tier-T capability, indexed to 100 at the base date." These are
the curves that fall 10–50×/yr — published per tier so the decline is legible, not hidden.

**Robustness:** `IsoQ` uses the **minimum** by definition, which is sensitive to a single spurious
cheap listing. To resist that, the index uses an **outlier-guarded minimum**: while the cheapest
qualifying price is more than 50% below the *next*-cheapest, it is quarantined (logged publicly for
manual verification) and the next price becomes the candidate; the minimum of what survives sets the
index. Implemented as `beacon.index.robust_min_price`. See §8.3.

### 7.2 Frontier index
`IsoQ` applied to the `Frontier` tier. Tracks the price of *staying at the frontier*, which (per the
research) falls far more slowly than iso-quality curves — the closest thing to a stable "price level."

### 7.3 Cross-provider spread index (the genuinely volatile, tradeable signal)
For a fixed tier `T` at date `t`, over the set `S(T,t)` of qualifying listings:

```
Spread(T, t) = P90( blended_price ∈ S ) / P10( blended_price ∈ S )
```

A ratio ≥ 1 measuring how much providers disagree on the price of the *same* capability. Unlike the
iso-quality level, the spread does **not** trend monotonically to zero, so it is the most natural
basis for a future hedgeable/settable instrument (Phase 3). Requires `|S(T,t)| ≥ N_min` (default
`N_min = 5`) to be published; otherwise marked `insufficient_breadth`.

### 7.4 Headline composite (optional, clearly labeled)
A single "Beacon Inference Rate (BIR)" may be published as a fixed-weight basket across a defined set of
tiers, with weights published in `tiers.yaml`. It is explicitly a **convenience aggregate**, secondary
to the per-tier series, and never used to obscure the underlying components.

### 7.5 Secondary validation: hedonic regression
As an independent cross-check (not the headline method), fit a hedonic model on each snapshot:

```
log(blended_price) = α + Σ_b β_b · score_b + γ · t  + ε
```

over benchmarks `b ∈ B` with time `t`. The time coefficient `γ` is a quality-adjusted price-change
estimate that should broadly agree with the iso-quality curves. Divergence between the two methods is a
flag to investigate, and is reported, not suppressed. (This mirrors how statistical agencies use
hedonic regression for quality adjustment in the CPI.)

---

## 8. Data-quality & manipulation-resistance rules

1. **Minimum sources.** A tier index publishes only when ≥ `N_min` (default 5) qualifying listings
   exist; otherwise it is marked `insufficient_breadth`.
2. **Median-first aggregation.** Wherever a representative price is needed, use the median; the
   minimum (for `IsoQ`) is guarded per §7.1.
3. **Outlier handling.** Any blended price > 50% below the next-cheapest qualifying listing is
   quarantined for manual verification before it can move an index; the event is logged publicly with
   the source URL.
4. **Provenance required.** Every input row carries a `source_url` and `source_type`; rows without
   provenance are excluded.
5. **No silent backfill.** Archive-sourced historical points are flagged `source_type = archive` and
   visibly distinguished from live data.
6. **Known limitation — quoted vs. transacted.** Phase-1 inputs are *list prices*, not cleared
   transactions. This is disclosed prominently (§11) and is the central problem Phase 2/3 addresses.

---

## 9. Update, versioning & publication

- **Snapshot cadence:** daily (UTC).
- **Index recomputation:** daily, from that day's snapshot + full history.
- **Series versioning:** every published series carries `methodology_version` (this doc's version) and
  `tiers_version` (the `tiers.yaml` version). A consumer can always tell which rules produced a value.
- **No restatement-in-place:** if a methodology change alters historical values, both the old and new
  series are published in parallel with a documented changelog; old values are never overwritten.
- **Outputs (Phase 1):** open methodology doc (this file), public dashboard, free read API, and an
  open-source repo containing the collector + computation + raw snapshots.

---

## 10. Governance of methodology changes

While Phase 1 is solo-run, changes still follow a lightweight, auditable process so the rate's
neutrality is defensible later:

1. Proposed change is written up (what, why, expected effect on series).
2. The change bumps `methodology_version` and/or `tiers_version`.
3. A changelog entry (§13) records the diff and the effective date.
4. Affected series are recomputed and **published in parallel** with the prior version for a transition
   window.

Parameters under governance: benchmark set `B`, tier thresholds (`tiers.yaml`), input:output weight
`W_io`, `N_min`, outlier thresholds, base date `t₀`, headline-basket weights.

(In Phase 2 this process is handed to token-holder governance — see roadmap spec §3.3.)

---

## 11. Limitations & known issues (disclosed, not hidden)

- **Quoted, not transacted, prices.** The single biggest limitation. A reference rate ultimately needs
  a deep transaction base (the SOFR lesson). Phase 1 is rules-based on list prices; transaction
  grounding (via observed x402 settlement flows / partnerships) is the Phase 2/3 mandate.
- **Benchmark validity & contamination.** Benchmarks saturate, leak, and imperfectly proxy real
  capability. Mitigation: a *vector* of benchmarks, periodic review, versioned tiers.
- **Quality non-fungibility.** Two models at the same tier are not identical (latency, refusals,
  context, tool use). The index measures *priced capability*, not total fitness-for-use.
- **Coverage gaps.** Private/enterprise pricing and committed-spend discounts are invisible to public
  data and excluded by design.
- **Survivorship.** Deprecated models exit; the methodology must record exits to avoid distorting
  iso-quality curves.

---

## 12. Reproducibility checklist (what we publish so others can verify)

- [ ] Daily raw snapshots (all listings + provenance) in the open repo.
- [ ] Benchmark scores used, with sources and versions.
- [ ] `tiers.yaml` (thresholds, weights, base date) under version control.
- [ ] The computation code (collector + index calc), open-source.
- [ ] A one-command reproduction: snapshot + tiers → published index values.

**Phase-1 acceptance test (from roadmap spec):** Beacon's iso-quality curves reproduce the published
LLMflation / Epoch numbers within a stated tolerance for the overlapping period. If they don't, the
methodology — not the published number — is wrong until reconciled.

---

## 13. Changelog

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-06-07 | Initial draft. Defines scope, principles, data model, blended-price (3:1), capability tiers, the three index families (iso-quality / frontier / spread), hedonic cross-check, data-quality rules, governance, and limitations. Tier thresholds left to v1 calibration (`tiers.yaml`). |

---

## 14. Open items for v1 calibration

1. Finalize tier thresholds in `tiers.yaml` (requires assembling the historical price+benchmark dataset
   first).
2. Choose the base date `t₀` (candidate: GPT-4 launch month, for comparability with a16z/Epoch).
3. Decide the initial provider/host universe and the exact pricing-source URLs per provider.
4. Set the headline-basket tier weights (or defer the headline until per-tier series are trusted).
5. Define the numeric tolerance for the Phase-1 acceptance test against Epoch/a16z.
