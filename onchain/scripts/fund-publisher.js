// Treasury helper: send a prospective publisher testnet BEACON + a little gas so they
// can register and post. Testnet only — these are valueless test tokens, NOT the gated
// mainnet distribution. Run as the treasury (the deployer key):
//   PUBLISHER_ADDRESS=0x... npx hardhat run scripts/fund-publisher.js --network baseSepolia
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, "..", f), "utf8")).address;

async function main() {
  const ethers = hre.ethers;
  const to = process.env.PUBLISHER_ADDRESS;
  if (!to || !ethers.isAddress(to)) throw new Error("set PUBLISHER_ADDRESS=0x...");

  const [treasury] = await ethers.getSigners();
  const token = await ethers.getContractAt("BeaconToken", read("token-deployed.json"));
  const staking = await ethers.getContractAt("BeaconStaking", read("staking-deployed.json"));

  const min = await staking.MIN_PUBLISHER_STAKE();
  const beaconAmt = min * 2n; // enough to self-stake with a buffer
  const gas = ethers.parseEther(process.env.GAS_ETH || "0.001");

  console.log(`Funding ${to}: ${ethers.formatUnits(beaconAmt, 18)} BEACON + ${ethers.formatEther(gas)} ETH`);
  await (await token.transfer(to, beaconAmt)).wait();
  await (await treasury.sendTransaction({ to, value: gas })).wait();
  console.log("funded. The publisher can now run register-publisher.js with their key.");
}

main().catch((e) => { console.error(e.message || e); process.exit(1); });
