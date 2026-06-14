// Daily on-chain heartbeat through the ECONOMICALLY-SECURED oracle (v2).
// Replaces the single-publisher v1 path in the autonomous collector: posts the
// python-computed index to BeaconOracleV2 as the treasury publisher, finalizes
// each round (publishes the stake-weighted median + refreshes `updatedAt` as a
// liveness heartbeat consumers check), and reads back to confirm.
//
// Self-heals eligibility: if this wallet isn't yet an eligible publisher it
// self-stakes the minimum first (treasury holds the BEACON supply on testnet).
// Idempotent + lag-tolerant: safe to re-run; tolerates public-RPC read-after-write lag.
//   set -a && . ./.env && set +a && node_modules/.bin/hardhat run scripts/publish-daily-v2.js --network baseSepolia
const hre = require("hardhat");
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, "..", f), "utf8")).address;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const ethers = hre.ethers;
  const [me] = await ethers.getSigners();
  const staking = await ethers.getContractAt("BeaconStaking", read("staking-deployed.json"));
  const oracle = await ethers.getContractAt("BeaconOracleV2", read("oracle-v2-deployed.json"));

  // 1) Ensure this wallet is an eligible publisher (self-stake the minimum once).
  if (!(await staking.isEligiblePublisher(me.address))) {
    const min = await staking.MIN_PUBLISHER_STAKE();
    const token = await ethers.getContractAt("BeaconToken", await staking.beacon());
    console.log(`Not eligible yet — self-staking ${ethers.formatUnits(min, 18)} BEACON to qualify...`);
    await (await token.approve(await staking.getAddress(), min)).wait();
    await (await staking.selfStake(min)).wait();
    for (let i = 0; i < 6 && !(await staking.isEligiblePublisher(me.address)); i++) await sleep(3000);
  }

  // 2) Post every feed, then finalize its round (single-publisher quorum is met,
  //    so the median is just our value — finalize publishes it + stamps updatedAt).
  const payload = JSON.parse(execSync("python3 -m beacon.feeds", { cwd: REPO_ROOT }).toString());
  console.log(`Publishing ${payload.feeds.length} feeds to oracle ${await oracle.getAddress()} as ${me.address}`);
  for (const f of payload.feeds) {
    const id = ethers.id(f.feed); // keccak256("GPQA-Diamond:<tier>")
    const value = ethers.parseUnits(Number(f.value_usd_per_mtok).toFixed(8), 8);
    try {
      await (await oracle.postFeed(id, value)).wait();
      await (await oracle.finalizeRound(id)).wait();
      let onchain = 0n;
      for (let i = 0; i < 6 && onchain === 0n; i++) {
        [onchain] = await oracle.latestValue(id);
        if (onchain === 0n) await sleep(3000);
      }
      const ok = onchain === value ? "OK" : `published=${onchain} (lag; expected ${value})`;
      console.log(`  ${ok} ${f.feed}: $${f.value_usd_per_mtok}/Mtok -> ${value}`);
    } catch (e) {
      console.error(`  FAILED ${f.feed}: ${e.message}`);
    }
  }
  console.log("Done — v2 feeds refreshed (stake-weighted median, auto-slash on deviation).");
}

main().catch((e) => { console.error(e.message || e); process.exit(1); });
