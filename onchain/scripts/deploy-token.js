// Deploy BeaconToken (BEACON). Testnet only — treasury = deployer for now;
// distribution (points -> airdrop) is deferred until traction.
//   npx hardhat run scripts/deploy-token.js --network baseSepolia
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const ethers = hre.ethers;
  const [deployer] = await ethers.getSigners();
  console.log(`Deploying BeaconToken as ${deployer.address} on ${hre.network.name} (treasury = deployer)`);

  const token = await (await ethers.getContractFactory("BeaconToken")).deploy(deployer.address);
  await token.waitForDeployment();
  const address = await token.getAddress();
  console.log("BeaconToken deployed at:", address);

  // Record the address BEFORE any state read (public RPC lags after deploy).
  const out = path.join(__dirname, "..", "token-deployed.json");
  fs.writeFileSync(out, JSON.stringify({ network: hre.network.name, address, treasury: deployer.address }, null, 2));
  console.log("Wrote", out);

  // Verify supply, tolerating read-after-write lag on load-balanced nodes.
  let supply = 0n;
  for (let i = 0; i < 6; i++) {
    try { supply = await token.totalSupply(); } catch (_) {}
    if (supply > 0n) break;
    await new Promise((r) => setTimeout(r, 3000));
  }
  console.log("Total supply:", ethers.formatUnits(supply, 18), "BEACON -> treasury", deployer.address);
}

main().catch((e) => { console.error(e); process.exit(1); });
