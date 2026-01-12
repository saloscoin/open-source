# SALOCOIN (SALO) - Exchange Listing Application

---

## 1. Project Overview

| Field | Details |
|-------|---------|
| **Coin Name** | SALOCOIN |
| **Ticker Symbol** | SALO |
| **Launch Date** | January 2026 |
| **Project Type** | Layer 1 Blockchain / Cryptocurrency |
| **Consensus** | Proof of Work (SHA-256d) |
| **Open Source** | Yes (MIT License) |

### Project Description

SALOCOIN is an enterprise-grade cryptocurrency built on proven blockchain technology. It uses the SHA-256d (double SHA-256) proof-of-work algorithm—the same algorithm that secures Bitcoin—ensuring compatibility with existing ASIC mining hardware and benefiting from over 15 years of cryptographic security research.

Designed for simplicity, security, and accessibility, SALOCOIN provides a fair and transparent monetary system with predictable supply economics modeled after Bitcoin's successful halving mechanism.

---

## 2. Technical Specifications

### Core Parameters

| Parameter | Value |
|-----------|-------|
| **Algorithm** | SHA-256d (Double SHA-256) |
| **Block Time** | 150 seconds (2.5 minutes) |
| **Blocks Per Day** | ~576 |
| **Initial Block Reward** | 100 SALO |
| **Current Block Reward** | 100 SALO |
| **Halving Interval** | 210,000 blocks (~1 year) |
| **Maximum Supply** | 39,000,000 SALO |
| **Minimum Block Reward** | 0.1 SALO |
| **Decimal Places** | 8 |
| **Smallest Unit** | 0.00000001 SALO (1 satoshi) |
| **Address Prefix** | S |
| **Address Format** | Base58Check (34 characters) |
| **Transaction Model** | UTXO (Unspent Transaction Output) |

### Security Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Coinbase Maturity** | 100 blocks | Confirmations before mined coins are spendable |
| **Recommended Confirmations** | 6 blocks | For standard transactions |
| **High-Value Confirmations** | 100+ blocks | For exchange deposits |
| **Max Reorg Depth** | 100 blocks | Maximum chain reorganization allowed |
| **Difficulty Adjustment** | Every block | Dark Gravity Wave v3 algorithm |
| **DGW Window** | 24 blocks | Blocks used for difficulty calculation |
| **Max Difficulty Change** | ±400% per block | Prevents gaming the difficulty |

### Cryptographic Primitives

| Component | Algorithm |
|-----------|-----------|
| **Proof of Work** | SHA-256d (SHA256(SHA256(header))) |
| **Address Derivation** | RIPEMD-160(SHA-256(pubkey)) |
| **Digital Signatures** | ECDSA with secp256k1 curve |
| **Key Derivation** | BIP-32/39/44 HD Wallet |
| **Encoding** | Base58Check |

---

## 3. Network Information

### Mainnet Ports

| Service | Port | Protocol |
|---------|------|----------|
| P2P Network | 7339 | TCP |
| RPC Interface | 7340 | HTTP/JSON-RPC |
| Mining Pool (Stratum) | 7261 | Stratum TCP |
| Pool Stats API | 7262 | HTTP |

### Official Infrastructure

| Service | URL | Status |
|---------|-----|--------|
| **Main Website** | https://salocoin.org | ✅ Live |
| **Block Explorer** | https://salocoin.org/explorer.html | ✅ Live |
| **Web Wallet** | https://salocoin.org/wallet.html | ✅ Live |
| **API Endpoint** | https://api.salocoin.org | ✅ Live |
| **Seed Node** | https://seed.salocoin.org | ✅ Live |
| **Bootstrap Server** | https://bootstrap.salocoin.org | ✅ Live |
| **Mining Pool (TCP)** | stratum+tcp://pool.salocoin.org:7261 | ✅ Live |
| **Mining Pool (SSL)** | stratum+ssl://pool.salocoin.org:7263 | ✅ Live |
| **Solo Mining (TCP)** | stratum+tcp://solo.salocoin.org:3333 | ✅ Live |
| **Solo Mining (SSL)** | stratum+ssl://solo.salocoin.org:3334 | ✅ Live |

### API Endpoints for Integration

```
GET /status              - Network status, height, difficulty
GET /blocks              - Block data with pagination
GET /block/{hash}        - Single block by hash
GET /block/height/{n}    - Block by height
GET /tx/{txid}           - Transaction details
GET /balance/{address}   - Address balance (confirmed/immature)
GET /utxos/{address}     - Unspent outputs for address
GET /address/{addr}/stats - Comprehensive address statistics
GET /mempool             - Pending transactions
GET /fee_estimate        - Dynamic fee recommendations
POST /submit_tx          - Broadcast signed transaction
```

---

## 4. Supply Economics

### Emission Schedule (Bitcoin-Style Halving)

| Era | Block Range | Block Reward | Era Supply | Cumulative Supply |
|-----|-------------|--------------|------------|-------------------|
| 1 | 0 - 209,999 | 100 SALO | 21,000,000 | 21,000,000 |
| 2 | 210,000 - 419,999 | 50 SALO | 10,500,000 | 31,500,000 |
| 3 | 420,000 - 629,999 | 25 SALO | 5,250,000 | 36,750,000 |
| 4 | 630,000 - 839,999 | 12.5 SALO | 2,625,000 | 38,375,000 |
| 5 | 840,000 - 1,049,999 | 6.25 SALO | 1,312,500 | 38,687,500 |
| ... | ... | Continues halving | ... | ~39,000,000 |

### Key Economic Features

- **No Premine**: All coins are mined through proof-of-work
- **No ICO**: Fair launch with no token sale
- **No Developer Tax**: 100% of block rewards go to miners
- **Predictable Supply**: Deterministic emission schedule
- **Deflationary**: Supply approaches but never exceeds 39M

### Current Network Statistics

| Metric | Value |
|--------|-------|
| **Current Block Height** | ~2,500+ |
| **Circulating Supply** | ~250,000 SALO |
| **Daily Emission** | ~57,600 SALO |
| **Network Hashrate** | Active mining |
| **Active Miners** | Multiple pool workers |

---

## 5. Mining Compatibility

### ASIC Mining (SHA-256d)

SALOCOIN uses the same SHA-256d algorithm as Bitcoin, making it compatible with all Bitcoin ASIC miners:

| ASIC Model | Hashrate | Compatible |
|------------|----------|------------|
| Bitmain Antminer S21 | 200 TH/s | ✅ Yes |
| Bitmain Antminer S19 Pro | 110 TH/s | ✅ Yes |
| MicroBT Whatsminer M50 | 114 TH/s | ✅ Yes |
| Canaan AvalonMiner 1246 | 90 TH/s | ✅ Yes |
| Any SHA-256d ASIC | Any | ✅ Yes |

### Mining Options

| Method | Description | Endpoint |
|--------|-------------|----------|
| **Pool Mining (TCP)** | Proportional rewards, 1% fee | stratum+tcp://pool.salocoin.org:7261 |
| **Pool Mining (SSL)** | Same as above, encrypted | stratum+ssl://pool.salocoin.org:7263 |
| **Solo Mining (TCP)** | Direct block rewards, no fee | stratum+tcp://solo.salocoin.org:3333 |
| **Solo Mining (SSL)** | Same as above, encrypted | stratum+ssl://solo.salocoin.org:3334 |
| **GPU Mining** | OpenCL support for hobbyists | Pool or solo |
| **CPU Mining** | For testing only | Pool or solo |

---

## 6. Security Features

### Double-Spend Protection

1. **UTXO Model**: Each output can only be spent once
2. **Mempool Validation**: Duplicate inputs rejected at mempool level
3. **Block Validation**: Double-spends rejected during block validation
4. **Signature Verification**: All transaction inputs require valid ECDSA signatures

### Chain Security

1. **100-Block Coinbase Maturity**: Prevents spending premature mining rewards
2. **100-Block Max Reorg**: Limits chain reorganization depth
3. **Dark Gravity Wave**: Per-block difficulty adjustment prevents time-warp attacks
4. **Merkle Root Validation**: Ensures transaction integrity in blocks

### Wallet Security

1. **HD Wallet (BIP-32/39/44)**: Hierarchical deterministic key derivation
2. **24-Word Mnemonic**: Industry-standard seed phrase backup
3. **secp256k1 Curve**: Same elliptic curve as Bitcoin
4. **Encrypted Storage**: Optional wallet encryption

---

## 7. Exchange Integration Guide

### Recommended Configuration

| Parameter | Recommended Value |
|-----------|-------------------|
| **Minimum Deposit Confirmations** | 100 blocks (~4 hours) |
| **Withdrawal Confirmations** | 6 blocks (~15 minutes) |
| **Address Validation Regex** | `^S[1-9A-HJ-NP-Za-km-z]{33}$` |
| **Minimum Withdrawal** | 0.001 SALO |
| **Transaction Fee** | Dynamic (use /fee_estimate API) |

### Node Deployment

```bash
# Clone repository
git clone https://github.com/saloscoin/open-source.git
cd salocoin

# Install dependencies
pip install -r requirements.txt

# Run full node
python run_node.py --seed https://api.salocoin.org --port 7339

# Or sync and run API server
python seed_server.py --port 7339
```

### Address Generation (Python)

```python
from core.wallet import Wallet

# Create new wallet
wallet = Wallet()
wallet.generate_mnemonic()
address = wallet.create_address()
print(f"Address: {address}")  # SN1qd...
```

### Transaction Signing

```python
from core.transaction import Transaction, TxInput, TxOutput

# Create transaction
tx = Transaction(
    inputs=[TxInput(prev_txid, prev_vout, script_sig)],
    outputs=[TxOutput(amount_satoshis, recipient_address)]
)
tx.sign(private_key)

# Broadcast
response = requests.post('https://api.salocoin.org/submit_tx', 
    json={'transaction': tx.to_dict()})
```

### Balance Checking

```bash
# Check balance
curl https://api.salocoin.org/balance/SN1qdiiNCaNjzs2mMV7Gg5jHWabdYX193q

# Get UTXOs
curl https://api.salocoin.org/utxos/SN1qdiiNCaNjzs2mMV7Gg5jHWabdYX193q
```

---

## 8. Links & Resources

### Official Links

| Resource | URL |
|----------|-----|
| **Website** | https://salocoin.org |
| **Block Explorer** | https://salocoin.org/explorer.html |
| **Web Wallet** | https://salocoin.org/wallet.html |
| **GitHub Repository** | https://github.com/saloscoin/open-source |
| **Whitepaper** | https://github.com/saloscoin/open-source/blob/main/WHITEPAPER.md |
| **API Documentation** | https://api.salocoin.org |

### Technical Documentation

| Document | Description |
|----------|-------------|
| README.md | Quick start guide and overview |
| WHITEPAPER.md | Technical whitepaper |
| COMMUNITY_SEED_NODE.md | Node setup guide |
| SEED_NODE_SETUP.md | Production node deployment |

---

## 9. Contact Information

| Channel | Contact |
|---------|---------|
| **Email** | contact@salocoin.org |
| **GitHub Issues** | https://github.com/saloscoin/open-source/issues |
| **Development Wallet** | SjioJU3LtAPDgrcQcQvcPH4gukB7yP6Ywg |

---

## 10. Legal & Compliance

- **License**: MIT License (fully open source)
- **No Securities**: SALO is a utility token for network transaction fees
- **No ICO/IEO**: Fair launch through proof-of-work mining only
- **No Premine**: All coins distributed through mining
- **Decentralized**: No central authority controls the network

---

## 11. Technical Summary for Exchange Integration

```
Coin Name:           SALOCOIN
Ticker:              SALO
Algorithm:           SHA-256d (Bitcoin-compatible)
Block Time:          150 seconds
Confirmations:       100 (deposits), 6 (withdrawals)
Address Format:      Base58Check, prefix 'S', 34 chars
Address Regex:       ^S[1-9A-HJ-NP-Za-km-z]{33}$
Decimal Places:      8
Max Supply:          39,000,000 SALO
API:                 https://api.salocoin.org
Explorer:            https://salocoin.org/explorer.html
GitHub:              https://github.com/saloscoin/open-source
```

---

*Document Version: 1.0*  
*Last Updated: January 2026*
