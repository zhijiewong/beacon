// Deploy BeaconOracleV2 (multi-publisher median + deviation auto-slash) and wire it
// as the authorized slasher on the live BeaconStaking. Testnet only — unaudited.
//   npx hardhat run scripts/deploy-oracle-v2.js --network baseSepolia
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const ethers = hre.ethers;
  const [deployer] = await ethers.getSigners();

  const stakingFile = path.join(__dirname, "..", "staking-deployed.json");
  const stakingAddr = JSON.parse(fs.readFileSync(stakingFile, "utf8")).address;
  console.log(`Deploying BeaconOracleV2 as ${deployer.address} on ${hre.network.name}`);
  console.log(`  staking: ${stakingAddr}`);

  const oracle = await (await ethers.getContractFactory("BeaconOracleV2")).deploy(stakingAddr);
  await oracle.waitForDeployment();
  const address = await oracle.getAddress();
  console.log("BeaconOracleV2 deployed at:", address);

  // Record BEFORE any state read (public RPC lags after deploy).
  const out = path.join(__dirname, "..", "oracle-v2-deployed.json");
  fs.writeFileSync(out, JSON.stringify({ network: hre.network.name, address, staking: stakingAddr, owner: deployer.address }, null, 2));
  console.log("Wrote", out);

  // Authorize the oracle as the staking slasher so deviation slashing can fire.
  const staking = await ethers.getContractAt("BeaconStaking", stakingAddr);
  const tx = await staking.setSlasher(address);
  await tx.wait();
  console.log("staking.setSlasher ->", address, "(tx", tx.hash + ")");

  // Verify, tolerating read-after-write lag.
  let slasher = "";
  for (let i = 0; i < 6; i++) {
    try { slasher = await staking.slasher(); } catch (_) {}
    if (slasher && slasher.toLowerCase() === address.toLowerCase()) break;
    await new Promise((r) => setTimeout(r, 3000));
  }
  console.log("staking.slasher() =", slasher, slasher.toLowerCase() === address.toLowerCase() ? "(ok)" : "(retry read)");
}

main().catch((e) => { console.error(e); process.exit(1); });
