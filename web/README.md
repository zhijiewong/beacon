# Beacon web — Next.js + Tremor dashboard

The public dashboard, rebuilt on Next.js (App Router) + Tremor + Tailwind, themed
to the "almanac" aesthetic (Instrument Serif + IBM Plex Mono/Sans, paper/ink/vermilion).
Static-exported so it hosts free on GitHub Pages / Cloudflare / Netlify.

Data comes from `data/index.json`, produced by the Python pipeline
(`python3 -m beacon.site`). Refresh it with `npm run sync-data`.

## Develop
```bash
cd web
npm install            # run in a real shell (large install)
npm run sync-data      # copy ../site/index.json -> data/index.json
npm run dev            # http://localhost:3000
```

## Build (static export -> web/out/)
```bash
npm run build          # emits web/out/ (static HTML/CSS/JS)
```
For a project Pages site under a repo path, build with the repo name as base path:
```bash
BASE_PATH=/beacon-index npm run build
```
Then serve / deploy `web/out/` (GitHub Pages, Cloudflare Pages, Netlify, or `npx serve out`).

## What's Tremor vs custom
- **Tremor:** the interactive LLMflation `AreaChart` (hover tooltips, legend).
- **Custom SVG (ported from the Python charts):** the annotated price-capability
  frontier and the price-dispersion dot-plot — bespoke views Tremor doesn't ship.
- **Tailwind theme** remaps Tremor's tokens onto the paper/ink palette so nothing
  reverts to the default blue-SaaS look.
