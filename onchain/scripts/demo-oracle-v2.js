// Live end-to-end demo of BeaconOracleV2 on Base Sepolia: stand up 3 publishers,
// have them submit, finalize, and show the median publish + deviation auto-slash.
// Funds two throwaway publisher wallets with a little gas + BEACON from the deployer.
// Testnet only — synthetic publishers for demonstration.
//   npx hardhat run scripts/demo-oracle-v2.js --network baseSepolia
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

const fmt = (x) => hre.ethers.formatUnits(x, 18);
const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, "..", f), "utf8")).address;

async function waitFor(fn, ok, tries = 8, ms = 3000) {
  let v;
  for (let i = 0; i < tries; i++) {
    try { v = await fn(); } catch (_) {}
    if (ok(v)) return v;
    await new Promise((r) => setTimeout(r, ms));
  }
  return v;
}

async function main() {
  const ethers = hre.ethers;
  const [deployer] = await ethers.getSigners();
  const tokenAddr = read("token-deployed.json");
  const stakingAddr = read("staking-deployed.json");
  const oracleAddr = read("oracle-v2-deployed.json");

  const token = await ethers.getContractAt("BeaconToken", tokenAddr);
  const staking = await ethers.getContractAt("BeaconStaking", stakingAddr);
  const oracle = await ethers.getContractAt("BeaconOracleV2", oracleAddr);

  const E18 = 10n ** 18n;
  const MIN = 1000n * E18;
  const ID = ethers.encodeBytes32String("frontier");

  // p1 = deployer (already holds BEACON). p2,p3 = fresh throwaway wallets.
  const p2 = ethers.Wallet.createRandom().connect(ethers.provider);
  const p3 = ethers.Wallet.createRandom().connect(ethers.provider);
  console.log("publishers:", deployer.address, p2.address, p3.address);

  // Fund p2,p3 with a little gas + BEACON, and stake each to MIN so they're eligible.
  for (const p of [p2, p3]) {
    await (await deployer.sendTransaction({ to: p.address, value: ethers.parseEther("0.0008") })).wait();
    await (await token.transfer(p.address, MIN)).wait();
    await (await token.connect(p).approve(stakingAddr, MIN)).wait();
    await (await staking.connect(p).selfStake(MIN)).wait();
  }
  // deployer self-stakes too (needs approve first).
  await (await token.approve(stakingAddr, MIN)).wait();
  await (await staking.selfStake(MIN)).wait();
  console.log("all three eligible:",
    await staking.isEligiblePublisher(deployer.address),
    await staking.isEligiblePublisher(p2.address),
    await staking.isEligiblePublisher(p3.address));

  // Submissions: p1=100, p2=101 (honest), p3=200 (way off -> should be slashed).
  await (await oracle.postFeed(ID, 100)).wait();
  await (await oracle.connect(p2).postFeed(ID, 101)).wait();
  await (await oracle.connect(p3).postFeed(ID, 200)).wait();
  const med = await waitFor(() => oracle.median(ID), (v) => v && v > 0n);
  console.log("round median (pre-finalize):", med.toString());

  const p3Before = await staking.poolStake(p3.address);
  await (await oracle.finalizeRound(ID)).wait();

  const [agg, at] = await waitFor(() => oracle.latestValue(ID), (r) => r && r[0] > 0n);
  console.log(`published aggregate: ${agg} @ ${at}`);
  const p3After = await waitFor(() => staking.poolStake(p3.address), (v) => v !== undefined && v < p3Before);
  console.log(`p3 pool stake: ${fmt(p3Before)} -> ${fmt(p3After)} BEACON  (slashed: ${p3Before > p3After})`);
  console.log(`p1 pool stake: ${fmt(await staking.poolStake(deployer.address))} (honest, untouched)`);
  console.log(`p2 pool stake: ${fmt(await staking.poolStake(p2.address))} (honest, untouched)`);
}

main().catch((e) => { console.error(e); process.exit(1); });
