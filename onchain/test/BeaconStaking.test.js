const { expect } = require("chai");
const { ethers } = require("hardhat");

const E18 = 10n ** 18n;
const MIN = 1000n * E18; // MIN_PUBLISHER_STAKE

async function setup() {
  const [deployer, pub, del, other] = await ethers.getSigners();
  const token = await (await ethers.getContractFactory("BeaconToken")).deploy(deployer.address);
  await token.waitForDeployment();
  const staking = await (await ethers.getContractFactory("BeaconStaking")).deploy(await token.getAddress());
  await staking.waitForDeployment();
  // fund publisher + delegator from treasury, and approve the staking contract
  await token.transfer(pub.address, 10_000n * E18);
  await token.transfer(del.address, 5_000n * E18);
  for (const s of [pub, del]) {
    await token.connect(s).approve(await staking.getAddress(), 1_000_000n * E18);
  }
  return { token, staking, deployer, pub, del, other };
}

async function increaseTime(seconds) {
  await ethers.provider.send("evm_increaseTime", [seconds]);
  await ethers.provider.send("evm_mine", []);
}

describe("BeaconStaking", function () {
  it("publisher self-stake increases pool stake and pulls tokens in", async () => {
    const { token, staking, pub } = await setup();
    await staking.connect(pub).selfStake(MIN);
    expect(await staking.stakeOf(pub.address, pub.address)).to.equal(MIN);
    expect(await staking.poolStake(pub.address)).to.equal(MIN);
    expect(await token.balanceOf(await staking.getAddress())).to.equal(MIN);
  });

  it("eligibility requires the minimum self-stake", async () => {
    const { staking, pub } = await setup();
    await staking.connect(pub).selfStake(MIN - 1n);
    expect(await staking.isEligiblePublisher(pub.address)).to.equal(false);
    await staking.connect(pub).selfStake(1n);
    expect(await staking.isEligiblePublisher(pub.address)).to.equal(true);
  });

  it("delegator stakes to a publisher's pool", async () => {
    const { staking, pub, del } = await setup();
    await staking.connect(pub).selfStake(MIN);
    await staking.connect(del).delegate(pub.address, 2_000n * E18);
    expect(await staking.stakeOf(pub.address, del.address)).to.equal(2_000n * E18);
    expect(await staking.poolStake(pub.address)).to.equal(MIN + 2_000n * E18);
  });

  it("cannot delegate to a non-publisher", async () => {
    const { staking, del, other } = await setup();
    await expect(staking.connect(del).delegate(other.address, E18)).to.be.revertedWith("not a publisher");
  });

  it("unstake honors the cooldown, then returns tokens", async () => {
    const { token, staking, pub } = await setup();
    await staking.connect(pub).selfStake(MIN);
    await staking.connect(pub).requestUnstake(pub.address, 400n * E18);
    // stake reduced immediately; tokens not yet withdrawable
    expect(await staking.poolStake(pub.address)).to.equal(MIN - 400n * E18);
    await expect(staking.connect(pub).withdraw(pub.address)).to.be.revertedWith("cooling down");

    await increaseTime(7 * 24 * 3600 + 1);
    const before = await token.balanceOf(pub.address);
    await staking.connect(pub).withdraw(pub.address);
    expect(await token.balanceOf(pub.address)).to.equal(before + 400n * E18);
  });
});
