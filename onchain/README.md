# Beacon on-chain oracle (Phase 2, sub-project A)

A minimal, push-based price oracle: the off-chain Beacon index (Python) is posted to
`BeaconOracle.sol` so contracts/agents can read the rate on-chain. **Testnet only — not
audited. Do not point a real-funds key at this.** See `../docs/phase2-onchain-oracle-design.md`.

## Live deployment (Base Sepolia testnet)
- **Contract:** `0xD3676E36b645883E1554489A1F9D2860ce6e4997`
- **Explorer:** https://sepolia.basescan.org/address/0xD3676E36b645883E1554489A1F9D2860ce6e4997
- Read a feed: `getFeed(keccak256("GPQA-Diamond:frontier"))` → value in 8-decimal $/Mtok.
  (Redeploys produce a new address; `deployed.json` holds the latest.)

## Setup
```bash
cd onchain
npm install
```

## Test (local, free, no wallet)
```bash
npm test                              # Hardhat unit tests (54) — all contracts
forge test --match-path "test/foundry/*"   # Foundry invariant/fuzz tests for the staking vault
```
Unit tests (Hardhat/Chai) check specific behaviors; the Foundry suite fuzzes random
stake/unstake/withdraw/slash sequences and asserts the vault stays **solvent** and stakers
can never collectively **over-claim** their pool. Foundry config is `foundry.toml`; it shares
`contracts/` but keeps its own `out-foundry/`/`cache_forge/` so it never clashes with Hardhat.
Install Foundry once (`brew install foundry`) and `forge-std` (`git clone --depth 1
https://github.com/foundry-rs/forge-std lib/forge-std`).

## End-to-end local demo (free, no wallet)
Quickest — one in-process run that deploys, posts the real index, and verifies read-back:
```bash
npx hardhat run scripts/demo.js
```
Or against a persistent local chain (mirrors the Base Sepolia flow):
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
