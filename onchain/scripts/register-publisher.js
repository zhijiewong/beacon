// Become a Beacon oracle publisher: self-stake the minimum so you're eligible to post
// feeds. Run with YOUR key (a throwaway testnet key):
//   PRIVATE_KEY=0x... npx hardhat run scripts/register-publisher.js --network baseSepolia
// You need testnet BEACON first (ask the treasury to run fund-publisher.js).
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, "..", f), "utf8")).address;

async function main() {
  const ethers = hre.ethers;
  const [me] = await ethers.getSigners();
  const token = await ethers.getContractAt("BeaconToken", read("token-deployed.json"));
  const staking = await ethers.getContractAt("BeaconStaking", read("staking-deployed.json"));

  const min = await staking.MIN_PUBLISHER_STAKE();
  console.log(`Registering ${me.address} as a publisher (self-stake ${ethers.formatUnits(min, 18)} BEACON)`);

  const bal = await token.balanceOf(me.address);
  if (bal < min) {
    throw new Error(
      `insufficient BEACON: have ${ethers.formatUnits(bal, 18)}, need ${ethers.formatUnits(min, 18)} — ` +
      "get testnet BEACON first (treasury runs fund-publisher.js)"
    );
  }

  await (await token.approve(await staking.getAddress(), min)).wait();
  await (await staking.selfStake(min)).wait();

  // Verify eligibility, tolerating public-RPC read-after-write lag.
  let ok = false;
  for (let i = 0; i < 6; i++) {
    try { ok = await staking.isEligiblePublisher(me.address); } catch (_) {}
    if (ok) break;
    await new Promise((r) => setTimeout(r, 3000));
  }
  console.log("eligible publisher:", ok);
  console.log("Next: PRIVATE_KEY=… npx hardhat run scripts/publish-to-oracle-v2.js --network baseSepolia");
}

main().catch((e) => { console.error(e.message || e); process.exit(1); });
