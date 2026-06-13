# Becoming a Beacon Publisher (testnet)

> **Status:** Base Sepolia testnet, **unaudited**. The BEACON you stake here is a
> valueless test token and rewards aren't funded yet — this is for trying out the
> publisher role and helping turn the multi-publisher oracle into a real feed, not for
> earning. Do **not** use a key that holds real funds.

## What a publisher is

A Beacon publisher stakes BEACON to back the accuracy of the price feeds it posts. Each
round, eligible publishers submit a value per feed; `BeaconOracleV2.finalizeRound`
aggregates them by a **stake-weighted median** and publishes it on-chain. The point of the
stake is skin in the game:

- **Reward:** publishers (and their delegators) earn a share of protocol rewards, paid in a
  stablecoin, pro-rata to stake. *(Reward distribution exists on-chain but isn't funded on
  testnet.)*
- **Risk:** if your submission deviates beyond the tolerance (`maxDeviationBps`, default
  **10%**) from the round's median, your pool is **slashed** (`deviationSlashBps`, default
  **5%**). Honest, in-line submissions are never touched.
- **Eligibility:** you must self-stake at least `MIN_PUBLISHER_STAKE` (**1000 BEACON**).

The off-chain index is the single source of truth: `python3 -m beacon.feeds` computes the
per-tier values; you post those. Feed ids are `keccak256("<benchmark>:<tier>")`, e.g.
`keccak256("GPQA-Diamond:frontier")` — in ethers, `ethers.id("GPQA-Diamond:frontier")`.

Current feeds (from `data/tiers.json`):

| Feed string | Tier |
|-------------|------|
| `GPQA-Diamond:frontier` | top capability |
| `GPQA-Diamond:strong` | strong |
| `GPQA-Diamond:gpt-4-class` | GPT-4-class |

Live contract addresses are the source of truth in `onchain/*-deployed.json` (and shown on
the dashboard's "Secured on-chain" section); they change when contracts are redeployed.

## Prerequisites

- Node + the repo's `onchain/` deps installed (`npm install` in `onchain/`).
- A **throwaway** testnet wallet (private key).
- Testnet **BEACON** (to stake) and a little **Base Sepolia ETH** (for gas). Ask the
  treasury to fund you (below), or use a Base Sepolia faucet for ETH.

## Steps

### 0. (Treasury) Fund a prospective publisher
The treasury sends testnet BEACON + gas so a new publisher can start:
```bash
cd onchain
set -a && . ./.env && set +a                     # treasury/deployer key
PUBLISHER_ADDRESS=0xYourPublisher \
  npx hardhat run scripts/fund-publisher.js --network baseSepolia
```

### 1. Register (self-stake)
Run with **your** publisher key:
```bash
cd onchain
PRIVATE_KEY=0xYourPublisherKey \
  npx hardhat run scripts/register-publisher.js --network baseSepolia
# -> "eligible publisher: true"
```

### 2. Post the index
```bash
cd onchain
PRIVATE_KEY=0xYourPublisherKey \
  npx hardhat run scripts/publish-to-oracle-v2.js --network baseSepolia
# posts one submission per feed for the current snapshot
```

### 3. Finalize (anyone, once the quorum is met)
Finalizing aggregates the round's submissions into the published median and slashes any
deviators. It's permissionless and quorum-gated (`minPublishers`):
```bash
# in a script / console:  oracle.finalizeRound(ethers.id("GPQA-Diamond:frontier"))
```

## Exiting

`requestUnstake(publisher, amount)` starts a **7-day** cooldown, then `withdraw(publisher)`
returns your tokens. Note: stake that is unbonding **remains slashable** during the
cooldown — you can't dodge a pending slash by unstaking.

## Honest caveats

- Testnet only; contracts are **unaudited** — a professional audit is required before any
  mainnet/real value.
- Rewards aren't funded on testnet, so there's no yield yet; this is about exercising the
  role and helping the feed reach a real multi-publisher quorum.
- Mainnet token **distribution stays gated on real traction** — testnet BEACON is not a
  claim on anything.
