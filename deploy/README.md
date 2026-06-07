# Deploy — daily collection (macOS launchd)

The daily price collector runs via a macOS **launchd** user agent. This folder keeps
a reference copy of the agent definition so the setup is reproducible.

> **Why the project lives in `~/Developer` and not `~/Documents`:** `~/Documents` is
> TCC-protected, so launchd/cron background jobs get "Operation not permitted" there.
> `~/Developer` is not protected. Keep this project outside `~/Documents`.

## Install
```bash
# 1. Copy the agent into LaunchAgents (paths inside assume ~/Developer/beacon)
cp deploy/com.beacon.collector.plist ~/Library/LaunchAgents/

# 2. Load it
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.beacon.collector.plist

# 3. (optional) run once now to verify
launchctl kickstart -k gui/$(id -u)/com.beacon.collector
tail -3 logs/collector.log
```

It runs `scripts/collect.sh` daily at **12:00 local**, which does three things, each non-fatal so a
later step's failure never breaks an earlier one:
1. **Collect** — write `data/snapshots/<UTC-date>.json`.
2. **Back up** — auto-commit & push any new snapshot to `origin/main` (scoped to `data/snapshots/`,
   so it never commits code you're editing; auth via `osxkeychain`, no `gh` needed).
3. **Publish on-chain** — post the index to the `BeaconOracle` on Base Sepolia (refreshes each feed's
   `updatedAt` as a liveness heartbeat). Requires `onchain/.env` + `onchain/deployed.json`; skipped if
   absent. `node` is found via `NODE_BIN=/opt/homebrew/bin` (launchd's PATH is minimal).

## Manage
```bash
launchctl print gui/$(id -u)/com.beacon.collector | grep -i "last exit\|state ="  # status
launchctl kickstart -k gui/$(id -u)/com.beacon.collector                          # run now
launchctl bootout gui/$(id -u)/com.beacon.collector                               # stop/uninstall
```

## If you move the project
The plist hardcodes absolute paths (`/Users/<you>/Developer/beacon/...`). After moving,
update `scripts/collect.sh` (the `PROJECT=` line) and every path in the plist, then
`bootout` and `bootstrap` again.
