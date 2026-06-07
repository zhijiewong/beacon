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
