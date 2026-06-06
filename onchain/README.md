# Beacon on-chain oracle (Phase 2, sub-project A)

A minimal, push-based price oracle: the off-chain Beacon index (Python) is posted to
`BeaconOracle.sol` so contracts/agents can read the rate on-chain. **Testnet only — not
audited. Do not point a real-funds key at this.** See `../docs/phase2-onchain-oracle-design.md`.

## Setup
```bash
cd onchain
npm install
```

## Test (local, free, no wallet)
```bash
npm test            # Hardhat unit tests for BeaconOracle
```

## End-to-end local demo (free, no wallet)
Run a local chain, deploy, then publish the real index and read it back:
```bash
npx hardhat node &                                   # local chain on :8545
npx hardhat run scripts/deploy.js  --network localhost
npx hardhat run scripts/publish.js --network localhost   # posts python `beacon.feeds`, verifies
```

## Deploy to Base Sepolia (needs YOUR funded testnet wallet)
1. Create a throwaway wallet; get free Base Sepolia ETH from a faucet
   (e.g. Coinbase Developer Platform faucet).
2. `cp .env.example .env` and fill `PRIVATE_KEY` (and optionally `BASE_SEPOLIA_RPC`).
3. Load env and run:
   ```bash
   export $(grep -v '^#' .env | xargs)
   npx hardhat run scripts/deploy.js  --network baseSepolia
   npx hardhat run scripts/publish.js --network baseSepolia
   ```
The published rate is then readable by anyone on Base Sepolia via `getFeed(id)` /
`latestValue(id)`, where `id = keccak256("GPQA-Diamond:<tier>")`.

## How values are encoded
- `value`: USD per 1M tokens, **8-decimal fixed point** (Chainlink convention).
  `$1.368/Mtok` → `136800000`.
- `snapshotDate`: `bytes8` ASCII (e.g. `20260606`) — provenance back to a snapshot.
- `methodologyVersion`: integer hundredths (`v0.1` → `10`).
- Consumers MUST check `updatedAt` for staleness (e.g. reject > 48h old).
