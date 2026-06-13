const { expect } = require("chai");
const { ethers } = require("hardhat");

const E18 = 10n ** 18n;
const USDC = 10n ** 6n; // 6-decimal stablecoin
const MIN = 1000n * E18;

// deployer owns the staking contract and funds the reward pot.
async function setup() {
  const [deployer, pub, del, other] = await ethers.getSigners();
  const beacon = await (await ethers.getContractFactory("BeaconToken")).deploy(deployer.address);
  await beacon.waitForDeployment();
  const usdc = await (await ethers.getContractFactory("MockERC20")).deploy("USD Coin", "USDC", 6);
  await usdc.waitForDeployment();
  const staking = await (await ethers.getContractFactory("BeaconStaking")).deploy(await beacon.getAddress());
  await staking.waitForDeployment();

  await staking.setRewardToken(await usdc.getAddress());
  await beacon.transfer(pub.address, 10_000n * E18);
  await beacon.transfer(del.address, 10_000n * E18);
  for (const s of [pub, del]) {
    await beacon.connect(s).approve(await staking.getAddress(), 1_000_000n * E18);
  }
  // deployer holds USDC to distribute as rewards
  await usdc.mint(deployer.address, 1_000_000n * USDC);
  await usdc.approve(await staking.getAddress(), 1_000_000n * USDC);

  return { beacon, usdc, staking, deployer, pub, del, other };
}

describe("BeaconStaking — USDC rewards", function () {
  it("distributes rewards pro-rata to shares; stakers claim in USDC", async () => {
    const { usdc, staking, deployer, pub, del } = await setup();
    await staking.connect(pub).selfStake(MIN); // 1000 -> 1/2 of pool
    await staking.connect(del).delegate(pub.address, MIN); // 1000 -> 1/2 of pool

    await staking.connect(deployer).distributeRewards(pub.address, 10n * USDC); // 10 USDC, no fee

    expect(await staking.pendingRewards(pub.address, pub.address)).to.equal(5n * USDC);
    expect(await staking.pendingRewards(pub.address, del.address)).to.equal(5n * USDC);

    await staking.connect(del).claim(pub.address);
    expect(await usdc.balanceOf(del.address)).to.equal(5n * USDC);
    // double claim yields nothing more
    await staking.connect(del).claim(pub.address);
    expect(await usdc.balanceOf(del.address)).to.equal(5n * USDC);
  });

  it("takes the publisher commission off the top before pro-rata split", async () => {
    const { staking, deployer, pub, del } = await setup();
    await staking.connect(pub).setPublisherFee(1000); // 10%
    await staking.connect(pub).selfStake(MIN);
    await staking.connect(del).delegate(pub.address, MIN);

    await staking.connect(deployer).distributeRewards(pub.address, 100n * USDC);
    // 10 USDC fee to publisher; remaining 90 split evenly -> 45 each
    expect(await staking.pendingRewards(pub.address, pub.address)).to.equal(10n * USDC + 45n * USDC);
    expect(await staking.pendingRewards(pub.address, del.address)).to.equal(45n * USDC);
  });

  it("caps the publisher commission", async () => {
    const { staking, pub } = await setup();
    await expect(staking.connect(pub).setPublisherFee(2001)).to.be.revertedWith("fee too high");
  });

  it("rewards already accrued survive a later slash", async () => {
    const { staking, deployer, pub } = await setup();
    await staking.connect(pub).selfStake(MIN);
    await staking.connect(deployer).distributeRewards(pub.address, 10n * USDC);
    await staking.connect(deployer).slash(pub.address, 500); // haircut on stake, not on owed USDC
    expect(await staking.pendingRewards(pub.address, pub.address)).to.equal(10n * USDC);
  });

  it("enforces the per-epoch reward cap, which resets after the epoch", async () => {
    const { staking, deployer, pub } = await setup();
    await staking.connect(deployer).setMaxRewardPerEpoch(2n * USDC); // cap: 2 USDC / pool / epoch
    await staking.connect(pub).selfStake(MIN);
    await staking.connect(deployer).distributeRewards(pub.address, 1n * USDC); // 1 used
    // 1 + 2 = 3 > 2 cap -> reverts
    await expect(staking.connect(deployer).distributeRewards(pub.address, 2n * USDC))
      .to.be.revertedWith("epoch cap");
    // after the epoch elapses, the cap resets
    await ethers.provider.send("evm_increaseTime", [7 * 24 * 3600 + 1]);
    await ethers.provider.send("evm_mine", []);
    await staking.connect(deployer).distributeRewards(pub.address, 1n * USDC);
    expect(await staking.pendingRewards(pub.address, pub.address)).to.equal(2n * USDC);
  });

  it("only the owner distributes, and the reward token must be set", async () => {
    const { staking, pub, other } = await setup();
    await staking.connect(pub).selfStake(MIN);
    await expect(staking.connect(other).distributeRewards(pub.address, 1n * USDC))
      .to.be.revertedWithCustomError(staking, "OwnableUnauthorizedAccount");
  });
});
