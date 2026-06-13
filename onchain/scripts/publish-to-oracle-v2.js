// Post the current Beacon index to the multi-publisher oracle (v2) as YOUR publisher.
// The off-chain Python pipeline (`python3 -m beacon.feeds`) stays the single source of
// truth; feed ids are keccak256("<benchmark>:<tier>"), values are 8-decimal $/Mtok.
//   PRIVATE_KEY=0x... npx hardhat run scripts/publish-to-oracle-v2.js --network baseSepolia
const hre = require("hardhat");
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, "..", f), "utf8")).address;

async function main() {
  const ethers = hre.ethers;
  const [me] = await ethers.getSigners();
  const staking = await ethers.getContractAt("BeaconStaking", read("staking-deployed.json"));
  if (!(await staking.isEligiblePublisher(me.address))) {
    throw new Error("not an eligible publisher — run register-publisher.js first");
  }
  const oracle = await ethers.getContractAt("BeaconOracleV2", read("oracle-v2-deployed.json"));

  const payload = JSON.parse(execSync("python3 -m beacon.feeds", { cwd: REPO_ROOT }).toString());
  console.log(`Posting ${payload.feeds.length} feeds to oracle ${await oracle.getAddress()} as ${me.address}`);
  for (const f of payload.feeds) {
    const id = ethers.id(f.feed); // keccak256 of e.g. "GPQA-Diamond:frontier"
    const value = ethers.parseUnits(Number(f.value_usd_per_mtok).toFixed(8), 8);
    try {
      const tx = await oracle.postFeed(id, value);
      await tx.wait();
      console.log(`  OK ${f.feed}: $${f.value_usd_per_mtok}/Mtok -> ${value}  tx ${tx.hash}`);
    } catch (e) {
      console.error(`  FAILED ${f.feed}: ${e.message}`);
    }
  }
  console.log("Posted. Once the quorum is met, anyone can call finalizeRound(id) to publish");
  console.log("the stake-weighted median and slash any publisher that deviated beyond tolerance.");
}

main().catch((e) => { console.error(e.message || e); process.exit(1); });
