// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ERC20Permit} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";

/// @title BeaconToken (BEACON)
/// @notice Native token for the Beacon reference rate. Its job (Phase 2): secure the
///         price oracle via Oracle Integrity Staking, capture protocol fees, and
///         govern the index — NOT a unit of account (settlement stays in USDC).
/// @dev    Fixed supply minted once to a treasury; distribution (points -> airdrop)
///         is deferred until the rate has traction (see docs/phase2-onchain-oracle-design.md).
///         ERC20Permit enables gasless approvals for the staking flow.
///         TESTNET ONLY — unaudited; no live launch.
contract BeaconToken is ERC20, ERC20Permit {
    uint256 public constant MAX_SUPPLY = 1_000_000_000e18; // 1,000,000,000 BEACON

    constructor(address treasury) ERC20("Beacon", "BEACON") ERC20Permit("Beacon") {
        require(treasury != address(0), "zero treasury");
        _mint(treasury, MAX_SUPPLY); // no further minting — supply is fixed at deploy
    }
}
