// Transfer owner of BeaconStaking + BeaconOracleV2 to a multisig (Ownable2Step phase A).
// Sets pendingOwner; the new owner (Safe) must then call acceptOwnership() itself.
// See docs/ownership-transfer-runbook.md.
//
//   # status only (read-only):
//   set -a && . ./.env && set +a && node_modules/.bin/hardhat run scripts/transfer-ownership.js --network baseSepolia
//   # propose the handoff:
//   NEW_OWNER=0xSafe... node_modules/.bin/hardhat run scripts/transfer-ownership.js --network baseSepolia
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, "..", f), "utf8")).address;

async function main() {
  const ethers = hre.ethers;
  const targets = [
    ["BeaconStaking", read("staking-deployed.json")],
    ["BeaconOracleV2", read("oracle-v2-deployed.json")],
  ];
  const newOwner = process.env.NEW_OWNER;

  for (const [name, addr] of targets) {
    const c = await ethers.getContractAt(name, addr);
    const [owner, pending] = [await c.owner(), await c.pendingOwner()];
    console.log(`${name} @ ${addr}\n  owner=${owner}\n  pendingOwner=${pending}`);

    if (!newOwner) continue;
    if (!ethers.isAddress(newOwner)) throw new Error(`NEW_OWNER is not an address: ${newOwner}`);
    const [me] = await ethers.getSigners();
    if (owner.toLowerCase() !== me.address.toLowerCase()) {
      console.log(`  SKIP transfer — signer ${me.address} is not the current owner`);
      continue;
    }
    const tx = await c.transferOwnership(newOwner);
    await tx.wait();
    console.log(`  transferOwnership(${newOwner}) -> pendingOwner set (tx ${tx.hash})`);
    console.log(`  NEXT: have the new owner call acceptOwnership() on ${addr}`);
  }
  if (!newOwner) console.log("\n(set NEW_OWNER=0x... to propose the handoff)");
}

main().catch((e) => { console.error(e.message || e); process.exit(1); });
