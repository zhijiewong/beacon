const { expect } = require("chai");
const { ethers } = require("hardhat");

const E18 = 10n ** 18n;
const MIN = 1000n * E18; // MIN_PUBLISHER_STAKE
const ID = ethers.encodeBytes32String("frontier");

// 3 eligible publishers (each self-staked) + 1 non-publisher. The oracle is the
// authorized slasher on the staking contract.
async function setup() {
  const [deployer, p1, p2, p3, nonPub] = await ethers.getSigners();
  const token = await (await ethers.getContractFactory("BeaconToken")).deploy(deployer.address);
  await token.waitForDeployment();
  const staking = await (await ethers.getContractFactory("BeaconStaking")).deploy(await token.getAddress());
  await staking.waitForDeployment();
  const oracle = await (await ethers.getContractFactory("BeaconOracleV2")).deploy(await staking.getAddress());
  await oracle.waitForDeployment();

  await staking.setSlasher(await oracle.getAddress());
  for (const p of [p1, p2, p3]) {
    await token.transfer(p.address, 10_000n * E18);
    await token.connect(p).approve(await staking.getAddress(), 1_000_000n * E18);
    await staking.connect(p).selfStake(MIN); // become an eligible publisher
  }
  return { token, staking, oracle, deployer, p1, p2, p3, nonPub };
}

describe("BeaconOracleV2 — median aggregation + deviation slashing", function () {
  it("aggregates eligible publishers' submissions by median on finalize", async () => {
    const { oracle, p1, p2, p3 } = await setup();
    await oracle.connect(p1).postFeed(ID, 100);
    await oracle.connect(p2).postFeed(ID, 102);
    await oracle.connect(p3).postFeed(ID, 104);
    expect(await oracle.median(ID)).to.equal(102);

    await oracle.finalizeRound(ID);
    const [value] = await oracle.latestValue(ID);
    expect(value).to.equal(102);
  });

  it("rejects submissions from non-eligible accounts", async () => {
    const { oracle, nonPub } = await setup();
    await expect(oracle.connect(nonPub).postFeed(ID, 100)).to.be.revertedWith("not eligible");
  });

  it("auto-slashes a publisher whose value deviates beyond the threshold", async () => {
    const { staking, oracle, p1, p2, p3 } = await setup();
    await oracle.connect(p1).postFeed(ID, 100);
    await oracle.connect(p2).postFeed(ID, 101);
    await oracle.connect(p3).postFeed(ID, 200); // ~98% off the median -> slashed

    await oracle.finalizeRound(ID);

    expect(await staking.poolStake(p3.address)).to.equal(950n * E18); // -5%
    expect(await staking.poolStake(p1.address)).to.equal(MIN); // honest, untouched
    expect(await staking.poolStake(p2.address)).to.equal(MIN);
  });

  it("does not slash submissions within the deviation threshold", async () => {
    const { staking, oracle, p1, p2, p3 } = await setup();
    await oracle.connect(p1).postFeed(ID, 100);
    await oracle.connect(p2).postFeed(ID, 102);
    await oracle.connect(p3).postFeed(ID, 105); // within 10% of median 102
    await oracle.finalizeRound(ID);
    for (const p of [p1, p2, p3]) {
      expect(await staking.poolStake(p.address)).to.equal(MIN);
    }
  });

  it("requires a quorum to finalize", async () => {
    const { oracle, deployer, p1, p2 } = await setup();
    await oracle.connect(deployer).setMinPublishers(3);
    await oracle.connect(p1).postFeed(ID, 100);
    await oracle.connect(p2).postFeed(ID, 102);
    await expect(oracle.finalizeRound(ID)).to.be.revertedWith("quorum");
  });

  it("weights the median by stake — a heavily-staked publisher pulls the rate", async () => {
    const { token, staking, oracle, p1, p2, p3 } = await setup();
    // p1 raises its stake to 3000 (3x the others at 1000 each).
    await token.connect(p1).approve(await staking.getAddress(), 2_000n * E18);
    await staking.connect(p1).selfStake(2_000n * E18); // p1 pool: 1000 -> 3000

    await oracle.connect(p1).postFeed(ID, 100); // weight 3000
    await oracle.connect(p2).postFeed(ID, 110); // weight 1000
    await oracle.connect(p3).postFeed(ID, 112); // weight 1000

    // unweighted median would be 110; stake-weighted (3000 at 100 > half of 5000) is 100
    expect(await oracle.median(ID)).to.equal(100);
  });

  it("falls back to a plain median when stakes are equal", async () => {
    const { oracle, p1, p2, p3 } = await setup();
    await oracle.connect(p1).postFeed(ID, 100);
    await oracle.connect(p2).postFeed(ID, 102);
    await oracle.connect(p3).postFeed(ID, 104);
    expect(await oracle.median(ID)).to.equal(102); // equal weights -> middle value
  });

  it("lets governance tighten the deviation threshold without a redeploy", async () => {
    const { staking, oracle, deployer, p1, p2, p3 } = await setup();
    await oracle.connect(deployer).setMaxDeviationBps(100); // 1% tolerance
    await oracle.connect(p1).postFeed(ID, 100);
    await oracle.connect(p2).postFeed(ID, 100);
    await oracle.connect(p3).postFeed(ID, 105); // 5% off median 100 -> slashed at 1% tol
    await oracle.finalizeRound(ID);
    expect(await staking.poolStake(p3.address)).to.equal(950n * E18);
    expect(await staking.poolStake(p1.address)).to.equal(MIN);
  });

  it("caps the configurable slash so staking.slash can never revert", async () => {
    const { oracle, deployer } = await setup();
    await expect(oracle.connect(deployer).setDeviationSlashBps(501)).to.be.revertedWith("slash too high");
  });

  it("only the owner can change oracle parameters", async () => {
    const { oracle, p1 } = await setup();
    await expect(oracle.connect(p1).setMaxDeviationBps(100))
      .to.be.revertedWithCustomError(oracle, "OwnableUnauthorizedAccount");
  });

  it("excludes stale submissions from the median and never slashes them", async () => {
    const { staking, oracle, deployer, p1, p2, p3 } = await setup();
    await oracle.connect(deployer).setMaxStaleness(3600); // 1 hour
    await oracle.connect(p3).postFeed(ID, 1_000_000); // wild outlier, posted first
    await ethers.provider.send("evm_increaseTime", [7200]); // p3 goes stale
    await ethers.provider.send("evm_mine", []);
    await oracle.connect(p1).postFeed(ID, 100); // fresh
    await oracle.connect(p2).postFeed(ID, 100); // fresh

    await oracle.finalizeRound(ID);
    const [value] = await oracle.latestValue(ID);
    expect(value).to.equal(100); // p3's stale outlier ignored
    expect(await staking.poolStake(p3.address)).to.equal(MIN); // stale -> not slashed
  });

  it("reverts finalize when every submission is stale (no fresh quorum)", async () => {
    const { oracle, deployer, p1, p2 } = await setup();
    await oracle.connect(deployer).setMaxStaleness(3600);
    await oracle.connect(p1).postFeed(ID, 100);
    await oracle.connect(p2).postFeed(ID, 102);
    await ethers.provider.send("evm_increaseTime", [7200]); // both stale
    await ethers.provider.send("evm_mine", []);
    await expect(oracle.finalizeRound(ID)).to.be.revertedWith("quorum");
  });

  it("clears the round so the next round starts fresh", async () => {
    const { oracle, p1, p2, p3 } = await setup();
    await oracle.connect(p1).postFeed(ID, 100);
    await oracle.connect(p2).postFeed(ID, 102);
    await oracle.connect(p3).postFeed(ID, 104);
    await oracle.finalizeRound(ID);
    // a fresh round with new values re-aggregates from scratch
    await oracle.connect(p1).postFeed(ID, 200);
    await oracle.connect(p2).postFeed(ID, 202);
    await oracle.connect(p3).postFeed(ID, 204);
    expect(await oracle.median(ID)).to.equal(202);
  });
});
