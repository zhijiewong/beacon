// Deploy BeaconStaking (Oracle Integrity Staking) bound to the deployed BEACON token.
// Testnet only — unaudited; no real value. Reward token (USDC) is set post-deploy by
// governance via setRewardToken once a testnet USDC is chosen.
//   npx hardhat run scripts/deploy-staking.js --network baseSepolia
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const ethers = hre.ethers;
  const [deployer] = await ethers.getSigners();

  // BEACON token address from the prior deploy.
  const tokenFile = path.join(__dirname, "..", "token-deployed.json");
  const beacon = JSON.parse(fs.readFileSync(tokenFile, "utf8")).address;
  console.log(`Deploying BeaconStaking as ${deployer.address} on ${hre.network.name}`);
  console.log(`  beacon token: ${beacon}`);

  const staking = await (await ethers.getContractFactory("BeaconStaking")).deploy(beacon);
  await staking.waitForDeployment();
  const address = await staking.getAddress();
  console.log("BeaconStaking deployed at:", address);

  // Record the address BEFORE any state read (public RPC lags after deploy).
  const out = path.join(__dirname, "..", "staking-deployed.json");
  fs.writeFileSync(out, JSON.stringify({ network: hre.network.name, address, beacon, owner: deployer.address }, null, 2));
  console.log("Wrote", out);

  // Verify the binding, tolerating read-after-write lag on load-balanced nodes.
  let bound = "";
  for (let i = 0; i < 6; i++) {
    try { bound = await staking.beacon(); } catch (_) {}
    if (bound && bound !== ethers.ZeroAddress) break;
    await new Promise((r) => setTimeout(r, 3000));
  }
  console.log("Bound BEACON token:", bound, bound.toLowerCase() === beacon.toLowerCase() ? "(ok)" : "(MISMATCH — retry read)");
  console.log("MIN_PUBLISHER_STAKE / MAX_SLASH_BPS / MAX_FEE_BPS are constants in the contract.");
}

main().catch((e) => { console.error(e); process.exit(1); });
