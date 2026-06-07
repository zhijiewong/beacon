# Phase 1 Dashboard Design — Public Index Site

**Version:** 0.1 (DRAFT)
**Date:** 2026-06-07
**Status:** for review before implementation
**Prereq:** Phase 1 pipeline (collector, index, feeds, plot) — built and running.

---

## 1. Context — why

Phase 1's index works and runs daily, but it is invisible: nobody can see or cite it.
Traction is the explicit gate for Phase 2 (token launch only after the rate has consumers —
the Hyperliquid sequencing). A public, shareable dashboard is the lowest-effort way to make
the rate visible and credible.

**Hard constraint:** the main repo is **private and holds the full business strategy**
(thesis, token plan, Phase 2/3). The dashboard must expose **only the index + methodology** —
never the strategy. This shapes both content and hosting.

**Outcome:** a shareable URL showing "what AI inference actually costs," that updates daily on
its own, and whose novel credibility hook (the on-chain feed) sets it apart from the existing
free price trackers.

---

## 2. Goals & non-goals

**Goals**
- A single, polished, **static** page anyone can open and share.
- Show the live capability-normalized rate, the frontier chart, the spread, and (as it builds)
  the LLMflation trend.
- Dependency-free generation (stdlib only), reusing existing modules.
- Auto-refresh from the daily job.

**Non-goals**
- No backend/server, no database, no JS framework (a static page + embedded SVG is enough).
- No interactivity beyond links in v1.
- No exposure of strategy/thesis/token/Phase 2-3 content.

---

## 3. What it shows (index-only)

| Section | Content |
|---------|---------|
| Header | "What AI inference actually costs" + "as of \<UTC date\>" + model count |
| Live rate | The 3 GPQA-Diamond tiers in $/Mtok: frontier, strong, gpt-4-class |
| Frontier chart | The price–capability frontier SVG (reused from `beacon.plot`) |
| Spread | Cross-provider P90/P10 spread per tier (the volatile signal) |
| LLMflation trend | Line of iso-quality over snapshot dates — shown once ≥2 snapshots exist |
| Methodology | Short blurb (capability-normalized, hedonic, transparent) + "how it's built" |
| Credibility footer | "Published on-chain (Base Sepolia): 0xD367…" + Basescan link |

**Explicitly excluded:** thesis, token/tokenomics, Phase 2/3 plans, research, competitor analysis.

---

## 4. Architecture & data flow

```
data/snapshots/<latest>.json  ─┐
data/benchmarks.csv           ─┤→ beacon.site.build_context()  → context dict
onchain/deployed.json (addr)  ─┘                                      │
beacon.plot._svg_frontier()  ───────────────────────────────────────┤→ render_html()
                                                                      ↓
                                          site/index.html  +  site/index.json (public data feed)
```

- **Reuse:** `beacon.feeds.build_feeds` (tier values), `beacon.analyze.compute_tier` (spread),
  `beacon.plot` (frontier SVG + iso_quality_series for the trend).
- **`site/index.json`** doubles as a stable public **data feed** (covers the "public API" option
  for free) — the same numbers the page shows.

---

## 5. The generator — `beacon/site.py`

Split pure data shaping (tested) from HTML rendering (presentation):

- `build_context(snapshot, cap, onchain_address) -> dict` — **pure, unit-tested.** Produces
  `{as_of, model_count, tiers: [{name, threshold, value_usd_per_mtok, spread, n_qualifying}],
  methodology_version, onchain: {address, explorer_url}}`.
- `render_html(context, frontier_svg, trend_svg|None) -> str` — presentation; inline CSS, embeds
  SVGs. Clean, distinctive, readable; no external assets.
- `main()` — load latest snapshot + verified benchmarks, build context, generate SVG(s) via
  `beacon.plot`, write `site/index.html` and `site/index.json`.

Privacy is structural: the generator only reads snapshots, `benchmarks.csv`, a hardcoded
methodology blurb, and the on-chain address. It has no path to strategy docs.

---

## 6. Hosting

GitHub Pages. Because the main repo is private (Pages there needs a paid plan), publish to a
**separate public repo** (working name `beacon-index`) that contains **only** the generated
`site/` output + `index.json`. Pages serves it at `https://<user>.github.io/beacon-index/`.

- The private repo's generator builds `site/`; a deploy step syncs `site/` → the public repo.
- The public repo contains no strategy, no Python source beyond what's needed (ideally just the
  built static files + data) — keeping the boundary clean.

---

## 7. Auto-update

Add a **4th non-fatal step** to `scripts/collect.sh` (after collect → backup → on-chain):
regenerate the site and push to the public repo. Same non-fatal discipline — a publish failure
never breaks collection. Wired only after hosting is set up.

---

## 8. Testing

- **TDD `build_context`** (pure): correct tier values, spread, as_of, model count, on-chain link.
- **Acceptance:** open `site/index.html`; the displayed tier values match `python3 -m beacon.feeds`
  exactly; `site/index.json` parses and matches.
- HTML/SVG rendering is visual — verified by opening the page, not unit-tested.

---

## 9. Build order

1. `beacon/site.py`: `build_context` (TDD) → `render_html` → `main` writing `site/index.html`+`json`.
2. Reuse `beacon.plot` for the frontier SVG (and trend SVG once ≥2 snapshots).
3. `.gitignore` `site/` in the private repo (it's generated output / lives in the public repo).
4. View locally, refine styling.
5. (separate step, user-gated) create the public repo + enable Pages + deploy.
6. (after hosting) wire the daily auto-publish step.

---

## 10. Open questions
1. Public repo name (`beacon-index`? final brand TBD).
2. How much methodology to show on-page vs link to a public methodology doc.
3. Whether to publish `index.json` as the advertised "data feed" in v1 or later.
4. Visual style direction (clean/minimal data-site vs more branded).

---

## 11. What "done" means
A polished static `index.html` + `index.json`, generated dependency-free from the live data,
showing the rate/frontier/spread/methodology/on-chain link and nothing strategic. Hosting and
daily auto-publish are explicit follow-on steps once the page itself is approved locally.
