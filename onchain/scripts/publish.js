// Publish the latest Beacon index to the on-chain oracle, then read it back.
// Reads feed values from the Python pipeline (`python3 -m beacon.feeds`) so the
// off-chain index stays the single source of truth. Non-fatal per feed.
//
//   npx hardhat run scripts/publish.js --network localhost
//   npx hardhat run scripts/publish.js --network baseSepolia
const hre = require("hardhat");
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..");

function loadFeeds() {
  const raw = execSync("python3 -m beacon.feeds", { cwd: REPO_ROOT }).toString();
  return JSON.parse(raw);
}

function loadDeployed() {
  const p = path.join(__dirname, "..", "deployed.json");
  if (!fs.existsSync(p)) throw new Error("deployed.json missing — run deploy.js first");
  return JSON.parse(fs.readFileSync(p));
}

async function main() {
  const ethers = hre.ethers;
  const payload = loadFeeds();
  const { address } = loadDeployed();
  const oracle = await ethers.getContractAt("BeaconOracle", address);

  // methodology "0.1" -> integer hundredths (10), snapshot date -> bytes8.
  const mver = Math.round(parseFloat(payload.methodology_version) * 100);
  const date = ethers.hexlify(ethers.toUtf8Bytes(payload.snapshot_date)); // 8 ascii bytes

  console.log(`Publishing ${payload.feeds.length} feeds to ${address} on ${hre.network.name}`);
  for (const f of payload.feeds) {
    const id = ethers.id(f.feed);
    const value = ethers.parseUnits(Number(f.value_usd_per_mtok).toFixed(8), 8);
    try {
      const tx = await oracle.postFeed(id, value, mver, date);
      await tx.wait();
      // Read back and verify. Public RPCs are load-balanced, so a read right
      // after a write can hit a lagging node; retry a few times before failing.
      let onchain = 0n;
      let ok = false;
      for (let attempt = 0; attempt < 6 && !ok; attempt++) {
        onchain = (await oracle.getFeed(id)).value;
        ok = onchain === value;
        if (!ok) await new Promise((r) => setTimeout(r, 2000));
      }
      console.log(
        `  ${ok ? "OK " : "MISMATCH"} ${f.feed}: $${f.value_usd_per_mtok.toFixed(6)}/Mtok ` +
        `-> ${value} (on-chain ${onchain})  tx ${tx.hash}`
      );
    } catch (e) {
      console.error(`  FAILED ${f.feed}: ${e.message}`);
    }
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
