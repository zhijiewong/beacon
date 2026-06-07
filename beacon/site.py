"""Generate the public Beacon dashboard (static, dependency-free).

  python3 -m beacon.site        # writes site/index.html + site/index.json

Aesthetic: "benchmark almanac" — an editorial financial reference rate (warm
paper, ink, one signal-vermilion accent; Instrument Serif + IBM Plex Mono/Sans).
Shows ONLY the index + methodology. build_context is pure and unit-tested;
HTML/SVG is presentation, verified by opening the page.
"""
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from beacon import analyze, feeds, plot

SITE_DIR = analyze.DATA_DIR.parent / "site"
EXPLORER = "https://sepolia.basescan.org/address/"

# palette (paper / ink / signal)
INK, SOFT, HAIR, SIG, SLATE, OCHRE = "#18140D", "#6A6354", "#D7D0BF", "#C8431B", "#2F5D74", "#A07C2C"


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


# ---- presentation: charts (paper palette) -----------------------------------

TIER_LABEL = {"frontier": "Frontier", "strong": "Strong", "gpt-4-class": "GPT-4 class"}
TIER_COLOR = {"frontier": SIG, "strong": SLATE, "gpt-4-class": OCHRE}


def _money(v: float) -> str:
    return ("%.0f" % v) if v >= 1 else ("%.2f" % v).rstrip("0").rstrip(".")


def _frontier_svg(points, frontier, benchmark, w=900, h=460) -> str:
    pad = 70
    xs = [c for _, c, _ in points]
    xmin, xmax = min(xs), max(xs)
    ly = [math.log10(p) for _, _, p in points]
    ymin, ymax = math.floor(min(ly)), math.ceil(max(ly))

    def px(c):
        return pad + (c - xmin) / (xmax - xmin) * (w - 2 * pad)

    def py(p):
        return h - pad - (math.log10(p) - ymin) / (ymax - ymin) * (h - 2 * pad)

    e = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
         'font-family="\'IBM Plex Mono\',monospace">' % (w, h)]
    for d in range(ymin, ymax + 1):
        y = py(10 ** d)
        e.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>' % (pad, y, w - pad, y, HAIR))
        e.append('<text x="%d" y="%.1f" fill="%s" font-size="12" text-anchor="end">$%s</text>'
                 % (pad - 12, y + 4, SOFT, _money(10 ** d)))
    for c in range(int(xmin // 10 * 10), int(xmax) + 1, 10):
        if c < xmin:
            continue
        e.append('<text x="%.1f" y="%d" fill="%s" font-size="12" text-anchor="middle">%d</text>'
                 % (px(c), h - pad + 24, SOFT, c))
    fr = [(px(t), py(v)) for t, v in frontier if v is not None]
    if fr:
        e.append('<path d="M%s" fill="none" stroke="%s" stroke-width="2.5"/>'
                 % (" L".join("%.1f %.1f" % xy for xy in fr), SIG))
    for _, c, p in points:
        e.append('<circle cx="%.1f" cy="%.1f" r="3.6" fill="%s" opacity="0.30"/>' % (px(c), py(p), INK))
    e.append('<text x="%d" y="%d" fill="%s" font-size="12" text-anchor="middle" '
             'letter-spacing="0.12em">%s CAPABILITY →</text>' % (w // 2, h - 18, SOFT, benchmark.upper()))
    e.append("</svg>")
    return "\n".join(e)


def _trend_svg(series_by_tier, w=900, h=320) -> Optional[str]:
    dated = {k: v for k, v in series_by_tier.items() if len(v) >= 2}
    if not dated:
        return None
    pad = 70
    vals = [v for s in dated.values() for _, v in s]
    ly = [math.log10(v) for v in vals]
    ymin, ymax = math.floor(min(ly)), math.ceil(max(ly))
    dates = sorted({d for s in dated.values() for d, _ in s})
    xi = {d: i for i, d in enumerate(dates)}
    nx = max(1, len(dates) - 1)

    def px(d):
        return pad + xi[d] / nx * (w - 2 * pad)

    def py(v):
        return h - pad - (math.log10(v) - ymin) / max(1e-9, ymax - ymin) * (h - 2 * pad)

    e = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
         'font-family="\'IBM Plex Mono\',monospace">' % (w, h)]
    for d in range(ymin, ymax + 1):
        y = py(10 ** d)
        e.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>' % (pad, y, w - pad, y, HAIR))
        e.append('<text x="%d" y="%.1f" fill="%s" font-size="12" text-anchor="end">$%s</text>'
                 % (pad - 12, y + 4, SOFT, _money(10 ** d)))
    for d in dates:
        e.append('<text x="%.1f" y="%d" fill="%s" font-size="11" text-anchor="middle">%s</text>'
                 % (px(d), h - pad + 22, SOFT, d[5:]))
    for name, s in dated.items():
        pts = [(px(d), py(v)) for d, v in s]
        e.append('<path d="M%s" fill="none" stroke="%s" stroke-width="2.5"/>'
                 % (" L".join("%.1f %.1f" % p for p in pts), TIER_COLOR.get(name, INK)))
        for x, y in pts:
            e.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="%s"/>' % (x, y, TIER_COLOR.get(name, INK)))
    e.append("</svg>")
    return "\n".join(e)


# ---- presentation: HTML -----------------------------------------------------

_GRAIN = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E"
          "%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E"
          "%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")

CSS = """
:root{
  --paper:#F3F0E7; --paper-2:#EBE7DA; --ink:#18140D; --soft:#6A6354;
  --hair:#D7D0BF; --sig:#C8431B;
  --serif:'Instrument Serif',Georgia,serif;
  --mono:'IBM Plex Mono',ui-monospace,monospace;
  --sans:'IBM Plex Sans',ui-sans-serif,system-ui,sans-serif;
}
*{box-sizing:border-box}
html{-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.6;font-feature-settings:"tnum" 1,"kern" 1;}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:9;
  background-image:url("__GRAIN__");background-size:240px 240px;opacity:.05;mix-blend-mode:multiply;}
.wrap{max-width:1000px;margin:0 auto;padding:clamp(28px,5vw,72px) clamp(20px,5vw,40px) 96px;}
.mono{font-family:var(--mono);font-feature-settings:"tnum" 1;}
.kicker{font-family:var(--mono);font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--soft);}

/* masthead */
.mast{display:flex;justify-content:space-between;align-items:baseline;gap:24px;
  border-bottom:1.5px solid var(--ink);padding-bottom:16px;flex-wrap:wrap;}
.wordmark{font-family:var(--serif);font-size:clamp(40px,7vw,76px);line-height:.9;letter-spacing:-.01em;}
.wordmark b{font-weight:400;}
.mast .tag{font-family:var(--mono);font-size:12px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--soft);text-align:right;}
.edition{display:flex;gap:20px;flex-wrap:wrap;font-family:var(--mono);font-size:12px;
  letter-spacing:.12em;text-transform:uppercase;color:var(--soft);padding:12px 0 0;border-top:none;}
.edition .dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--sig);
  margin-right:7px;vertical-align:middle;box-shadow:0 0 0 0 rgba(200,67,27,.5);animation:pulse 2.4s infinite;}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(200,67,27,.45)}70%{box-shadow:0 0 0 7px rgba(200,67,27,0)}100%{box-shadow:0 0 0 0 rgba(200,67,27,0)}}

/* lede */
.lede{font-family:var(--serif);font-weight:400;font-size:clamp(34px,5.6vw,60px);
  line-height:1.04;letter-spacing:-.01em;margin:clamp(40px,7vw,72px) 0 14px;max-width:18ch;}
.standfirst{max-width:56ch;color:#3a352b;font-size:clamp(16px,2vw,18px);margin:0 0 8px;}

/* rate table */
.rates{margin:44px 0 16px;border-top:1.5px solid var(--ink);}
.rate{display:grid;grid-template-columns:1.1fr 1.4fr 1fr;gap:16px;align-items:baseline;
  padding:22px 8px;border-bottom:1px solid var(--hair);position:relative;transition:background .2s;}
.rate:hover{background:var(--paper-2);}
.rate::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:transparent;transition:background .2s;}
.rate:hover::before{background:var(--sig);}
.rate .name{font-family:var(--serif);font-size:clamp(22px,3vw,30px);}
.rate .gate{font-family:var(--mono);font-size:12px;letter-spacing:.06em;color:var(--soft);text-transform:uppercase;margin-top:2px;}
.rate .price{font-family:var(--mono);font-weight:500;font-size:clamp(30px,4.6vw,44px);letter-spacing:-.02em;}
.rate .price u{text-decoration:none;color:var(--soft);font-size:.42em;font-weight:400;}
.rate .stat{font-family:var(--mono);font-size:13px;color:var(--soft);text-align:right;}
.rate .stat b{color:var(--ink);font-weight:500;}

/* charts */
figure{margin:40px 0;padding:18px 18px 8px;background:var(--paper-2);border:1px solid var(--hair);}
figure svg{display:block;width:100%;height:auto;}
figcaption{font-family:var(--mono);font-size:12px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--soft);padding:8px 4px 4px;}
.note{font-family:var(--mono);font-size:13px;color:var(--soft);font-style:normal;
  padding:28px;border:1px dashed var(--hair);margin:40px 0;text-align:center;}

/* prose + seal */
h2{font-family:var(--serif);font-weight:400;font-size:clamp(26px,3.4vw,34px);margin:64px 0 12px;}
.prose{max-width:62ch;color:#33302a;}
.seal{margin:44px 0 0;padding:22px 24px;border:1.5px solid var(--ink);display:flex;gap:18px;
  align-items:center;flex-wrap:wrap;justify-content:space-between;background:var(--paper-2);}
.seal .l{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--soft);}
.seal a{font-family:var(--mono);color:var(--ink);text-decoration:none;border-bottom:2px solid var(--sig);
  word-break:break-all;font-size:14px;}
.seal a:hover{background:var(--sig);color:var(--paper);}
footer{margin-top:64px;border-top:1px solid var(--hair);padding-top:18px;
  font-family:var(--mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--soft);
  display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;}

/* load reveal */
.rise{opacity:0;transform:translateY(14px);animation:rise .7s cubic-bezier(.2,.7,.2,1) forwards;}
@keyframes rise{to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){.rise{animation:none;opacity:1;transform:none}.edition .dot{animation:none}}
@media(max-width:680px){.rate{grid-template-columns:1fr auto;row-gap:6px}.rate .stat{grid-column:1/-1;text-align:left}}
"""

JS = """
(function(){
  if(matchMedia('(prefers-reduced-motion:reduce)').matches)return;
  document.querySelectorAll('[data-count]').forEach(function(el){
    var to=parseFloat(el.getAttribute('data-count')),dec=parseInt(el.getAttribute('data-dec')||'0'),
        t0=null,dur=900;
    function step(t){if(!t0)t0=t;var p=Math.min((t-t0)/dur,1),e=1-Math.pow(1-p,3),
        v=(to*e).toFixed(dec);el.firstChild.nodeValue='$'+v;if(p<1)requestAnimationFrame(step);}
    el.firstChild.nodeValue='$'+(0).toFixed(dec);requestAnimationFrame(step);
  });
})();
"""


def _rate_rows(context: dict) -> str:
    rows = []
    for i, t in enumerate(context["tiers"]):
        label = TIER_LABEL.get(t["name"], t["name"])
        spread = f'{t["spread"]:.1f}×' if t["spread"] is not None else "—"
        delay = 0.15 + i * 0.08
        rows.append(f"""
      <div class="rate rise" style="animation-delay:{delay:.2f}s">
        <div>
          <div class="name">{label}</div>
          <div class="gate">{context['benchmark']} &ge; {t['threshold']}</div>
        </div>
        <div class="price"><span class="mono" data-count="{t['value_usd_per_mtok']:.3f}" data-dec="3">${t['value_usd_per_mtok']:.3f}</span><u>/Mtok</u></div>
        <div class="stat"><b>{t['n_qualifying']}</b> models<br>spread <b>{spread}</b></div>
      </div>""")
    return "".join(rows)


def render_html(context: dict, frontier_svg: str, trend_svg: Optional[str]) -> str:
    trend = (f'<figure class="rise" style="animation-delay:.55s">{trend_svg}'
             f'<figcaption>LLMflation &mdash; cheapest price to hold each tier, over time</figcaption></figure>'
             if trend_svg else
             '<p class="note rise" style="animation-delay:.55s">The LLMflation trend line fills in as daily snapshots accrue.</p>')
    onchain = ""
    if context["onchain"]:
        a = context["onchain"]["address"]
        onchain = f"""
  <div class="seal rise" style="animation-delay:.2s">
    <span class="l">Published on-chain &middot; Base Sepolia &middot; readable by any contract</span>
    <a href="{context['onchain']['explorer_url']}">{a}</a>
  </div>"""

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beacon &mdash; the reference rate for AI inference</title>
<meta name="description" content="What AI inference actually costs: a capability-normalized price reference rate across every major model, as of {context['as_of']}.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS.replace("__GRAIN__", _GRAIN)}</style></head>
<body><div class="wrap">

  <header class="mast rise">
    <div class="wordmark"><b>Beacon</b></div>
    <div class="tag">The Reference Rate<br>for AI Inference</div>
  </header>
  <div class="edition rise" style="animation-delay:.08s">
    <span><span class="dot"></span>As of {context['as_of']}</span>
    <span>{context['model_count']} models tracked</span>
    <span>Methodology v{context['methodology_version']}</span>
  </div>

  <h1 class="lede rise" style="animation-delay:.12s">What a unit of intelligence costs.</h1>
  <p class="standfirst rise" style="animation-delay:.16s">The cheapest price to reach a fixed AI capability &mdash; not a raw average that only falls &mdash; measured across every major provider and published as a neutral reference rate.</p>

  <section class="rates">{_rate_rows(context)}</section>

  <figure class="rise" style="animation-delay:.5s">{frontier_svg}
    <figcaption>Price &times; capability frontier &mdash; cheapest $/Mtok to reach each level today</figcaption>
  </figure>
  {trend}

  <h2 class="rise">How it's measured</h2>
  <p class="prose rise">Beacon is a <em>capability-normalized</em> index. Rather than averaging sticker
     prices &mdash; which only fall and hide what you actually get &mdash; it tracks the lowest
     $/million-tokens to reach a fixed capability tier (scored on {context['benchmark']}) across every
     major model. The construction is rules-based, reproducible, and transparent, the way credible
     commodity and rate benchmarks are built.</p>
  {onchain}

  <footer>
    <span>Beacon &middot; Neutral reference rate for AI inference</span>
    <span>Capability-normalized &middot; Rules-based &middot; Reproducible</span>
  </footer>
</div>
<script>{JS}</script>
</body></html>
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

    addr = None
    deployed = analyze.DATA_DIR.parent / "onchain" / "deployed.json"
    if deployed.exists():
        addr = json.loads(deployed.read_text()).get("address")

    context = build_context(snapshot, cap, addr)

    pts = plot.scored_points(snapshot["listings"], cap, context["benchmark"])
    cmin, cmax = int(min(c for _, c, _ in pts)), int(max(c for _, c, _ in pts))
    frontier = plot.frontier_curve(snapshot["listings"], cap, context["benchmark"],
                                   list(range(cmin, cmax + 1, 5)))
    frontier_svg = _frontier_svg(pts, frontier, context["benchmark"])

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
