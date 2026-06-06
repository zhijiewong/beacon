const { expect } = require("chai");
const { ethers } = require("hardhat");

// Feed id = keccak256 of a human name; value is $/Mtok in 8-decimal fixed point.
const FEED_ID = ethers.id("GPQA-Diamond:frontier");
const DATE = ethers.hexlify(ethers.toUtf8Bytes("20260607")); // bytes8 "20260607"
const VALUE = 136800000n; // $1.368/Mtok
const MVER = 1;

async function deploy() {
  const [publisher, other] = await ethers.getSigners();
  const Oracle = await ethers.getContractFactory("BeaconOracle");
  const oracle = await Oracle.deploy();
  await oracle.waitForDeployment();
  return { oracle, publisher, other };
}

describe("BeaconOracle", function () {
  it("stores a posted feed and returns it via getFeed", async () => {
    const { oracle } = await deploy();
    await oracle.postFeed(FEED_ID, VALUE, MVER, DATE);
    const feed = await oracle.getFeed(FEED_ID);
    expect(feed.value).to.equal(VALUE);
    expect(feed.methodologyVersion).to.equal(MVER);
    expect(feed.snapshotDate).to.equal(DATE);
    expect(feed.updatedAt).to.be.greaterThan(0n);
  });

  it("latestValue returns value and timestamp", async () => {
    const { oracle } = await deploy();
    await oracle.postFeed(FEED_ID, VALUE, MVER, DATE);
    const [value, updatedAt] = await oracle.latestValue(FEED_ID);
    expect(value).to.equal(VALUE);
    expect(updatedAt).to.be.greaterThan(0n);
  });

  it("reverts when a non-publisher posts", async () => {
    const { oracle, other } = await deploy();
    await expect(
      oracle.connect(other).postFeed(FEED_ID, VALUE, MVER, DATE)
    ).to.be.revertedWith("not publisher");
  });

  it("overwrites with the latest post", async () => {
    const { oracle } = await deploy();
    await oracle.postFeed(FEED_ID, VALUE, MVER, DATE);
    await oracle.postFeed(FEED_ID, 99000000n, MVER, DATE);
    expect((await oracle.getFeed(FEED_ID)).value).to.equal(99000000n);
  });

  it("emits FeedPosted on a post", async () => {
    const { oracle } = await deploy();
    await expect(oracle.postFeed(FEED_ID, VALUE, MVER, DATE)).to.emit(
      oracle,
      "FeedPosted"
    );
  });

  it("returns a zeroed feed for an unknown id", async () => {
    const { oracle } = await deploy();
    const feed = await oracle.getFeed(ethers.id("does-not-exist"));
    expect(feed.value).to.equal(0n);
    expect(feed.updatedAt).to.equal(0n);
  });

  it("rotates the publisher; the old one loses access", async () => {
    const { oracle, publisher, other } = await deploy();
    await oracle.setPublisher(other.address);
    await expect(
      oracle.connect(publisher).postFeed(FEED_ID, VALUE, MVER, DATE)
    ).to.be.revertedWith("not publisher");
    await oracle.connect(other).postFeed(FEED_ID, VALUE, MVER, DATE);
    expect((await oracle.getFeed(FEED_ID)).value).to.equal(VALUE);
  });
});
