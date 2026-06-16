require("@nomicfoundation/hardhat-ethers");
require("@nomicfoundation/hardhat-chai-matchers");
require("@nomicfoundation/hardhat-verify");

/**
 * Beacon on-chain oracle — Hardhat config.
 * Base Sepolia deploy uses env: BASE_SEPOLIA_RPC (optional) and PRIVATE_KEY.
 * Source verification: Sourcify (no key) is enabled; BaseScan/Etherscan needs an
 * Etherscan v2 multichain key in ETHERSCAN_API_KEY (free from etherscan.io).
 * @type import('hardhat/config').HardhatUserConfig
 */
module.exports = {
  solidity: {
    version: "0.8.28",
    // Cancun EVM (Base supports it) — required by OpenZeppelin 5.6's mcopy usage.
    settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: "cancun" },
  },
  networks: {
    baseSepolia: {
      url: process.env.BASE_SEPOLIA_RPC || "https://sepolia.base.org",
      chainId: 84532,
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
    },
  },
  // Etherscan v2 multichain key covers Base Sepolia (chainId 84532).
  etherscan: { apiKey: process.env.ETHERSCAN_API_KEY || "" },
  // Decentralized, key-free verification — works without an explorer API key.
  sourcify: { enabled: true },
};
