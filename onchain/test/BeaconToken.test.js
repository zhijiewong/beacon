const { expect } = require("chai");
const { ethers } = require("hardhat");

const SUPPLY = 1_000_000_000n * 10n ** 18n; // 1B BEACON, 18 decimals

async function deploy() {
  const [deployer, treasury, alice] = await ethers.getSigners();
  const Token = await ethers.getContractFactory("BeaconToken");
  const token = await Token.deploy(treasury.address);
  await token.waitForDeployment();
  return { token, deployer, treasury, alice };
}

describe("BeaconToken", function () {
  it("has the right metadata", async () => {
    const { token } = await deploy();
    expect(await token.name()).to.equal("Beacon");
    expect(await token.symbol()).to.equal("BEACON");
    expect(await token.decimals()).to.equal(18n);
  });

  it("mints the full fixed supply to the treasury", async () => {
    const { token, treasury } = await deploy();
    expect(await token.totalSupply()).to.equal(SUPPLY);
    expect(await token.balanceOf(treasury.address)).to.equal(SUPPLY);
    expect(await token.MAX_SUPPLY()).to.equal(SUPPLY);
  });

  it("transfers tokens", async () => {
    const { token, treasury, alice } = await deploy();
    await token.connect(treasury).transfer(alice.address, 1000n);
    expect(await token.balanceOf(alice.address)).to.equal(1000n);
    expect(await token.balanceOf(treasury.address)).to.equal(SUPPLY - 1000n);
  });

  it("supports ERC20Permit (gasless approvals for staking later)", async () => {
    const { token, treasury } = await deploy();
    expect(await token.nonces(treasury.address)).to.equal(0n);
    expect(await token.DOMAIN_SEPARATOR()).to.be.properHex(64);
  });
});
