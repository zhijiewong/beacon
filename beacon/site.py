"""Generate the public Beacon dashboard (static, dependency-free).

  python3 -m beacon.site        # writes site/index.html + site/index.json

Shows ONLY the index + methodology — never strategy. build_context is pure and
unit-tested; HTML/SVG rendering is presentation, verified by opening the page.
"""
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from beacon import analyze, feeds, plot

SITE_DIR = analyze.DATA_DIR.parent / "site"
EXPLORER = "https://sepolia.basescan.org/address/"


# ---- pure data shaping (unit-tested) ----------------------------------------

def build_context(
    snapshot: dict,
    cap: Dict[str, Dict[str, float]],
    onchain_address: Optional[str],
    tiers: Sequence[Tuple[str, float]] = feeds.DEFAULT_TIERS,
    benchmark: str = "GPQA-Diamond",
) -> dict:
    """Everything the dashboard template needs, derived from one snapshot."""
    listings = snapshot["listings"]
    tier_rows = []
    for name, threshold in tiers:
        t = analyze.compute_tier(listings, cap, benchmark, threshold)
        if t["iso_quality"] is None:
            continue
        tier_rows.append({
            "name": name,
            "threshold": threshold,
            "value_usd_per_mtok": t["iso_quality"],
            "spread": t["spread"],
            "n_qualifying": t["n_qualifying"],
        })
    return {
        "as_of": snapshot["observed_at"],
        "model_count": snapshot.get("listing_count", len(listings)),
        "methodology_version": snapshot.get("methodology_version", "0.1"),
        "benchmark": benchmark,
        "tiers": tier_rows,
        "onchain": (
            {"address": onchain_address, "explorer_url": EXPLORER + onchain_address}
            if onchain_address else None
        ),
    }


# ---- presentation -----------------------------------------------------------

TIER_LABEL = {"frontier": "Frontier", "strong": "Strong", "gpt-4-class": "GPT-4 class"}


def _trend_svg(series_by_tier: Dict[str, List[Tuple[str, float]]], w=820, h=300) -> Optional[str]:
    """Compact LLMflation line chart; None if no tier has >=2 dated points."""
    dated = {k: v for k, v in series_by_tier.items() if len(v) >= 2}
    if not dated:
        return None
    pad = 60
    all_vals = [val for s in dated.values() for _, val in s]
    ly = [math.log10(v) for v in all_vals]
    ymin, ymax = math.floor(min(ly)), math.ceil(max(ly))
    dates = sorted({d for s in dated.values() for d, _ in s})
    xi = {d: i for i, d in enumerate(dates)}
    nx = max(1, len(dates) - 1)

    def px(d):
        return pad + xi[d] / nx * (w - 2 * pad)

    def py(v):
        lp = math.log10(v)
        return h - pad - (lp - ymin) / max(1e-9, (ymax - ymin)) * (h - 2 * pad)

    colors = {"frontier": "#f5a623", "strong": "#4aa3ff", "gpt-4-class": "#7ed957"}
    e = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="system-ui,sans-serif">' % (w, h)]
    e.append('<rect width="100%%" height="100%%" fill="#0b0e14"/>')
    for d in range(ymin, ymax + 1):
        y = py(10 ** d)
        e.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#1e2633"/>' % (pad, y, w - pad, y))
        e.append('<text x="%d" y="%.1f" fill="#7a8699" font-size="11" text-anchor="end">$%s</text>'
                 % (pad - 8, y + 4, ("%.2f" % (10 ** d)).rstrip("0").rstrip(".")))
    for name, s in dated.items():
        pts = [(px(d), py(v)) for d, v in s]
        path = "M" + " L".join("%.1f %.1f" % p for p in pts)
        c = colors.get(name, "#aaa")
        e.append('<path d="%s" fill="none" stroke="%s" stroke-width="2.5"/>' % (path, c))
        for x, y in pts:
            e.append('<circle cx="%.1f" cy="%.1f" r="3" fill="%s"/>' % (x, y, c))
    e.append('<text x="%d" y="20" fill="#9aa7b8" font-size="12">iso-quality $/Mtok over time (LLMflation)</text>' % pad)
    e.append("</svg>")
    return "\n".join(e)


def render_html(context: dict, frontier_svg: str, trend_svg: Optional[str]) -> str:
    cards = []
    for t in context["tiers"]:
        label = TIER_LABEL.get(t["name"], t["name"])
        spread = f'{t["spread"]:.1f}&times;' if t["spread"] is not None else "&mdash;"
        cards.append(f"""
      <div class="card">
        <div class="tier">{label}</div>
        <div class="price">${t['value_usd_per_mtok']:.3f}<span>/Mtok</span></div>
        <div class="meta">{context['benchmark']} &ge; {t['threshold']} &middot; {t['n_qualifying']} models &middot; spread {spread}</div>
      </div>""")
    cards_html = "".join(cards)
    trend_html = f'<section class="chart">{trend_svg}</section>' if trend_svg else (
        '<p class="note">The LLMflation trend chart appears as more daily snapshots accrue.</p>')
    onchain_html = ""
    if context["onchain"]:
        a = context["onchain"]["address"]
        onchain_html = (
            f'<p class="onchain">Published on-chain (Base Sepolia testnet): '
            f'<a href="{context["onchain"]["explorer_url"]}"><code>{a}</code></a> &mdash; '
            f'readable by any smart contract.</p>')

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beacon &mdash; what AI inference actually costs</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#0b0e14; color:#e6e6e6; font-family:ui-sans-serif,system-ui,sans-serif; line-height:1.5; }}
  .wrap {{ max-width:880px; margin:0 auto; padding:48px 20px 80px; }}
  h1 {{ font-size:30px; margin:0 0 6px; letter-spacing:-0.02em; }}
  .sub {{ color:#9aa7b8; margin:0 0 32px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin-bottom:36px; }}
  .card {{ background:#121724; border:1px solid #1e2633; border-radius:14px; padding:20px; }}
  .tier {{ color:#9aa7b8; font-size:13px; text-transform:uppercase; letter-spacing:0.06em; }}
  .price {{ font-size:34px; font-weight:650; margin:6px 0 4px; }}
  .price span {{ font-size:15px; color:#7a8699; font-weight:400; }}
  .meta {{ color:#7a8699; font-size:13px; }}
  .chart {{ background:#121724; border:1px solid #1e2633; border-radius:14px; padding:12px; margin:24px 0; overflow:auto; }}
  .chart svg {{ display:block; max-width:100%; height:auto; }}
  h2 {{ font-size:18px; margin:36px 0 10px; }}
  p {{ color:#c4ccd6; }}
  .note {{ color:#7a8699; font-style:italic; }}
  .onchain code {{ background:#121724; padding:2px 6px; border-radius:6px; }}
  a {{ color:#4aa3ff; }}
  footer {{ color:#5b6675; font-size:13px; margin-top:48px; border-top:1px solid #1e2633; padding-top:16px; }}
</style></head>
<body><div class="wrap">
  <h1>What AI inference actually costs</h1>
  <p class="sub">The cheapest price to reach a fixed AI capability, across all major providers &middot;
     as of {context['as_of']} &middot; {context['model_count']} models tracked</p>

  <div class="cards">{cards_html}</div>

  <section class="chart">{frontier_svg}</section>
  {trend_html}

  <h2>How it's measured</h2>
  <p>Beacon is a <strong>capability-normalized</strong> price index: instead of a raw average that just
     falls over time, it tracks the cheapest $/million-tokens to reach a fixed capability tier
     (measured on {context['benchmark']}) across every major provider. The method is rules-based,
     reproducible, and transparent &mdash; the same way credible commodity benchmarks are built.</p>
  {onchain_html}

  <footer>Methodology v{context['methodology_version']} &middot; capability-normalized, rules-based, reproducible.
     A neutral reference rate for AI inference.</footer>
</div></body></html>
"""


def main() -> int:
    snaps = sorted(analyze.SNAPSHOT_DIR.glob("*.json"))
    if not snaps:
        print("No snapshots; run beacon.collector")
        return 1
    snapshot = json.loads(snaps[-1].read_text())
    rows = analyze.read_benchmarks(str(analyze.BENCHMARKS_CSV))
    cap = analyze.build_capability_map(rows, include_unverified=False)
    if not cap:
        print("No verified benchmarks; calibrate data/benchmarks.csv first")
        return 1

    # on-chain address (optional)
    addr = None
    deployed = analyze.DATA_DIR.parent / "onchain" / "deployed.json"
    if deployed.exists():
        addr = json.loads(deployed.read_text()).get("address")

    context = build_context(snapshot, cap, addr)

    # frontier chart (reuse beacon.plot)
    pts = plot.scored_points(snapshot["listings"], cap, context["benchmark"])
    cmin, cmax = int(min(c for _, c, _ in pts)), int(max(c for _, c, _ in pts))
    frontier = plot.frontier_curve(snapshot["listings"], cap, context["benchmark"],
                                   list(range(cmin, cmax + 1, 5)))
    frontier_svg = plot._svg_frontier(pts, frontier, context["benchmark"])

    # trend chart (>=2 snapshots)
    all_snaps = [(json.loads(p.read_text())["observed_at"], json.loads(p.read_text())["listings"])
                 for p in snaps]
    series = {name: plot.iso_quality_series(all_snaps, cap, context["benchmark"], thr)
              for name, thr in feeds.DEFAULT_TIERS}
    trend_svg = _trend_svg(series)

    SITE_DIR.mkdir(exist_ok=True)
    (SITE_DIR / "index.html").write_text(render_html(context, frontier_svg, trend_svg))
    (SITE_DIR / "index.json").write_text(json.dumps(context, indent=2))
    print(f"Wrote {SITE_DIR/'index.html'} and index.json  ({len(context['tiers'])} tiers, "
          f"as of {context['as_of']}, trend={'yes' if trend_svg else 'pending'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
