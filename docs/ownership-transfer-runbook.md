# Ownership transfer runbook — EOA → multisig (+ timelock)

> Moves `owner` of `BeaconStaking` and `BeaconOracleV2` from the single deploy EOA to a
> multisig (Safe), closing security-review **Finding 8** (single-key owner). Both contracts use
> **OpenZeppelin `Ownable2Step`**, so the handoff is two-phase and safe against fat-fingering.
> Do this independent of (and ideally before) the audit. Testnet first, then mainnet.

## Why
The owner can `slash` (≤5%), `pause`, set the slasher, distribute rewards, set params, and
`rescueTokens`. On one EOA that's a single point of compromise. A 2-of-3 / 3-of-5 Safe (later
behind a timelock) removes it.

## What `owner` controls (so the Safe inherits these)
- `BeaconStaking`: `slash`, `pause`/`unpause`, `setSlasher`, `setRewardToken` (once),
  `setMaxRewardPerEpoch`, `setSlashTreasury`, `distributeRewards`, `rescueTokens`.
- `BeaconOracleV2`: `setMinPublishers`, `setMaxDeviationBps`, `setDeviationSlashBps`,
  `setMaxStaleness`, `setMaxPublishersPerRound`.
- The `slasher` role (the oracle) is separate and unaffected — deviation slashing keeps working.

## Steps

### 1. Create the Safe
- Deploy a **Safe** (safe.global) on Base with your chosen signers (e.g. 2-of-3) and **the same
  Safe address on Base Sepolia and Base mainnet** if you can (deterministic deploy) — simplifies ops.
- Fund it with a little ETH for gas.

### 2. Transfer ownership (Ownable2Step — two phases)
For **each** contract (staking, then oracle):

**Phase A — current EOA proposes** (run the helper; it only calls `transferOwnership`):
```bash
cd onchain
set -a && . ./.env && set +a            # the current-owner EOA key
NEW_OWNER=0xYourSafeAddress \
  node_modules/.bin/hardhat run scripts/transfer-ownership.js --network baseSepolia
```
This calls `transferOwnership(safe)` on both contracts and sets `pendingOwner`. **Ownership has
NOT moved yet** — the EOA is still owner until the Safe accepts.

**Phase B — the Safe accepts** (from the Safe UI, one transaction per contract):
- New transaction → To: `<contract address>` → Contract interaction → method **`acceptOwnership()`**
  (no args) → collect signatures → execute.
- Do it for **both** `BeaconStaking` and `BeaconOracleV2`.

### 3. Verify
```bash
# owner() should be the Safe; pendingOwner() should be the zero address
node_modules/.bin/hardhat run scripts/transfer-ownership.js --network baseSepolia   # prints current state when NEW_OWNER unset
```
Confirm on BaseScan: `owner()` == Safe, `pendingOwner()` == `0x0` for both contracts.

### 4. (Recommended) Add a timelock later
For mainnet, put a **TimelockController** between the Safe and the contracts (Safe owns the
timelock; timelock owns the contracts) so privileged changes have a public delay. Exception: keep
an **emergency path for `pause`/`slash`** that isn't delayed, or the timelock defeats the security
response — give the Safe a direct fast lane for those, timelock the rest. Decide this with the auditor.

## Rollback / safety notes
- Because it's `Ownable2Step`, a wrong `NEW_OWNER` is **recoverable** before acceptance: the EOA
  just calls `transferOwnership` again with the right address (overwrites `pendingOwner`).
- Don't transfer to an address you don't fully control — there is **no recovery after the Safe
  accepts** except the Safe itself transferring back.
- Do the **whole flow on Base Sepolia first** and confirm you can execute a Safe `acceptOwnership`
  and a sample owner action (e.g. `setMaxStaleness`) before repeating on mainnet.
