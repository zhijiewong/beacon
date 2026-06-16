# Verifying the contracts on BaseScan (Base Sepolia)

> Publishes the contracts' source on the block explorer so anyone can read and check the
> deployed bytecode — a baseline trust signal for an oracle. ~5 minutes. The config and a
> one-shot script are ready; the only thing not automatable is the (free) explorer API key.

## One-time: get a free Etherscan API key

BaseScan verification uses the **Etherscan v2 multichain API** (one key covers Base, Base
Sepolia, Ethereum, etc.). Create a free key at https://etherscan.io/apis → "API Keys".

> Sourcify (key-free, decentralized) is also wired in `hardhat.config.js` (`sourcify.enabled`),
> but its v1 API is being deprecated/brownout'd — prefer the Etherscan key path until
> `hardhat-verify` ships v2-Sourcify support.

## Verify everything

```bash
cd onchain
set -a && . ./.env && set +a                 # PRIVATE_KEY (any throwaway is fine for reads)
export ETHERSCAN_API_KEY=YourKeyHere
node_modules/.bin/hardhat run scripts/verify-all.js --network baseSepolia
```

`verify-all.js` reads addresses + constructor args from the `*-deployed.json` records (so it
stays correct across redeploys) and verifies all four contracts. "Already Verified" counts as
success. Re-run after any redeploy.

## What it verifies (current live addresses)

| Contract | Address | Constructor args |
|----------|---------|------------------|
| BeaconToken | `0x7848eAD4459C8334854B015C49F10dFb02B5dC83` | treasury = deployer EOA |
| BeaconStaking | `0x23783C0F305dA38Ee57baE4fe507ea078Bd52602` | beacon token addr |
| BeaconOracleV2 | `0x7bA170f7e156cCCDeDcf5757233b0d65fF3C497C` | staking addr |
| BeaconConsumer | `0x60ED1326A7FCB132CFceD2C4f407cD30D8FE5ef7` | oracle addr, `172800` (2-day maxAge) |

After it succeeds, each address on https://sepolia.basescan.org shows a green "Contract"
checkmark with the full source and the ABI's read/write methods.

## Verify a single contract manually

```bash
node_modules/.bin/hardhat verify --network baseSepolia <address> <constructorArg1> <constructorArg2>
# e.g. the consumer:
node_modules/.bin/hardhat verify --network baseSepolia \
  0x60ED1326A7FCB132CFceD2C4f407cD30D8FE5ef7 \
  0x7bA170f7e156cCCDeDcf5757233b0d65fF3C497C 172800
```
