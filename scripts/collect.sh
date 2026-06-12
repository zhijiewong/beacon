#!/bin/bash
# Beacon daily price collector — invoked by launchd (com.beacon.collector).
# Fetches live OpenRouter prices and writes data/snapshots/<UTC-date>.json.
# Safe to run repeatedly: re-running on the same day refreshes that day's snapshot.
set -euo pipefail

PROJECT="/Users/yvon.zhu/Developer/beacon"
PYTHON="/usr/bin/python3"
GIT="/usr/bin/git"
NODE_BIN="/opt/homebrew/bin"   # so launchd's minimal PATH can find node/hardhat
LOG="$PROJECT/logs/collector.log"

cd "$PROJECT"
echo "[$(date -u +%FT%TZ)] collect: start" >> "$LOG"
if "$PYTHON" -m beacon.collector >> "$LOG" 2>&1; then
  echo "[$(date -u +%FT%TZ)] collect: ok" >> "$LOG"
else
  echo "[$(date -u +%FT%TZ)] collect: FAILED (exit $?)" >> "$LOG"
  exit 1
fi

# --- Back up new snapshots to GitHub. Non-fatal: a push/commit problem must
# never fail the collection. Scoped to data/snapshots so it never auto-commits
# code you're editing. Unpushed commits are retried on the next run. ---
if [ -n "$("$GIT" status --porcelain data/snapshots)" ]; then
  "$GIT" add data/snapshots >> "$LOG" 2>&1 || true
  if "$GIT" commit -q -m "data: snapshot $(date -u +%F)" >> "$LOG" 2>&1; then
    if "$GIT" push -q origin main >> "$LOG" 2>&1; then
      echo "[$(date -u +%FT%TZ)] backup: pushed" >> "$LOG"
    else
      echo "[$(date -u +%FT%TZ)] backup: push FAILED (committed locally, will retry)" >> "$LOG"
    fi
  fi
else
  echo "[$(date -u +%FT%TZ)] backup: no snapshot change" >> "$LOG"
fi

# --- Publish the index to the on-chain oracle (Base Sepolia). Non-fatal: an
# RPC/gas/key problem must never break collection or backup. Posts daily even if
# values are unchanged, which refreshes each feed's on-chain `updatedAt` (a
# liveness heartbeat for consumers' staleness checks). Requires onchain/.env
# (publisher key) and onchain/deployed.json (contract address). ---
ONCHAIN="$PROJECT/onchain"
if [ -f "$ONCHAIN/.env" ] && [ -f "$ONCHAIN/deployed.json" ]; then
  echo "[$(date -u +%FT%TZ)] onchain: publishing to Base Sepolia..." >> "$LOG"
  if ( cd "$ONCHAIN" \
       && set -a && . ./.env && set +a \
       && PATH="$NODE_BIN:$PATH" CI=true HARDHAT_DISABLE_TELEMETRY_PROMPT=true \
          node_modules/.bin/hardhat run scripts/publish.js --network baseSepolia ) >> "$LOG" 2>&1; then
    echo "[$(date -u +%FT%TZ)] onchain: ok" >> "$LOG"
  else
    echo "[$(date -u +%FT%TZ)] onchain: publish FAILED (non-fatal)" >> "$LOG"
  fi
else
  echo "[$(date -u +%FT%TZ)] onchain: skipped (.env or deployed.json missing)" >> "$LOG"
fi

# --- Publish the public dashboard: regenerate -> rebuild (Next.js static export)
# -> deploy to the beacon-index GitHub Pages repo. Non-fatal: a build/push problem
# must never break collection/backup/on-chain. Only deploys when files changed.
# Requires web/node_modules (npm install) and web/.deploy (clone of beacon-index). ---
WEB="$PROJECT/web"
DEPLOY="$WEB/.deploy"
if [ -d "$WEB/node_modules" ] && [ -d "$DEPLOY/.git" ]; then
  echo "[$(date -u +%FT%TZ)] dashboard: rebuilding + deploying..." >> "$LOG"
  if (
    cd "$PROJECT"
    "$PYTHON" -m beacon.site >/dev/null
    cp site/index.json "$WEB/data/index.json"
    cd "$WEB"
    PATH="$NODE_BIN:$PATH" BASE_PATH=/beacon-index CI=true npm run build >/dev/null
    touch out/.nojekyll
    /usr/bin/rsync -a --delete --exclude='.git' out/ "$DEPLOY/"
    cd "$DEPLOY"
    "$GIT" add -A
    if ! "$GIT" diff --cached --quiet; then
      "$GIT" commit -q -m "dashboard: $(date -u +%F)"
      "$GIT" push -q origin main
    fi
  ) >> "$LOG" 2>&1; then
    echo "[$(date -u +%FT%TZ)] dashboard: ok" >> "$LOG"
  else
    echo "[$(date -u +%FT%TZ)] dashboard: FAILED (non-fatal)" >> "$LOG"
  fi
else
  echo "[$(date -u +%FT%TZ)] dashboard: skipped (web/node_modules or web/.deploy missing)" >> "$LOG"
fi
