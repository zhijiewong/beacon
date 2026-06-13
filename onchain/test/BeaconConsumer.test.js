const { expect } = require("chai");
const { ethers } = require("hardhat");

const E18 = 10n ** 18n;
const MIN = 1000n * E18;
const ID = ethers.encodeBytes32String("frontier");
const RATE = 136_250_000n; // $1.3625/Mtok at 8 decimals
const DAY = 24 * 3600;

// Stand up the full stack, publish + finalize one feed, then a consumer pointed at it.
async function setup() {
  const [deployer] = await ethers.getSigners();
  const token = await (await ethers.getContractFactory("BeaconToken")).deploy(deployer.address);
  await token.waitForDeployment();
  const staking = await (await ethers.getContractFactory("BeaconStaking")).deploy(await token.getAddress());
  await staking.waitForDeployment();
  const oracle = await (await ethers.getContractFactory("BeaconOracleV2")).deploy(await staking.getAddress());
  await oracle.waitForDeployment();
  await staking.setSlasher(await oracle.getAddress());

  await token.approve(await staking.getAddress(), MIN);
  await staking.selfStake(MIN); // deployer becomes an eligible publisher
  await oracle.postFeed(ID, RATE);
  await oracle.finalizeRound(ID); // publishes latestValue(ID)

  const consumer = await (await ethers.getContractFactory("BeaconConsumer")).deploy(await oracle.getAddress(), DAY);
  await consumer.waitForDeployment();
  return { oracle, consumer };
}

describe("BeaconConsumer — reading the rate for settlement", function () {
  it("reads the published rate", async () => {
    const { consumer } = await setup();
    expect(await consumer.readRate(ID)).to.equal(RATE);
  });

  it("quotes a settlement cost against the rate", async () => {
    const { consumer } = await setup();
    // cost to settle 10 million-tokens of this capability tier, in 8-decimal USD
    expect(await consumer.quote(ID, 10n)).to.equal(RATE * 10n);
  });

  it("reverts on an unknown feed", async () => {
    const { consumer } = await setup();
    await expect(consumer.readRate(ethers.encodeBytes32String("nope"))).to.be.revertedWith("no rate");
  });

  it("reverts on a stale rate", async () => {
    const { consumer } = await setup();
    await ethers.provider.send("evm_increaseTime", [2 * DAY]); // older than maxAge
    await ethers.provider.send("evm_mine", []);
    await expect(consumer.readRate(ID)).to.be.revertedWith("stale rate");
  });
});
