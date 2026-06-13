const { expect } = require("chai");
const { ethers } = require("hardhat");

const E18 = 10n ** 18n;
const MIN = 1000n * E18; // MIN_PUBLISHER_STAKE

// deployer is the owner (slasher) and the token treasury.
async function setup() {
  const [deployer, pub, del, other] = await ethers.getSigners();
  const token = await (await ethers.getContractFactory("BeaconToken")).deploy(deployer.address);
  await token.waitForDeployment();
  const staking = await (await ethers.getContractFactory("BeaconStaking")).deploy(await token.getAddress());
  await staking.waitForDeployment();
  await token.transfer(pub.address, 10_000n * E18);
  await token.transfer(del.address, 10_000n * E18);
  for (const s of [pub, del]) {
    await token.connect(s).approve(await staking.getAddress(), 1_000_000n * E18);
  }
  return { token, staking, deployer, pub, del, other };
}

describe("BeaconStaking — slashing", function () {
  it("owner slashes a pool, cutting every staker pro-rata and routing tokens to the treasury", async () => {
    const { token, staking, deployer, pub, del, other } = await setup();
    await staking.setSlashTreasury(other.address); // clean balance to assert against
    await staking.connect(pub).selfStake(MIN); // 1000
    await staking.connect(del).delegate(pub.address, MIN); // 1000 -> pool 2000

    await staking.connect(deployer).slash(pub.address, 500); // 5% of 2000 = 100

    expect(await staking.poolStake(pub.address)).to.equal(1900n * E18);
    expect(await staking.stakeOf(pub.address, pub.address)).to.equal(950n * E18);
    expect(await staking.stakeOf(pub.address, del.address)).to.equal(950n * E18);
    expect(await token.balanceOf(other.address)).to.equal(100n * E18);
  });

  it("slashing is capped at MAX_SLASH_BPS (5%)", async () => {
    const { staking, deployer, pub } = await setup();
    await staking.connect(pub).selfStake(MIN);
    await expect(staking.connect(deployer).slash(pub.address, 501)).to.be.revertedWith("slash too large");
  });

  it("only the owner or the authorized slasher can slash", async () => {
    const { staking, deployer, pub, del, other } = await setup();
    await staking.connect(pub).selfStake(MIN);
    // a random account cannot slash
    await expect(staking.connect(other).slash(pub.address, 100)).to.be.revertedWith("not authorized");
    // the owner authorizes `del` as the automated slasher, who can then slash
    await staking.connect(deployer).setSlasher(del.address);
    await staking.connect(del).slash(pub.address, 100);
    expect(await staking.poolStake(pub.address)).to.equal(990n * E18); // -1%
  });

  it("slashing can drop a publisher below the eligibility threshold", async () => {
    const { staking, deployer, pub } = await setup();
    await staking.connect(pub).selfStake(MIN); // exactly eligible
    expect(await staking.isEligiblePublisher(pub.address)).to.equal(true);
    await staking.connect(deployer).slash(pub.address, 500); // -5% -> 950 < 1000
    expect(await staking.isEligiblePublisher(pub.address)).to.equal(false);
  });

  it("a delegation after a slash is priced fairly (no dilution of the new staker)", async () => {
    const { staking, deployer, pub, del } = await setup();
    await staking.connect(pub).selfStake(MIN); // pool 1000
    await staking.connect(deployer).slash(pub.address, 500); // pool 950
    await staking.connect(del).delegate(pub.address, 950n * E18); // buys in at the post-slash rate

    // both end up at 950 each from a 1900 pool — the new staker isn't penalised for the prior slash
    expect(await staking.poolStake(pub.address)).to.equal(1900n * E18);
    expect(await staking.stakeOf(pub.address, del.address)).to.equal(950n * E18);
    expect(await staking.stakeOf(pub.address, pub.address)).to.equal(950n * E18);
  });
});
