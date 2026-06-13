// Deploy the reference BeaconConsumer and read the LIVE Beacon rate through it —
// the demand-side proof: an external contract settling against the on-chain feed.
// Finalizes the frontier round first if needed (permissionless) so there's a value.
//   npx hardhat run scripts/deploy-consumer.js --network baseSepolia
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, "..", f), "utf8")).address;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const ethers = hre.ethers;
  const oracle = await ethers.getContractAt("BeaconOracleV2", read("oracle-v2-deployed.json"));
  const id = ethers.id("GPQA-Diamond:frontier");
  const TWO_DAYS = 2 * 24 * 3600;

  // Make sure the feed has a published value (finalize the open round if it's quorate).
  let [val] = await oracle.latestValue(id);
  if (val === 0n) {
    const size = await oracle.roundSize(id);
    const minP = await oracle.minPublishers();
    if (size >= minP && size > 0n) {
      console.log(`Finalizing frontier round (${size} submission(s)) to publish the rate...`);
      await (await oracle.finalizeRound(id)).wait();
      for (let i = 0; i < 6 && val === 0n; i++) { [val] = await oracle.latestValue(id); if (val === 0n) await sleep(3000); }
    }
  }

  // Deploy the consumer pointed at the live oracle.
  const consumer = await (await ethers.getContractFactory("BeaconConsumer")).deploy(await oracle.getAddress(), TWO_DAYS);
  await consumer.waitForDeployment();
  const address = await consumer.getAddress();
  console.log("BeaconConsumer deployed at:", address);
  fs.writeFileSync(path.join(__dirname, "..", "consumer-deployed.json"),
    JSON.stringify({ network: hre.network.name, address, oracle: await oracle.getAddress() }, null, 2));

  // Read the live rate through the consumer, tolerating read-after-write lag.
  let rate = 0n;
  for (let i = 0; i < 6; i++) {
    try { rate = await consumer.readRate(id); } catch (e) { /* not yet visible */ }
    if (rate > 0n) break;
    await sleep(3000);
  }
  const quote = await consumer.quote(id, 1_000_000n); // settle 1,000,000 Mtok
  console.log(`Live frontier rate read on-chain via consumer: ${rate} (= $${Number(rate) / 1e8}/Mtok)`);
  console.log(`Sample settlement quote(1,000,000 Mtok): ${quote} (= $${Number(quote) / 1e8})`);
}

main().catch((e) => { console.error(e); process.exit(1); });
