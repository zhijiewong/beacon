"""Generate the public Beacon dashboard (static, dependency-free).

  python3 -m beacon.site        # writes site/index.html + site/index.json

Aesthetic: "benchmark almanac" — an editorial financial reference rate (warm
paper, ink, signal-vermilion; Instrument Serif + IBM Plex Mono/Sans). Dense with
real, computed data: a key-figures band, a sparkline rate sheet, a price-
distribution dot-plot, and an annotated price-capability frontier. Shows ONLY the
index + methodology. build_context / pct_change are pure & unit-tested; the rest
is presentation, verified by opening the page.
"""
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from beacon import analyze, feeds, index, plot

SITE_DIR = analyze.DATA_DIR.parent / "site"
EXPLORER = "https://sepolia.basescan.org/address/"

INK, SOFT, HAIR, SIG, SLATE, OCHRE = "#18140D", "#6A6354", "#D7D0BF", "#C8431B", "#2F5D74", "#A07C2C"
UP, DOWN = "#C8431B", "#3F7A4F"  # price up (costlier) / down (cheaper)
TIER_LABEL = {"frontier": "Frontier", "strong": "Strong", "gpt-4-class": "GPT-4 class"}
TIER_COLOR = {"frontier": SIG, "strong": SLATE, "gpt-4-class": OCHRE}


# ---- pure data (unit-tested) ------------------------------------------------

def _provider_of(listing: dict) -> str:
    return listing.get("provider") or listing["model"].split("/", 1)[0]


def _tier_detail(listings, cap, benchmark, threshold) -> dict:
    t = analyze.compute_tier(listings, cap, benchmark, threshold)
    q = []  # (model, provider, blended) for qualifying listings
    for li in listings:
        sc = cap.get(li["model"])
        if sc and sc.get(benchmark, -1) >= threshold:
            q.append((li["model"], _provider_of(li), li["blended_mtok"]))
    cheapest = None
    if q:
        qs = sorted(q, key=lambda r: r[2])
        while len(qs) >= 2 and qs[0][2] < (1 - index.OUTLIER_DROP_FRACTION) * qs[1][2]:
            qs.pop(0)  # outlier-guarded cheapest (mirrors index.robust_min_price)
        cheapest = qs[0][0]
    return {
        "value_usd_per_mtok": t["iso_quality"],
        "spread": t["spread"],
        "n_qualifying": t["n_qualifying"],
        "provider_count": len({p for _, p, _ in q}),
        "cheapest_model": cheapest,
        "prices": sorted(b for _, _, b in q),
    }


def build_context(snapshot, cap, onchain_address, tiers=feeds.DEFAULT_TIERS,
                  benchmark="GPQA-Diamond") -> dict:
    listings = snapshot["listings"]
    rows = []
    for name, threshold in tiers:
        d = _tier_detail(listings, cap, benchmark, threshold)
        if d["value_usd_per_mtok"] is None:
            continue
        rows.append({"name": name, "threshold": threshold, **d})
    multiple = None
    if len(rows) >= 2 and rows[-1]["value_usd_per_mtok"]:
        multiple = rows[0]["value_usd_per_mtok"] / rows[-1]["value_usd_per_mtok"]
    return {
        "as_of": snapshot["observed_at"],
        "model_count": snapshot.get("listing_count", len(listings)),
        "methodology_version": snapshot.get("methodology_version", "0.1"),
        "benchmark": benchmark,
        "tiers": rows,
        "key_figures": {
            "providers_total": len({_provider_of(li) for li in listings}),
            "multiple": multiple,
        },
        "onchain": ({"address": onchain_address, "explorer_url": EXPLORER + onchain_address}
                    if onchain_address else None),
    }


def pct_change(series: Sequence[Tuple[str, float]]) -> Optional[float]:
    """Percent change of the most recent point vs the previous one."""
    if len(series) < 2:
        return None
    prev, last = series[-2][1], series[-1][1]
    return None if prev == 0 else (last - prev) / prev * 100.0


# ---- presentation: small charts ---------------------------------------------

def _money(v):
    return ("%.0f" % v) if v >= 1 else ("%.2f" % v).rstrip("0").rstrip(".")


def _short_model(m):
    return m.split("/", 1)[1] if "/" in m else m


def _sparkline(series, w=84, h=24):
    if len(series) < 2:
        return ""
    vals = [v for _, v in series]
    lo, hi = min(vals), max(vals)
    n = len(vals) - 1
    px = lambda i: 2 + i / n * (w - 4)
    py = lambda v: h / 2 if hi == lo else (h - 3) - (v - lo) / (hi - lo) * (h - 6)
    pts = " ".join("%.1f,%.1f" % (px(i), py(v)) for i, v in enumerate(vals))
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" class="spark">'
            f'<polyline points="{pts}" fill="none" stroke="{SOFT}" stroke-width="1.6"/>'
            f'<circle cx="{px(n):.1f}" cy="{py(vals[-1]):.1f}" r="2.2" fill="{SIG}"/></svg>')


def _distribution_svg(tiers, w=900, h=300):
    """Shared log-axis dot-plot: every provider's price, per capability tier."""
    allp = [p for t in tiers for p in t["prices"]]
    if not allp:
        return ""
    lo, hi = math.floor(math.log10(min(allp))), math.ceil(math.log10(max(allp)))
    padL, padR, padT, padB = 130, 40, 30, 46
    def px(p):
        return padL + (math.log10(p) - lo) / max(1e-9, hi - lo) * (w - padL - padR)
    rows = [t for t in tiers if t["prices"]]
    lane_h = (h - padT - padB) / max(1, len(rows))
    e = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
         'font-family="\'IBM Plex Mono\',monospace">' % (w, h)]
    for d in range(lo, hi + 1):
        x = px(10 ** d)
        e.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s"/>' % (x, padT, x, h - padB, HAIR))
        e.append('<text x="%.1f" y="%d" fill="%s" font-size="12" text-anchor="middle">$%s</text>'
                 % (x, h - padB + 22, SOFT, _money(10 ** d)))
    for i, t in enumerate(rows):
        cy = padT + lane_h * (i + 0.5)
        c = TIER_COLOR.get(t["name"], INK)
        e.append('<text x="%d" y="%.1f" fill="%s" font-size="13" text-anchor="end" '
                 'font-family="\'IBM Plex Sans\',sans-serif">%s</text>'
                 % (padL - 16, cy + 4, INK, TIER_LABEL.get(t["name"], t["name"])))
        cheapest = min(t["prices"])
        for p in t["prices"]:
            big = (p == cheapest)
            e.append('<circle cx="%.1f" cy="%.1f" r="%s" fill="%s" opacity="%s"/>'
                     % (px(p), cy, "5.5" if big else "4", c, "1" if big else "0.42"))
            if big:
                e.append('<circle cx="%.1f" cy="%.1f" r="8.5" fill="none" stroke="%s" stroke-width="1.3"/>'
                         % (px(p), cy, c))
    e.append('<text x="%d" y="%d" fill="%s" font-size="12" letter-spacing="0.1em">PRICE $/MTOK (LOG) &mdash; EACH DOT IS A PROVIDER; RINGED = CHEAPEST</text>'
             % (padL, 18, SOFT))
    e.append("</svg>")
    return "\n".join(e)


def _frontier_svg(points, frontier, benchmark, tiers, w=900, h=460):
    pad = 70
    xs = [c for _, c, _ in points]
    xmin, xmax = min(xs), max(xs)
    ly = [math.log10(p) for _, _, p in points]
    ymin, ymax = math.floor(min(ly)), math.ceil(max(ly))
    px = lambda c: pad + (c - xmin) / (xmax - xmin) * (w - 2 * pad)
    py = lambda p: h - pad - (math.log10(p) - ymin) / (ymax - ymin) * (h - 2 * pad)
    e = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="\'IBM Plex Mono\',monospace">' % (w, h)]
    for d in range(ymin, ymax + 1):
        y = py(10 ** d)
        e.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>' % (pad, y, w - pad, y, HAIR))
        e.append('<text x="%d" y="%.1f" fill="%s" font-size="12" text-anchor="end">$%s</text>' % (pad - 12, y + 4, SOFT, _money(10 ** d)))
    for c in range(int(xmin // 10 * 10), int(xmax) + 1, 10):
        if c < xmin:
            continue
        e.append('<text x="%.1f" y="%d" fill="%s" font-size="12" text-anchor="middle">%d</text>' % (px(c), h - pad + 24, SOFT, c))
    # tier threshold guides (annotation)
    for t in tiers:
        thr = t["threshold"]
        if xmin <= thr <= xmax:
            x = px(thr)
            e.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-dasharray="3 4" opacity="0.7"/>'
                     % (x, pad, x, h - pad, TIER_COLOR.get(t["name"], SOFT)))
            e.append('<text x="%.1f" y="%d" fill="%s" font-size="11" text-anchor="middle" letter-spacing="0.06em">%s</text>'
                     % (x, pad - 8, TIER_COLOR.get(t["name"], SOFT), TIER_LABEL.get(t["name"], t["name"]).upper()))
    fr = [(px(t), py(v)) for t, v in frontier if v is not None]
    if fr:
        e.append('<path d="M%s" fill="none" stroke="%s" stroke-width="2.5"/>' % (" L".join("%.1f %.1f" % xy for xy in fr), SIG))
    for _, c, p in points:
        e.append('<circle cx="%.1f" cy="%.1f" r="3.6" fill="%s" opacity="0.28"/>' % (px(c), py(p), INK))
    e.append('<text x="%d" y="%d" fill="%s" font-size="12" text-anchor="middle" letter-spacing="0.12em">%s CAPABILITY &rarr;</text>' % (w // 2, h - 18, SOFT, benchmark.upper()))
    e.append("</svg>")
    return "\n".join(e)


def _trend_svg(series_by_tier, w=900, h=300):
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
    px = lambda d: pad + xi[d] / nx * (w - 2 * pad)
    py = lambda v: h - pad - (math.log10(v) - ymin) / max(1e-9, ymax - ymin) * (h - 2 * pad)
    e = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="\'IBM Plex Mono\',monospace">' % (w, h)]
    for d in range(ymin, ymax + 1):
        y = py(10 ** d)
        e.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>' % (pad, y, w - pad, y, HAIR))
        e.append('<text x="%d" y="%.1f" fill="%s" font-size="12" text-anchor="end">$%s</text>' % (pad - 12, y + 4, SOFT, _money(10 ** d)))
    for d in dates:
        e.append('<text x="%.1f" y="%d" fill="%s" font-size="11" text-anchor="middle">%s</text>' % (px(d), h - pad + 22, SOFT, d[5:]))
    for name, s in dated.items():
        pts = [(px(d), py(v)) for d, v in s]
        e.append('<path d="M%s" fill="none" stroke="%s" stroke-width="2.5"/>' % (" L".join("%.1f %.1f" % p for p in pts), TIER_COLOR.get(name, INK)))
        for x, y in pts:
            e.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="%s"/>' % (x, y, TIER_COLOR.get(name, INK)))
    return "\n".join(e) + "</svg>"


# ---- presentation: HTML -----------------------------------------------------

_GRAIN = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E"
          "%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E"
          "%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")

CSS = """
:root{--paper:#F3F0E7;--paper-2:#EBE7DA;--ink:#18140D;--soft:#6A6354;--hair:#D7D0BF;--sig:#C8431B;
  --serif:'Instrument Serif',Georgia,serif;--mono:'IBM Plex Mono',ui-monospace,monospace;--sans:'IBM Plex Sans',system-ui,sans-serif;}
*{box-sizing:border-box}
html{-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.6;font-feature-settings:"tnum" 1,"kern" 1;}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:9;background-image:url("__GRAIN__");background-size:240px 240px;opacity:.05;mix-blend-mode:multiply;}
.wrap{max-width:1040px;margin:0 auto;padding:clamp(28px,5vw,72px) clamp(20px,5vw,40px) 96px;}
.mono{font-family:var(--mono);font-feature-settings:"tnum" 1;}
/* masthead */
.mast{display:flex;justify-content:space-between;align-items:baseline;gap:24px;border-bottom:1.5px solid var(--ink);padding-bottom:16px;flex-wrap:wrap;}
.wordmark{font-family:var(--serif);font-size:clamp(40px,7vw,76px);line-height:.9;}
.tag{font-family:var(--mono);font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--soft);text-align:right;}
.edition{display:flex;gap:20px;flex-wrap:wrap;font-family:var(--mono);font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--soft);padding:12px 0 0;}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--sig);margin-right:7px;animation:pulse 2.4s infinite;}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(200,67,27,.45)}70%{box-shadow:0 0 0 7px rgba(200,67,27,0)}100%{box-shadow:0 0 0 0 rgba(200,67,27,0)}}
/* lede + figures band */
.lede{font-family:var(--serif);font-size:clamp(34px,5.6vw,60px);line-height:1.04;margin:clamp(36px,6vw,64px) 0 14px;max-width:18ch;}
.standfirst{max-width:58ch;color:#3a352b;font-size:clamp(16px,2vw,18px);margin:0 0 28px;}
.figures{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--hair);border:1px solid var(--hair);margin:8px 0 40px;}
.fig{background:var(--paper);padding:20px 22px;}
.fig .n{font-family:var(--mono);font-weight:600;font-size:clamp(28px,4vw,40px);letter-spacing:-.02em;}
.fig .l{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--soft);margin-top:4px;}
/* rate sheet */
.kicker{font-family:var(--mono);font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--soft);margin:8px 0 6px;}
.rates{border-top:1.5px solid var(--ink);}
.rate{display:grid;grid-template-columns:1.2fr 1.3fr .8fr 1.7fr;gap:18px;align-items:center;padding:20px 10px;border-bottom:1px solid var(--hair);position:relative;transition:background .2s;}
.rate:hover{background:var(--paper-2);}
.rate::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:transparent;transition:background .2s;}
.rate:hover::before{background:var(--sig);}
.rate .name{font-family:var(--serif);font-size:clamp(22px,3vw,30px);line-height:1;}
.rate .gate{font-family:var(--mono);font-size:11px;letter-spacing:.06em;color:var(--soft);text-transform:uppercase;margin-top:3px;}
.rate .price{font-family:var(--mono);font-weight:500;font-size:clamp(26px,4vw,40px);letter-spacing:-.02em;}
.rate .price u{text-decoration:none;color:var(--soft);font-size:.4em;}
.chg{font-family:var(--mono);font-size:12px;margin-top:2px;}
.spark{display:block}
.detail{font-family:var(--mono);font-size:12.5px;color:var(--soft);text-align:right;line-height:1.5;}
.detail b{color:var(--ink);font-weight:500;}
.detail .m{color:var(--ink);}
/* figures/charts */
figure{margin:40px 0;padding:18px 18px 8px;background:var(--paper-2);border:1px solid var(--hair);}
figure svg{display:block;width:100%;height:auto;}
figcaption{font-family:var(--mono);font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--soft);padding:10px 4px 4px;}
.note{font-family:var(--mono);font-size:13px;color:var(--soft);padding:28px;border:1px dashed var(--hair);margin:40px 0;text-align:center;}
h2{font-family:var(--serif);font-size:clamp(26px,3.4vw,34px);margin:64px 0 12px;font-weight:400;}
.prose{max-width:62ch;color:#33302a;}
.seal{margin:44px 0 0;padding:22px 24px;border:1.5px solid var(--ink);display:flex;gap:18px;align-items:center;flex-wrap:wrap;justify-content:space-between;background:var(--paper-2);}
.seal .l{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--soft);}
.seal a{font-family:var(--mono);color:var(--ink);text-decoration:none;border-bottom:2px solid var(--sig);word-break:break-all;font-size:14px;}
.seal a:hover{background:var(--sig);color:var(--paper);}
footer{margin-top:64px;border-top:1px solid var(--hair);padding-top:18px;font-family:var(--mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--soft);display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;}
.rise{opacity:0;transform:translateY(14px);animation:rise .7s cubic-bezier(.2,.7,.2,1) forwards;}
@keyframes rise{to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){.rise{animation:none;opacity:1;transform:none}.dot{animation:none}}
@media(max-width:760px){.figures{grid-template-columns:1fr 1fr}.rate{grid-template-columns:1fr auto;row-gap:8px}.rate .spark{display:none}.detail{grid-column:1/-1;text-align:left}}
"""

JS = """
(function(){if(matchMedia('(prefers-reduced-motion:reduce)').matches)return;
document.querySelectorAll('[data-count]').forEach(function(el){
  var to=parseFloat(el.getAttribute('data-count')),dec=parseInt(el.getAttribute('data-dec')||'0'),pre=el.getAttribute('data-pre')||'',suf=el.getAttribute('data-suf')||'',t0=null;
  function f(t){if(!t0)t0=t;var p=Math.min((t-t0)/900,1),e=1-Math.pow(1-p,3);el.firstChild.nodeValue=pre+(to*e).toFixed(dec)+suf;if(p<1)requestAnimationFrame(f);}
  el.firstChild.nodeValue=pre+(0).toFixed(dec)+suf;requestAnimationFrame(f);});})();
"""


def _fig_band(context):
    kf = context["key_figures"]
    cells = []
    if kf["multiple"]:
        cells.append(('<span data-count="%.0f" data-suf="×">%.0f×</span>' % (kf["multiple"], kf["multiple"]),
                      "frontier vs GPT-4-class cost"))
    cells.append(('<span data-count="%d">%d</span>' % (context["model_count"], context["model_count"]), "models priced"))
    cells.append(('<span data-count="%d">%d</span>' % (kf["providers_total"], kf["providers_total"]), "providers tracked"))
    return "".join('<div class="fig"><div class="n mono">%s</div><div class="l">%s</div></div>' % (n, l) for n, l in cells[:3])


def _rate_rows(context):
    out = []
    for i, t in enumerate(context["tiers"]):
        label = TIER_LABEL.get(t["name"], t["name"])
        spread = f'{t["spread"]:.1f}×' if t["spread"] is not None else "—"
        chg = t.get("change_pct")
        if chg is None:
            chg_html = ""
        elif abs(chg) < 0.05:
            chg_html = f'<div class="chg" style="color:{SOFT}">flat dod</div>'
        else:
            col, arr = (DOWN, "▼") if chg < 0 else (UP, "▲")
            chg_html = f'<div class="chg" style="color:{col}">{arr} {abs(chg):.1f}% dod</div>'
        spark = t.get("spark_svg", "")
        cheapest = _short_model(t["cheapest_model"]) if t["cheapest_model"] else "—"
        out.append(f"""
      <div class="rate rise" style="animation-delay:{0.14+i*0.07:.2f}s">
        <div><div class="name">{label}</div><div class="gate">{context['benchmark']} &ge; {t['threshold']}</div></div>
        <div><div class="price"><span class="mono" data-count="{t['value_usd_per_mtok']:.3f}" data-dec="3" data-pre="$">${t['value_usd_per_mtok']:.3f}</span><u>/Mtok</u></div>{chg_html}</div>
        <div>{spark}</div>
        <div class="detail">cheapest <span class="m">{cheapest}</span><br><b>{t['n_qualifying']}</b> models &middot; <b>{t['provider_count']}</b> providers &middot; spread <b>{spread}</b></div>
      </div>""")
    return "".join(out)


def render_html(context, frontier_svg, distribution_svg, trend_svg):
    trend = (f'<figure class="rise">{trend_svg}<figcaption>LLMflation &mdash; cheapest price to hold each tier, over time</figcaption></figure>'
             if trend_svg else
             '<p class="note rise">The LLMflation trend line fills in as daily snapshots accrue.</p>')
    dist = (f'<figure class="rise">{distribution_svg}<figcaption>Price dispersion &mdash; what every provider charges, by capability tier</figcaption></figure>'
            if distribution_svg else "")
    onchain = ""
    if context["onchain"]:
        a = context["onchain"]["address"]
        onchain = f"""
  <div class="seal rise">
    <span class="l">Published on-chain &middot; Base Sepolia &middot; readable by any contract</span>
    <a href="{context['onchain']['explorer_url']}">{a}</a></div>"""
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beacon &mdash; the reference rate for AI inference</title>
<meta name="description" content="What AI inference actually costs: a capability-normalized price reference rate across every major model, as of {context['as_of']}.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS.replace("__GRAIN__", _GRAIN)}</style></head>
<body><div class="wrap">
  <header class="mast rise"><div class="wordmark">Beacon</div><div class="tag">The Reference Rate<br>for AI Inference</div></header>
  <div class="edition rise" style="animation-delay:.06s">
    <span><span class="dot"></span>As of {context['as_of']}</span>
    <span>{context['model_count']} models</span>
    <span>{context['key_figures']['providers_total']} providers</span>
    <span>Methodology v{context['methodology_version']}</span></div>

  <h1 class="lede rise" style="animation-delay:.1s">What a unit of intelligence costs.</h1>
  <p class="standfirst rise" style="animation-delay:.14s">The cheapest price to reach a fixed AI capability &mdash; not a raw average that only falls &mdash; measured across every major provider and published as a neutral reference rate.</p>

  <div class="figures rise" style="animation-delay:.18s">{_fig_band(context)}</div>

  <div class="kicker rise">Today's rates &middot; $/million tokens</div>
  <section class="rates">{_rate_rows(context)}</section>

  <figure class="rise">{frontier_svg}<figcaption>Price &times; capability frontier &mdash; cheapest $/Mtok to reach each level today</figcaption></figure>
  {dist}
  {trend}

  <h2 class="rise">How it's measured</h2>
  <p class="prose rise">Beacon is a <em>capability-normalized</em> index. Rather than averaging sticker prices &mdash; which only fall and hide what you actually get &mdash; it tracks the lowest $/million-tokens to reach a fixed capability tier (scored on {context['benchmark']}) across every major model. The construction is rules-based, reproducible, and transparent, the way credible commodity and rate benchmarks are built.</p>
  {onchain}
  <footer><span>Beacon &middot; Neutral reference rate for AI inference</span><span>Capability-normalized &middot; Rules-based &middot; Reproducible</span></footer>
</div><script>{JS}</script></body></html>
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

    # time-derived per-tier fields (change + sparkline) from full history
    all_snaps = [(json.loads(p.read_text())["observed_at"], json.loads(p.read_text())["listings"]) for p in snaps]
    by_thr = {thr: plot.iso_quality_series(all_snaps, cap, context["benchmark"], thr)
              for _, thr in feeds.DEFAULT_TIERS}
    for t in context["tiers"]:
        s = by_thr.get(t["threshold"], [])
        t["change_pct"] = pct_change(s)
        t["spark_svg"] = _sparkline(s)

    pts = plot.scored_points(snapshot["listings"], cap, context["benchmark"])
    cmin, cmax = int(min(c for _, c, _ in pts)), int(max(c for _, c, _ in pts))
    frontier = plot.frontier_curve(snapshot["listings"], cap, context["benchmark"], list(range(cmin, cmax + 1, 5)))
    frontier_svg = _frontier_svg(pts, frontier, context["benchmark"], context["tiers"])
    distribution_svg = _distribution_svg(context["tiers"])
    trend_svg = _trend_svg({name: by_thr[thr] for name, thr in feeds.DEFAULT_TIERS})

    SITE_DIR.mkdir(exist_ok=True)
    # index.json = the public data feed (drop inline SVGs; add raw chart series)
    public = {**context, "tiers": [{k: v for k, v in t.items() if k != "spark_svg"} for t in context["tiers"]]}
    public["charts"] = {
        "scatter": [{"model": m, "capability": c, "price": p} for m, c, p in pts],
        "frontier": [[t, v] for t, v in frontier],
        "trend": {name: by_thr[thr] for name, thr in feeds.DEFAULT_TIERS},
    }
    (SITE_DIR / "index.html").write_text(render_html(context, frontier_svg, distribution_svg, trend_svg))
    (SITE_DIR / "index.json").write_text(json.dumps(public, indent=2))
    print(f"Wrote dashboard ({len(context['tiers'])} tiers, as of {context['as_of']}, "
          f"trend={'yes' if trend_svg else 'pending'}, dist={'yes' if distribution_svg else 'no'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
