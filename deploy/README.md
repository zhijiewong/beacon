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

It runs `scripts/collect.sh` daily at **12:00 local**, writing `data/snapshots/<UTC-date>.json`.

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
