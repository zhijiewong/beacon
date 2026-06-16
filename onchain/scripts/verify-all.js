// Verify all live Beacon contracts on the configured explorer (Base Sepolia).
// Reads addresses + constructor args from the *-deployed.json records (source of
// truth), so it stays correct across redeploys. Needs ETHERSCAN_API_KEY (free
// Etherscan v2 multichain key) OR Sourcify when its v2 endpoint is reachable.
//   set -a && . ./.env && set +a && ETHERSCAN_API_KEY=... \
//     node_modules/.bin/hardhat run scripts/verify-all.js --network baseSepolia
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, "..", f), "utf8"));
const CONSUMER_MAX_AGE = 2 * 24 * 3600; // deploy-consumer.js TWO_DAYS

async function verify(name, address, constructorArguments, contract) {
  try {
    await hre.run("verify:verify", { address, constructorArguments, contract });
    console.log(`OK   ${name} @ ${address}`);
  } catch (e) {
    const msg = (e.message || String(e)).split("\n")[0];
    // "Already Verified" is success, not failure.
    console.log(`${/already verified/i.test(msg) ? "OK  " : "FAIL"} ${name} @ ${address}: ${msg}`);
  }
}

async function main() {
  const [me] = await hre.ethers.getSigners(); // the deployer == token treasury
  const token = read("token-deployed.json").address;
  const staking = read("staking-deployed.json");
  const oracle = read("oracle-v2-deployed.json");
  const consumer = read("consumer-deployed.json");

  await verify("BeaconToken", token, [me.address], "contracts/BeaconToken.sol:BeaconToken");
  await verify("BeaconStaking", staking.address, [staking.beacon], "contracts/BeaconStaking.sol:BeaconStaking");
  await verify("BeaconOracleV2", oracle.address, [oracle.staking], "contracts/BeaconOracleV2.sol:BeaconOracleV2");
  await verify("BeaconConsumer", consumer.address, [consumer.oracle, CONSUMER_MAX_AGE], "contracts/examples/BeaconConsumer.sol:BeaconConsumer");
}

main().catch((e) => { console.error(e); process.exit(1); });
