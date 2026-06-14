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

  it("transfers ownership in two steps (no accidental hand-off)", async () => {
    const { staking, deployer, other } = await setup();
    await staking.connect(deployer).transferOwnership(other.address);
    expect(await staking.owner()).to.equal(deployer.address); // not transferred yet
    expect(await staking.pendingOwner()).to.equal(other.address);
    await staking.connect(other).acceptOwnership();
    expect(await staking.owner()).to.equal(other.address);
  });

  it("pause stops new staking but never traps a withdrawal; unpause restores it", async () => {
    const { staking, deployer, pub } = await setup();
    await staking.connect(pub).selfStake(MIN);
    await staking.connect(pub).requestUnstake(pub.address, 400n * E18); // pool -> 600
    await staking.connect(deployer).pause();

    await expect(staking.connect(pub).selfStake(MIN)).to.be.revertedWithCustomError(staking, "EnforcedPause");
    // exiting is always allowed: the cooldown'd withdrawal still goes through while paused
    await increaseTime(7 * 24 * 3600 + 1);
    await staking.connect(pub).withdraw(pub.address);

    await staking.connect(deployer).unpause();
    await staking.connect(pub).selfStake(MIN); // staking works again
    expect(await staking.poolStake(pub.address)).to.equal(600n * E18 + MIN);
  });

  it("only the owner can pause", async () => {
    const { staking, pub } = await setup();
    await expect(staking.connect(pub).pause()).to.be.revertedWithCustomError(staking, "OwnableUnauthorizedAccount");
  });

  it("owner can rescue a stray ERC20, but never the staked BEACON or the reward token", async () => {
    const { token, staking, deployer, other } = await setup();
    const stray = await (await ethers.getContractFactory("MockERC20")).deploy("Stray", "STRY", 18);
    await stray.mint(await staking.getAddress(), 5n * E18); // fat-fingered straight to the contract
    await staking.connect(deployer).rescueTokens(await stray.getAddress(), other.address, 5n * E18);
    expect(await stray.balanceOf(other.address)).to.equal(5n * E18);

    // the staked asset is off-limits
    await expect(staking.connect(deployer).rescueTokens(await token.getAddress(), other.address, 1n))
      .to.be.revertedWith("protected");
    // and so is the reward token once set
    const usdc = await (await ethers.getContractFactory("MockERC20")).deploy("USD Coin", "USDC", 6);
    await staking.connect(deployer).setRewardToken(await usdc.getAddress());
    await expect(staking.connect(deployer).rescueTokens(await usdc.getAddress(), other.address, 1n))
      .to.be.revertedWith("protected");
  });

  it("only the owner can rescue", async () => {
    const { token, staking, pub, other } = await setup();
    await expect(staking.connect(pub).rescueTokens(await token.getAddress(), other.address, 1n))
      .to.be.revertedWithCustomError(staking, "OwnableUnauthorizedAccount");
  });

  // Regression for security-review Finding 3: the shares/assets vault must resist the
  // ERC-4626 first-depositor / donation share-inflation attack. The defense is that pool
  // assets are internal accounting (not balanceOf), so a raw token "donation" can't move
  // the share price and round a later depositor's stake to zero.
  it("resists the first-depositor share-inflation attack (no donation path)", async () => {
    const { token, staking, deployer, pub, del } = await setup();
    // Attacker opens a pool with a 1-wei self-stake (1 share) and tries to inflate it.
    await staking.connect(pub).selfStake(1n);
    expect(await staking.poolStake(pub.address)).to.equal(1n);
    expect(await staking.totalShares(pub.address)).to.equal(1n);

    // "Donate" a large amount straight to the contract to pump the share price.
    await token.connect(deployer).transfer(await staking.getAddress(), 1_000n * E18);
    expect(await staking.poolStake(pub.address)).to.equal(1n); // internal accounting ignores it

    // Victim delegates a normal amount — must get fair shares, never rounded to zero.
    const amt = 2_000n * E18;
    await staking.connect(del).delegate(pub.address, amt);
    expect(await staking.stakeOf(pub.address, del.address)).to.equal(amt);
    expect(await staking.sharesOf(pub.address, del.address)).to.be.gt(0n);

    // And recovers their full principal — nothing was siphoned by the attacker.
    await staking.connect(del).requestUnstake(pub.address, amt);
    await increaseTime(7 * 24 * 3600 + 1);
    const before = await token.balanceOf(del.address);
    await staking.connect(del).withdraw(pub.address);
    expect(await token.balanceOf(del.address)).to.equal(before + amt);
  });
});
