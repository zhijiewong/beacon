// One-shot LOCAL proof: deploy BeaconOracle, post the real Beacon index, and
// read every value back — all in a single in-process Hardhat network (free, no
// wallet). For persistent chains (localhost / Base Sepolia) use deploy.js + publish.js.
//
//   npx hardhat run scripts/demo.js
const hre = require("hardhat");
const { execSync } = require("child_process");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..");

async function main() {
  const ethers = hre.ethers;
  const [publisher] = await ethers.getSigners();

  console.log("Deploying BeaconOracle (in-process hardhat network)...");
  const oracle = await (await ethers.getContractFactory("BeaconOracle")).deploy();
  await oracle.waitForDeployment();
  console.log("  deployed:", await oracle.getAddress());
  console.log("  publisher:", publisher.address, "\n");

  const payload = JSON.parse(
    execSync("python3 -m beacon.feeds", { cwd: REPO_ROOT }).toString()
  );
  const mver = Math.round(parseFloat(payload.methodology_version) * 100);
  const date = ethers.hexlify(ethers.toUtf8Bytes(payload.snapshot_date));

  console.log(`Publishing ${payload.feeds.length} feeds (snapshot ${payload.snapshot_date}, methodology v${payload.methodology_version}):`);
  let allOk = true;
  for (const f of payload.feeds) {
    const id = ethers.id(f.feed);
    const value = ethers.parseUnits(Number(f.value_usd_per_mtok).toFixed(8), 8);
    await (await oracle.postFeed(id, value, mver, date)).wait();

    const onchain = await oracle.getFeed(id);
    const ok = onchain.value === value;
    allOk = allOk && ok;
    const readDate = Buffer.from(onchain.snapshotDate.slice(2), "hex").toString();
    console.log(
      `  ${ok ? "OK " : "BAD"} ${f.feed.padEnd(26)} ` +
      `$${f.value_usd_per_mtok.toFixed(6)}/Mtok  ->  on-chain ${onchain.value} (8dp)  date=${readDate}`
    );
  }

  // Show a consumer-style read (value + staleness timestamp).
  const id0 = ethers.id(payload.feeds[0].feed);
  const [v, updatedAt] = await oracle.latestValue(id0);
  console.log(`\nConsumer latestValue(${payload.feeds[0].feed}): value=${v}  updatedAt=${updatedAt}`);
  console.log(allOk ? "\nALL FEEDS VERIFIED ON-CHAIN ✓" : "\nMISMATCH DETECTED ✗");
  if (!allOk) process.exit(1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
