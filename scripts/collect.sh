#!/bin/bash
# Beacon daily price collector — invoked by launchd (com.beacon.collector).
# Fetches live OpenRouter prices and writes data/snapshots/<UTC-date>.json.
# Safe to run repeatedly: re-running on the same day refreshes that day's snapshot.
set -euo pipefail

PROJECT="/Users/yvon.zhu/Developer/beacon"
PYTHON="/usr/bin/python3"
LOG="$PROJECT/logs/collector.log"

cd "$PROJECT"
echo "[$(date -u +%FT%TZ)] collect: start" >> "$LOG"
if "$PYTHON" -m beacon.collector >> "$LOG" 2>&1; then
  echo "[$(date -u +%FT%TZ)] collect: ok" >> "$LOG"
else
  echo "[$(date -u +%FT%TZ)] collect: FAILED (exit $?)" >> "$LOG"
  exit 1
fi
