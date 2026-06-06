// Deploy BeaconOracle to the selected --network and record the address.
// Works for local (`localhost`) and Base Sepolia (`baseSepolia`).
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const ethers = hre.ethers;
  const [deployer] = await ethers.getSigners();
  console.log(`Deploying BeaconOracle as ${deployer.address} on ${hre.network.name}`);

  const Oracle = await ethers.getContractFactory("BeaconOracle");
  const oracle = await Oracle.deploy();
  await oracle.waitForDeployment();
  const address = await oracle.getAddress();
  console.log("BeaconOracle deployed at:", address);

  const out = path.join(__dirname, "..", "deployed.json");
  fs.writeFileSync(
    out,
    JSON.stringify({ network: hre.network.name, address }, null, 2)
  );
  console.log("Wrote", out);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
