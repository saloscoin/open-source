# SALOCOIN (SALO) Whitepaper

**Version 1.2 | January 2026**

---

## Abstract

SALOCOIN (SALO) is a decentralized cryptocurrency built on proven blockchain technology, utilizing the SHA-256d (double SHA-256) proof-of-work algorithm. Designed for simplicity, security, and accessibility, SALOCOIN provides a fair and transparent monetary system with predictable supply economics modeled after Bitcoin's successful halving mechanism.

**Network Status**: 🟢 LIVE (Mainnet launched January 2026)

This whitepaper describes the technical architecture, consensus mechanism, economic model, and ecosystem of SALOCOIN.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Technical Specifications](#2-technical-specifications)
3. [Consensus Mechanism](#3-consensus-mechanism)
4. [Economic Model](#4-economic-model)
5. [Wallet Architecture](#5-wallet-architecture)
6. [Network Protocol](#6-network-protocol)
7. [Mining](#7-mining)
8. [Security](#8-security)
9. [Roadmap](#9-roadmap)
10. [Conclusion](#10-conclusion)

---

## 1. Introduction

### 1.1 Background

Since Bitcoin's introduction in 2009, blockchain technology has revolutionized the concept of digital money. However, many cryptocurrencies have become overly complex, making them inaccessible to average users. SALOCOIN returns to the fundamentals: a simple, secure, and decentralized currency that anyone can use, mine, and understand.

### 1.2 Vision

SALOCOIN aims to be:
- **Simple**: Easy to use, mine, and understand
- **Secure**: Built on proven cryptographic primitives
- **Decentralized**: No central authority, fully open-source
- **Accessible**: Anyone can participate with consumer hardware

### 1.3 Key Features

- SHA-256d proof-of-work (Bitcoin-compatible algorithm)
- 39 million maximum supply
- 2.5-minute block time
- Bitcoin-style halving every 210,000 blocks
- HD wallet support with BIP-39/BIP-44
- Open-source Python implementation

---

## 2. Technical Specifications

| Parameter | Value |
|-----------|-------|
| **Algorithm** | SHA-256d (Double SHA-256) |
| **Block Time** | 150 seconds (2.5 minutes) |
| **Initial Block Reward** | 100 SALO |
| **Halving Interval** | 210,000 blocks (~1 year) |
| **Maximum Supply** | 39,000,000 SALO |
| **Minimum Block Reward** | 0.1 SALO |
| **Decimal Places** | 8 (100,000,000 satoshis = 1 SALO) |
| **Address Prefix** | S |
| **P2P Port** | 7339 |
| **Difficulty Adjustment** | Every block (DAA) |
| **Transaction Fee** | 0.0001 SALO minimum |

### 2.1 Block Structure

Each block contains:
- **Version**: Protocol version (currently 1)
- **Previous Hash**: SHA-256d hash of the previous block header
- **Merkle Root**: Root of the Merkle tree of all transactions
- **Timestamp**: Unix timestamp of block creation
- **Difficulty Target**: Compact representation of target difficulty
- **Nonce**: 32-bit value adjusted during mining

### 2.2 Transaction Structure

Transactions follow the UTXO (Unspent Transaction Output) model:
- **Inputs**: References to previous unspent outputs
- **Outputs**: New outputs with value and locking script
- **Version**: Transaction version
- **Locktime**: Optional time-based locking

---

## 3. Consensus Mechanism

### 3.1 Proof of Work

SALOCOIN uses SHA-256d (double SHA-256) for its proof-of-work function:

```
hash = SHA256(SHA256(block_header))
```

This algorithm:
- Is battle-tested (used by Bitcoin since 2009)
- Compatible with existing ASIC mining hardware
- Provides strong security guarantees
- Well-understood cryptographic properties

### 3.2 Difficulty Adjustment Algorithm (DAA)

SALOCOIN employs Dark Gravity Wave v3 (DGW) for difficulty adjustment, maintaining consistent 2.5-minute block times:

**Parameters:**
| Setting | Value | Purpose |
|---------|-------|--------|
| Block Time Target | 150 seconds | 2.5 minutes |
| DGW Window | 24 blocks | Lookback for average calculation |
| Max Adjustment | 2x per block | Prevents extreme changes |
| Emergency Threshold | 600 seconds | 10 minutes without block |
| Emergency Reduction | 2x easier | Per emergency period |

**Algorithm:**
```python
# Dark Gravity Wave v3
adjustment = actual_time / target_time
new_difficulty = old_difficulty * adjustment

# Bounded to prevent extreme changes (max 2x per block)
max_adjustment = 2.0
min_adjustment = 0.5

# Emergency reduction if no block for 10+ minutes
if time_since_last_block > 600:
    difficulty = difficulty / 2  # Gets easier gradually
```

This responsive DAA:
- Adjusts every block for quick response to hashrate changes
- Prevents difficulty oscillation with 2x max adjustment
- Handles ASIC miners joining/leaving without inflation
- Emergency mode prevents stuck chains if hashrate drops
- Maintains ~576 blocks/day (like Litecoin/Dash)

### 3.3 Chain Selection

The chain with the most cumulative proof-of-work is considered valid:

```
chain_work = Σ (2^256 / target) for each block
```

---

## 4. Economic Model

### 4.1 Supply Schedule

SALOCOIN follows Bitcoin's proven halving model:

| Era | Block Range | Block Reward | Cumulative Supply |
|-----|-------------|--------------|-------------------|
| 1 | 0 - 209,999 | 100 SALO | 21,000,000 |
| 2 | 210,000 - 419,999 | 50 SALO | 31,500,000 |
| 3 | 420,000 - 629,999 | 25 SALO | 36,750,000 |
| 4 | 630,000 - 839,999 | 12.5 SALO | 38,375,000 |
| 5 | 840,000 - 1,049,999 | 6.25 SALO | 38,687,500 |
| ... | ... | ... | ... |
| ∞ | After final halving | 0.1 SALO | ~39,000,000 |

### 4.2 Halving Timeline

With 2.5-minute blocks:
- **Blocks per day**: ~576
- **Blocks per year**: ~210,240
- **Halving interval**: ~1 year

### 4.3 Inflation Rate

The inflation rate decreases over time:
- Year 1: ~100% initial distribution
- Year 2: ~33% (after first halving)
- Year 3: ~14% (after second halving)
- Approaches 0% asymptotically

### 4.4 Transaction Fees

SALOCOIN uses **Bitcoin-style dynamic fee estimation** that automatically adjusts based on network conditions:

**Fee Calculation Factors:**
1. **Mempool Size** - Number and size of pending transactions
2. **Recent Block Fill Rate** - How full the last N blocks were
3. **Median Accepted Fee** - Fees paid by confirmed transactions

**Wallet Fee Suggestions:**

| Priority | Target Confirmation | Description |
|----------|---------------------|-------------|
| **Fast** | 1-2 blocks (~5 min) | Higher fee, prioritized |
| **Normal** | 3-6 blocks (~15 min) | Balanced fee |
| **Economy** | 7+ blocks (~20+ min) | Lower fee, may wait |

**Algorithm:**
```
base_fee = max(median_accepted_fee, min_fee * congestion_factor)
congestion_factor = 1 + (mempool_size - 100) / 100 + block_fill_bonus
fee_rate = base_fee * priority_multiplier
```

**API Endpoint**: `GET /fee_estimate` returns recommended fees:
```json
{
  "fast": {"fee_rate": 10, "target_blocks": 1},
  "normal": {"fee_rate": 5, "target_blocks": 3},
  "economy": {"fee_rate": 2, "target_blocks": 10}
}
```

Fees are awarded to miners alongside block rewards.

---

## 5. Wallet Architecture

### 5.1 HD Wallet (BIP-32/39/44)

SALOCOIN wallets implement hierarchical deterministic key derivation:

```
Derivation Path: m/44'/9339'/account'/change/address_index
```

- **BIP-39**: 24-word mnemonic seed phrase
- **BIP-32**: Hierarchical deterministic derivation
- **BIP-44**: Multi-account structure

### 5.2 Address Format

Addresses use Base58Check encoding with prefix 'S':
- **Type**: P2PKH (Pay to Public Key Hash)
- **Format**: S + Base58Check(RIPEMD160(SHA256(pubkey)))
- **Length**: 34 characters

Example: `SN1qdiiNCaNjzs2mMV7Gg5jHWabdYX193q`

### 5.3 Cryptographic Primitives

- **Elliptic Curve**: secp256k1
- **Signature**: ECDSA
- **Hashing**: SHA-256, RIPEMD-160
- **Encoding**: Base58Check

---

## 6. Network Protocol

### 6.1 Node Types

1. **Full Nodes**: Store complete blockchain, validate all transactions
2. **Mining Nodes**: Full nodes that participate in mining
3. **Seed Nodes**: Bootstrap nodes for peer discovery
4. **Pool Nodes**: Mining pool servers

### 6.2 Peer Discovery

Nodes discover peers through:
- DNS seeds (seed.salocoin.org)
- Hardcoded seed nodes
- Peer exchange protocol
- Bootstrap server (bootstrap.salocoin.org)

### 6.3 Message Types

| Message | Purpose |
|---------|---------|
| `version` | Handshake and version negotiation |
| `getblocks` | Request block inventory |
| `blocks` | Send block data |
| `tx` | Broadcast transaction |
| `getaddr` | Request peer addresses |
| `addr` | Send peer addresses |

### 6.4 API Endpoints

The seed node provides REST API:
- `GET /status` - Network status
- `GET /blocks` - Block list
- `GET /block/<height>` - Specific block
- `GET /mempool` - Pending transactions
- `GET /fee_estimate` - Dynamic fee recommendations
- `GET /balance/<address>` - Address balance
- `POST /submit_tx` - Submit transaction
- `POST /submit_block` - Submit mined block

---

## 7. Mining

### 7.1 Solo Mining

Individual miners can mine directly:
```bash
python gpu_miner.py --address YOUR_ADDRESS
```

### 7.2 Pool Mining

Pool mining distributes rewards among contributors:
```bash
python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_ADDRESS --gpu
```

**Pool Features:**
- Stratum protocol compatible
- Per-block reward distribution
- **Dynamic pool fee (1-10%)** - More workers = lower fee
- **Bitcoin-style payouts** - Network fee deducted from miner payout
- **Coinbase maturity** - 100 block confirmations before payout
- **Partial payouts** - Pays available mature balance
- **Persistent stats** - Pending payouts saved on shutdown
- **Dynamic network fees** - Adjusts based on mempool congestion
- Real-time statistics API

**Network Fee (Bitcoin-Style):**
Like Bitcoin pools, the network transaction fee is deducted from the miner's payout rather than from the pool fee. The fee is dynamic and adjusts based on network congestion:
- **Fast** (1-2 blocks): 2x base rate
- **Normal** (3-6 blocks): 1x base rate  
- **Economy** (7+ blocks): 0.5x base rate

Minimum network fee: 250 sats (0.0000025 SALO)

**Dynamic Pool Fee Schedule:**
| Workers | Pool Fee |
|---------|----------|
| 1 | 10% |
| 5 | 5% |
| 10 | 3% |
| 20 | 2% |
| 50 | 1.5% |
| 100+ | 1% |

### 7.3 Hardware Support

| Type | Hashrate | Power | Efficiency |
|------|----------|-------|------------|
| CPU (Ryzen 9) | ~10 MH/s | 105W | ~0.1 MH/W |
| GPU (RTX 3080) | ~1 GH/s | 320W | ~3 MH/W |
| ASIC (S19) | ~110 TH/s | 3250W | ~34 GH/W |

SALOCOIN is compatible with all SHA-256d mining hardware.

### 7.4 ASIC Mining Endpoints

**Pool Mining** (shared rewards, 1-10% fee):
```
# Standard (TCP)
stratum+tcp://pool.salocoin.org:7261
Worker: YOUR_SALO_ADDRESS.rig1

# SSL/TLS (recommended)
stratum+ssl://pool.salocoin.org:7263
Worker: YOUR_SALO_ADDRESS.rig1
```

**Solo Mining** (100% reward, no fee):
```
# Standard (TCP)
stratum+tcp://solo.salocoin.org:3333
Worker: YOUR_SALO_ADDRESS

# SSL/TLS (recommended)
stratum+ssl://solo.salocoin.org:3334
Worker: YOUR_SALO_ADDRESS
```

For solo mining, the Worker name must be a valid SALO address. Block rewards (100 SALO) go directly to that address.

---

## 8. Security

### 8.1 Cryptographic Security

- **256-bit security**: Private keys are 256-bit integers
- **Collision resistance**: SHA-256 provides 128-bit security against collisions
- **Quantum resistance**: Not currently quantum-resistant (like Bitcoin)

### 8.2 Network Security

- **51% attack resistance**: Requires majority hashpower
- **Double-spend prevention**: Confirmations reduce risk exponentially
- **Replay protection**: Each transaction has unique inputs

### 8.3 Best Practices

1. Keep private keys secure and backed up
2. Use HD wallets with mnemonic backup
3. Wait for confirmations (6+ for large amounts)
4. Run your own node for trustless validation

---

## 9. Roadmap

### Phase 1: Foundation (Complete)
- ✅ Core blockchain implementation
- ✅ HD wallet with mnemonic support
- ✅ GPU mining support
- ✅ Mining pool with Stratum
- ✅ Block explorer
- ✅ Seed node infrastructure

### Phase 2: Ecosystem (Completed)
- ✅ Desktop wallet application (Windows/macOS/Linux)
- ✅ Web wallet interface
- ✅ GPU mining support (OpenCL)
- ✅ Mining pool with dynamic fees
- ✅ ASIC solo mining proxy
- 🔄 Mobile wallet (planned)
- 🔄 Hardware wallet integration (planned)

### Phase 3: Adoption (In Progress)
- Exchange listings
- Merchant payment integration
- Lightning Network layer-2
- Cross-chain bridges

### Phase 4: Governance (Future)
- Decentralized governance proposals
- Community voting mechanism
- Development fund allocation

---

## 10. Conclusion

SALOCOIN represents a return to cryptocurrency fundamentals: a simple, secure, and decentralized digital currency accessible to everyone. By leveraging proven technology (SHA-256d, UTXO model, HD wallets) and maintaining clean, readable code, SALOCOIN provides a solid foundation for a community-driven cryptocurrency.

The combination of:
- Battle-tested proof-of-work algorithm
- Fair distribution through mining
- Predictable monetary policy
- Open-source development

...creates a cryptocurrency that embodies the original vision of peer-to-peer electronic cash.

---

## References

1. Nakamoto, S. (2008). Bitcoin: A Peer-to-Peer Electronic Cash System
2. BIP-32: Hierarchical Deterministic Wallets
3. BIP-39: Mnemonic code for generating deterministic keys
4. BIP-44: Multi-Account Hierarchy for Deterministic Wallets
5. NIST FIPS 180-4: Secure Hash Standard (SHA-256)

---

## License

SALOCOIN is released under the MIT License. See [LICENSE](LICENSE) for details.

---

## Links

- **Website**: https://salocoin.org
- **Explorer**: https://salocoin.org/explorer.html
- **GitHub**: https://github.com/saloscoin/open-source
- **Pool (TCP)**: stratum+tcp://pool.salocoin.org:7261
- **Pool (SSL)**: stratum+ssl://pool.salocoin.org:7263
- **Solo (TCP)**: stratum+tcp://solo.salocoin.org:3333
- **Solo (SSL)**: stratum+ssl://solo.salocoin.org:3334

---

*This whitepaper is a living document and may be updated as the project evolves.*
