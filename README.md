# SALOCOIN

<p align="center">
  <img src="https://salocoin.org/assets/salocoin.png" alt="SALOCOIN Logo" width="120">
</p>

<p align="center">
  <strong>Enterprise-Grade Masternode Cryptocurrency</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#desktop-wallet">Desktop Wallet</a> •
  <a href="#block-explorer">Block Explorer</a> •
  <a href="#pool-mining">Pool Mining</a> •
  <a href="#cli-commands">CLI Commands</a> •
  <a href="#api">API</a>
</p>

<p align="center">
  <a href="https://salocoin.org">🌐 Website</a> •
  <a href="https://salocoin.org/explorer.html">🔍 Block Explorer</a> •
  <a href="https://salocoin.org/wallet.html">💳 Web Wallet</a> •
  <a href="https://discord.gg/Z6S5Ngtk">💬 Discord</a> •
  <a href="https://t.me/saloscoin">📱 Telegram</a>
</p>

---

## 🚀 Live Network Status

**SALOCOIN Mainnet is LIVE!** The network launched in January 2026 and is fully operational.

| Metric | Current |
|--------|---------|
| **Network Status** | 🟢 Online |
| **Block Height** | Growing |
| **Target Block Time** | 2.5 minutes (150 sec) |
| **Blocks Per Day** | ~576 (like Litecoin/Dash) |
| **Mining Algorithm** | SHA-256d (Bitcoin/ASIC-compatible) |
| **Mining Pool** | Active at `pool.salocoin.org:7261` |
| **Exchange Ready** | ✅ Yes |

---

## Overview

SALOCOIN is an enterprise-grade cryptocurrency built with Python, featuring SHA-256d proof-of-work mining (Bitcoin-compatible), HD wallets with BIP-39/44 support, and a fully decentralized peer-to-peer network.

### Specifications

| Parameter | Value |
|-----------|-------|
| **Algorithm** | SHA-256d (Double SHA-256) |
| **Block Time** | 150 seconds (2.5 minutes) |
| **Initial Block Reward** | 100 SALO |
| **Max Supply** | 39,000,000 SALO |
| **Halving Interval** | 210,000 blocks (~1 year) |
| **Minimum Reward** | 0.1 SALO |
| **Decimal Places** | 8 |
| **Address Prefix** | S (starts with S) |
| **GPU Mining** | OpenCL (NVIDIA/AMD) |

### Official Network Nodes

| Service | URL | Description |
|---------|-----|-------------|
| **API Node** | https://api.salocoin.org | Main API for wallets & explorers |
| **Seed Node** | https://seed.salocoin.org | Peer discovery & block sync |
| **Bootstrap** | https://bootstrap.salocoin.org | Fast initial blockchain download |
| **Mining Pool** | stratum+tcp://pool.salocoin.org:7261 | Public mining pool (1-10% dynamic fee) |
| **Pool SSL** | stratum+ssl://pool.salocoin.org:7263 | Pool mining with SSL/TLS |
| **Solo Mining** | stratum+tcp://solo.salocoin.org:3333 | Solo mining (100% to miner) |
| **Solo SSL** | stratum+ssl://solo.salocoin.org:3334 | Solo mining with SSL/TLS |

### Reward Distribution (Bitcoin-Style Halving)

| Block Height | Reward | Era |
|--------------|--------|-----|
| 0 - 209,999 | 100 SALO | Era 1 |
| 210,000 - 419,999 | 50 SALO | Era 2 |
| 420,000 - 629,999 | 25 SALO | Era 3 |
| 630,000 - 839,999 | 12.5 SALO | Era 4 |
| ... | ... | ... |

*Reward halves every 210,000 blocks until minimum of 0.1 SALO. Full block reward goes to miners.*

### Network Ports

| Service | Mainnet | Testnet |
|---------|---------|---------|
| P2P | 7339 | 17339 |
| RPC | 7340 | 17340 |
| Masternode | 7341 | 17341 |
| Mining Pool (Stratum) | 7261 | 7261 |
| Pool Stats API (HTTP) | 7262 | 7262 |

### Security Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| **MAX_REORG_DEPTH** | 100 blocks | Maximum chain reorganization depth |
| **COINBASE_MATURITY** | 100 blocks | Confirmations before mined coins spendable |
| **MTP_BLOCK_COUNT** | 11 blocks | Median Time Past window |
| **MAX_FUTURE_BLOCK_TIME** | 7200 sec | Max time block can be ahead of network |
| **Difficulty Adjustment** | Every block | Dark Gravity Wave v3 |
| **DGW Window** | 24 blocks | Blocks used for difficulty calculation |
| **Max Adjustment** | ±200% | Maximum 2x difficulty change per block |
| **Emergency Threshold** | 600 seconds | Difficulty reduction if no block for 10 min |
| **Emergency Reduction** | 2x easier | Gradual reduction per period |

### Transaction Fee Estimation

SALOCOIN uses **Bitcoin-style dynamic fee estimation** based on network conditions:

| Priority | Target | Description |
|----------|--------|-------------|
| **Fast** | 1-2 blocks | High priority, confirmed quickly |
| **Normal** | 3-6 blocks | Standard priority |
| **Economy** | 7+ blocks | Low priority, cheaper fees |

**Fee Factors:**
- Current mempool size and congestion
- Recent block fill rate (last 10 blocks)
- Median fee rate of confirmed transactions
- Network congestion multiplier

**API Endpoints:**
```bash
# Get all fee estimates
curl https://api.salocoin.org/fee_estimate

# Get specific priority
curl https://api.salocoin.org/fee_estimate/fast
curl https://api.salocoin.org/fee_estimate/normal
curl https://api.salocoin.org/fee_estimate/economy
```

**Response Example:**
```json
{
  "fast": {"fee_rate": 15.5, "fee_per_kb": 15500, "target_blocks": 2},
  "normal": {"fee_rate": 8.2, "fee_per_kb": 8200, "target_blocks": 4},
  "economy": {"fee_rate": 2.0, "fee_per_kb": 2000, "target_blocks": 10}
}
```

---

## ⛏️ Mining

SALOCOIN supports **ASIC**, **GPU**, and **CPU** mining with solo and pool options.

### ASIC Mining (Fastest) ⚡

SALOCOIN uses **SHA-256d** (same as Bitcoin), so any Bitcoin ASIC works!

| ASIC Model | Hashrate | Works with SALO? |
|------------|----------|------------------|
| Antminer S21 | 200 TH/s | ✅ Yes |
| Antminer S19 | 110 TH/s | ✅ Yes |
| Whatsminer M50 | 114 TH/s | ✅ Yes |
| Any SHA-256d ASIC | Any | ✅ Yes |

**Pool Mining (Recommended for ASIC):**
```
# Standard (TCP)
Pool URL:     stratum+tcp://pool.salocoin.org:7261
Worker:       YOUR_SALO_ADDRESS.rig1
Password:     x

# With SSL/TLS
Pool URL:     stratum+ssl://pool.salocoin.org:7263
Worker:       YOUR_SALO_ADDRESS.rig1
Password:     x
```

**Solo Mining (ASIC):**
```
# Standard (TCP) - 100% rewards to your address
Pool URL:     stratum+tcp://solo.salocoin.org:3333
Worker:       YOUR_SALO_ADDRESS
Password:     x

# With SSL/TLS
Pool URL:     stratum+ssl://solo.salocoin.org:3334
Worker:       YOUR_SALO_ADDRESS
Password:     x
```
Note: Worker name must be a valid SALO address - rewards go directly to that address (100% to you, no pool fee).

**Run Your Own Solo Proxy:**
```bash
# On your own server (optional)
python asic_solo_proxy.py --address YOUR_SALO_ADDRESS --port 3333
```

### GPU Mining (Recommended for Hobbyists)

GPU mining uses OpenCL and achieves **200+ MH/s** on modern GPUs (vs ~500 KH/s on CPU).

**Solo Mining (GPU):**
```bash
# Install dependencies
pip install pyopencl numpy

# Mine with GPU
python gpu_miner.py --address YOUR_SALO_ADDRESS
```

**Pool Mining (GPU):**
```bash
# Connect to pool with GPU
python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_SALO_ADDRESS --gpu
```

### CPU Mining

**Solo Mining (CPU):**
```bash
python miner.py --address YOUR_SALO_ADDRESS --threads 8
```

**Pool Mining (CPU):**
```bash
python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_SALO_ADDRESS --threads 4
```

### Mining Comparison

| Method | Hashrate | Best For |
|--------|----------|----------|
| **ASIC** | 100-200 TH/s | Serious miners |
| **GPU** | 200-500 MH/s | Hobbyists |
| **CPU** | 0.5-5 MH/s | Testing only |

---

## 🌊 Pool Mining

SALOCOIN supports distributed pool mining where multiple workers combine hashpower and share rewards when any worker finds a block.

### Public Mining Pool

| Parameter | Value |
|-----------|-------|
| **Pool URL** | `pool.salocoin.org:7261` |
| **Protocol** | Stratum (TCP) |
| **Fee** | 1-10% (dynamic, lower with more workers) |
| **Reward** | Proportional to shares |

### Connect to Pool

**Windows (Batch):**
```batch
REM GPU Mining (recommended)
pool-worker.bat YOUR_SALO_ADDRESS MyRig --gpu

REM CPU Mining
pool-worker.bat YOUR_SALO_ADDRESS MyRig
```

**Python:**
```bash
# Install dependencies
pip install -r requirements.txt

# CPU Mining (replace with YOUR address)
python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_SALO_ADDRESS --worker PC1 --threads 4

# GPU Mining (much faster!)
python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_SALO_ADDRESS --worker PC1 --gpu
```

### Example

```bash
# Create wallet first
python salocoin-wallet.py create my_pool_wallet

# Get your address
python salocoin-wallet.py receive my_pool_wallet

# Connect to pool
python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_SALO_ADDRESS --worker MyPC --threads 4
```

### How Pool Mining Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Worker 1  │     │   Worker 2  │     │   Worker 3  │
│   (PC1)     │     │   (PC2)     │     │   (PC3)     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    ┌──────▼──────┐
                    │ Pool Server │
                    │  :7261      │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Network    │
                    │ (Seed Node) │
                    └─────────────┘
```

1. **Workers connect** to pool server
2. **Pool assigns jobs** (block templates)
3. **Workers mine** and submit shares
4. **When block found** → Reward distributed to ALL workers based on shares
5. **Block submitted** to network

### Reward Distribution

When any worker finds a valid block:
- **Pool Fee**: Dynamic 1-10% (more workers = lower fee)
- **Workers**: 90-99% split proportionally based on shares
- **Network Fee**: Deducted from each payout (Bitcoin-style)
- **Coinbase Maturity**: 100 blocks (~4 hours) before payout

**Bitcoin-Style Payout**: Network transaction fees are deducted from the miner's payout, not from the pool fee. This matches Bitcoin pool behavior where the miner receives their share minus the dynamic network fee.

**Payout System:**
- **Automatic**: Payouts sent when coinbase matures (100 confirmations)
- **Partial Payouts**: If pool has limited mature balance, pays what's available
- **Minimum Payout**: 1 SALO
- **Persistent Stats**: Pending payouts saved on shutdown, restored on restart

**Dynamic Pool Fee Tiers:**
| Workers | Fee | Workers Keep |
|---------|-----|-------------|
| 1 | 10% | 90% |
| 5 | 5% | 95% |
| 10 | 3% | 97% |
| 20 | 2% | 98% |
| 50 | 1.5% | 98.5% |
| 100+ | 1% | 99% |

Example (100 SALO block with 10 workers @ 3% pool fee):
```
Block Reward:              100.00 SALO
Pool Fee (3%):              -3.00 SALO
Workers Pool:               97.00 SALO

Worker 1: 500 shares (50%) → 48.50 - 0.00025 network fee = 48.49975 SALO
Worker 2: 300 shares (30%) → 29.10 - 0.00025 network fee = 29.09975 SALO  
Worker 3: 200 shares (20%) → 19.40 - 0.00025 network fee = 19.39975 SALO
```
Note: Network fee (0.00025 SALO minimum) is dynamic based on network congestion.

### Run Your Own Pool

**Windows:**
```batch
REM Start pool server
start-pool.bat YOUR_POOL_ADDRESS YOUR_PRIVATE_KEY 1.0
```

**Linux/Mac:**
```bash
# On your VPS/Server
./scripts/start-pool.sh YOUR_POOL_ADDRESS YOUR_PRIVATE_KEY 1.0
```

**Python:**
```bash
python -m pool.pool_server --address YOUR_POOL_ADDRESS --privkey YOUR_PRIVATE_KEY --fee 1.0 --port 7261 --http 7262
```

**Workers connect from any PC:**

Windows:
```batch
pool-worker.bat YOUR_SALO_ADDRESS MyRig --gpu
```

Linux/Mac:
```bash
python pool_worker.py --pool YOUR_SERVER_IP:7261 --address WORKER_ADDRESS --gpu
```

### Pool Stats API

The pool server exposes a JSON API for real-time statistics:

| Endpoint | URL | Protocol |
|----------|-----|----------|
| Direct (Local) | `http://pool.salocoin.org:7262` | HTTP |
| Via Seed (HTTPS) | `https://api.salocoin.org/pool_stats` | HTTPS |

```bash
# Get pool stats (direct)
curl http://pool.salocoin.org:7262

# Get pool stats (via HTTPS proxy - used by explorer)
curl https://api.salocoin.org/pool_stats
```

**Response:**
```json
{
  "pool_address": "SRwXNMAcLwDaVDsjPkqAGFgQ2cjFWnxb9W",
  "pool_fee": 1.0,
  "hashrate_formatted": "1.25 MH/s",
  "authorized_workers": 3,
  "blocks_found": 15,
  "total_shares": 50000,
  "total_rewards_formatted": "1500.00000000 SALO",
  "workers": [...],
  "pending_payouts": [...]
}
```

---

## � Decentralized Network & Auto-Sync

SALOCOIN is fully decentralized - no central server required!

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                  PEER-TO-PEER NETWORK                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│        ┌─────────┐     ┌─────────┐     ┌─────────┐         │
│        │ Node A  │◄───►│ Node B  │◄───►│ Node C  │         │
│        │  H:500  │     │  H:500  │     │  H:500  │         │
│        └─────────┘     └─────────┘     └─────────┘         │
│             ▲               ▲               ▲               │
│             └───────────────┼───────────────┘               │
│                             │                               │
│                      All synced!                            │
│                                                             │
│   • Any node can join/leave - network continues            │
│   • Each node has FULL blockchain copy                      │
│   • Auto-sync from any peer with more blocks               │
│   • "Longest valid chain" wins                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Auto-Sync Process

1. **Start node** → Connects to known seeds
2. **Compare heights** → "I'm at 0, peer is at 500"
3. **Download blocks** → Requests missing blocks
4. **Validate** → Verifies PoW and transactions
5. **Listen** → Receives new blocks as they're mined

### If Main Seed Goes Down

- ✅ Other nodes keep running with same blockchain
- ✅ Mining and transactions continue
- ✅ When main seed returns, it syncs FROM other nodes
- ✅ No data loss - everyone has full copy

> 📖 **Full guide**: See [COMMUNITY_SEED_NODE.md](COMMUNITY_SEED_NODE.md) for running your own node!

---

## �🚀 Bootstrap (Fast Sync)

New nodes can download the entire blockchain quickly using the bootstrap service.

### Download Bootstrap File

```bash
# Download gzipped bootstrap (fastest)
curl -O https://bootstrap.salocoin.org/bootstrap.dat.gz
gunzip bootstrap.dat.gz

# Or download JSON format
curl -O https://bootstrap.salocoin.org/bootstrap.json.gz
```

### Bootstrap API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/bootstrap.dat` | Binary blockchain file |
| `/bootstrap.dat.gz` | Gzipped (smaller download) |
| `/bootstrap.json` | JSON format |
| `/bootstrap/info` | File info & current height |
| `/bootstrap/latest/<height>` | Get blocks from specific height |

### Check Bootstrap Info

```bash
curl https://bootstrap.salocoin.org/bootstrap/info
```

---

## 🔄 Auto Backup (VPS)

The VPS automatically backs up blockchain data every hour using cron.

### Manual Backup

```bash
# Run backup once
python3 auto_backup.py

# List all backups
python3 auto_backup.py --list
```

### Install Hourly Cron Backup

```bash
python3 auto_backup.py --install-cron
```

### Backup Details

| Setting | Value |
|---------|-------|
| Frequency | Every hour |
| Retention | 48 backups (2 days) |
| Compression | gzip (~85% reduction) |
| Location | `/root/salocoin/backups/` |
| Log | `/var/log/salocoin_backup.log` |

---

## 🌐 Run a Public Node

Help decentralize the SALOCOIN network by running your own node! Your node will:
- Sync and store the blockchain
- Serve wallets and miners
- Relay transactions and blocks
- Strengthen network security

### Quick Start

**Windows:**
```batch
run-node.bat
```

**Linux/Mac:**
```bash
chmod +x run-node.sh
./run-node.sh
```

**Python:**
```bash
# Install dependencies
pip install requests

# Run node (localhost only)
python run_node.py

# Run with external access (for public nodes)
python run_node.py --public --port 7339
```

### Node Options

| Option | Description |
|--------|-------------|
| `--port 7339` | Port to listen on (default: 7339) |
| `--public` | Accept external connections & register with network |
| `--datadir ./mydata` | Custom blockchain data directory |
| `--seed http://ip:port` | Additional seed node to connect to |
| `--mine` | Enable solo mining |
| `--threads N` | Mining threads (default: 1) |

> 💡 **Network Visibility:** When running with `--public`, your node automatically registers with the main seed and appears on the [Block Explorer](https://salocoin.org/explorer.html) peer list!

### API Endpoints

Your node serves these endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Node status and blockchain info |
| `/height` | GET | Current block height |
| `/blocks` | GET | All blocks |
| `/block/<n>` | GET | Block at height n |
| `/mempool` | GET | Pending transactions |
| `/utxos/<address>` | GET | Unspent outputs for address |
| `/balance/<address>` | GET | Balance for address |
| `/difficulty` | GET | Current mining difficulty |
| `/peers` | GET | List of active network peers |
| `/info` | GET | Network info |
| `/fee_estimate` | GET | Dynamic fee estimates (fast/normal/economy) |
| `/fee_estimate/<priority>` | GET | Fee estimate for priority (fast/normal/economy) |
| `/submit_block` | POST | Submit mined block |
| `/submit_tx` | POST | Submit transaction |
| `/sync` | POST | Sync blocks from a height |

### Example: Run Public Node on VPS

```bash
# On your VPS (Ubuntu/Debian)
git clone https://github.com/salocoin/salocoin.git
cd salocoin
pip3 install -r requirements.txt

# Run public node (accepts connections from anywhere)
python3 run_node.py --public --port 7339

# Run in background with screen
screen -S salocoin-node
python3 run_node.py --public --port 7339
# Press Ctrl+A, D to detach
```

### Test Your Node

```bash
# Check status
curl http://localhost:7339/status

# Get blockchain height
curl http://localhost:7339/height

# Get block info
curl http://localhost:7339/block/0
```

---

## Features

### ✅ Masternode Network
- **15,000 SALO Collateral** - Stake and earn 60% of block rewards
- **Deterministic Payments** - Fair, predictable payment queue
- **Masternode Governance** - Vote on proposals and budget allocation

### ⚡ InstantSend
- **Near-Instant Confirmations** - Transactions locked in seconds
- **Quorum-Based Locking** - Secured by masternode consensus
- **Double-Spend Protection** - Cryptographic guarantees

### 🔒 PrivateSend
- **CoinJoin Mixing** - Enhanced transaction privacy
- **Multiple Denominations** - 10, 1, 0.1, 0.01 SALO
- **Trustless Mixing** - No central coordinator

### 🏛️ Governance
- **Decentralized Proposals** - Community-driven development
- **Budget System** - 10% treasury for ecosystem growth
- **Superblock Payouts** - Automatic proposal funding

### 🛡️ Security
- **SHA-256d Algorithm** - Bitcoin-compatible double hashing
- **Dark Gravity Wave v3** - Responsive difficulty adjustment (every block, 24-block window)
- **Chain Reorganization Protection** - Max 100 block reorg depth
- **Coinbase Maturity** - 100 confirmations before spending mined coins
- **Median Time Past (MTP)** - 11-block median timestamp validation
- **Difficulty Bounds** - Enforced min/max difficulty to prevent manipulation
- **Future Block Limit** - Blocks cannot be >2 hours in future
- **Hardcoded Genesis** - Network rejects invalid chains
- **Spork System** - Network-wide feature activation

### ⛏️ Mining
- **GPU Mining** - OpenCL support for 200+ MH/s (NVIDIA/AMD)
- **CPU Mining** - Multi-threaded solo mining
- **Pool Mining** - Distributed mining with proportional rewards
- **Dynamic Pool Fee** - 1-10% (more workers = lower fee)
- **Bitcoin-Style Payouts** - Network fees deducted from miner payouts
- **Dynamic Network Fees** - Adjusts based on mempool congestion
- **Public Pool** - Connect to `pool.salocoin.org:7261`

### 🖥️ Desktop Wallet
- **Modern GUI** - Beautiful CustomTkinter interface
- **GPU/CPU Mining** - Solo and pool mining with toggle switch
- **HD Wallet** - BIP32/39/44 hierarchical deterministic
- **QR Code Scanning** - Scan addresses with camera
- **Cross-Platform** - Windows executable available

### 🌐 Block Explorer
- **Live Website** - [salocoin.org/explorer.html](https://salocoin.org/explorer.html)
- **Search** - Blocks, transactions, addresses
- **Pending Transactions** - View mempool in real-time
- **Pagination** - Browse all blocks easily

---

## 🖥️ Desktop Wallet

Download the SALOCOIN Desktop Wallet for a full-featured GUI experience.

### Features

- ✅ Create/Import HD wallets with 24-word recovery phrase
- ✅ Send and receive SALO with one click
- ✅ QR code scanning for recipient addresses
- ✅ View transaction history and balance
- ✅ **GPU Mining** - Toggle between GPU and CPU for solo/pool mining
- ✅ **Solo Mining** - Mine blocks directly to your wallet
- ✅ **Pool Mining** - Connect to mining pool with real-time stats
- ✅ Dark modern interface

### Download

| Platform | Download |
|----------|----------|
| Windows | `SALOCOIN-Wallet.exe` |
| Pool Worker | `SALOCOIN-Pool-Worker.exe` |

### Build from Source

```bash
cd desktop
pip install -r requirements.txt
pip install pyopencl numpy  # For GPU mining
python salocoin_wallet.py
```

### Build EXE (Windows)

```bash
cd desktop
pip install pyinstaller
pyinstaller --onefile --windowed --name "SALOCOIN-Wallet" --icon "assets/icon.ico" salocoin_wallet.py
```

The executable will be in `desktop/dist/SALOCOIN-Wallet.exe`

---

## 🔍 Block Explorer

Explore the SALOCOIN blockchain at [salocoin.org/explorer.html](https://salocoin.org/explorer.html)

### Features

- **Network Stats** - Block height, difficulty, supply
- **Pool Stats** - Live mining pool information (workers, hashrate, rewards)
- **Recent Blocks** - Paginated list with details
- **Pending Transactions** - View unconfirmed transactions
- **Transaction Details** - Full inputs/outputs breakdown
- **Address Lookup** - Balance, UTXOs, transaction history
- **Search** - Find by block height, hash, txid, or address

### Self-Host

```bash
cd website
# Serve with any HTTP server
python -m http.server 8080
```

---

## 🌐 Run Your Own Seed Node

Want to help decentralize the network? Run your own seed node!

### Quick Setup (VPS)

```bash
# Clone repo
git clone https://github.com/saloscoin/open-source.git salocoin
cd salocoin

# Install dependencies
pip3 install -r requirements.txt

# Run seed node
python3 salocoind.py --rpcbind=0.0.0.0
```

### Automated Setup (Ubuntu/Debian)

```bash
bash setup-seed-node.sh
```

This creates a systemd service that runs 24/7.

### Genesis Block (MUST MATCH)

All nodes use this hardcoded genesis - ensuring everyone is on the same network:

```
Genesis Hash: c52fd198c676978ce4d71d325b2e7703dc302e13621efb7efefe527a04793c0b
Merkle Root: ab259459bfb5bd1fce4297f6f031c33769ec1980cb7c4a510eaf838d8b2789ff
Timestamp: 1735689600 (January 1, 2025)
```

**Do not modify `config.py` genesis settings!** Nodes with different genesis will be rejected.

📖 **Full guide**: [SEED_NODE_SETUP.md](SEED_NODE_SETUP.md)

---

## Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

```bash
# Clone repository
git clone https://github.com/saloscoin/open-source.git
cd open-source

# Install dependencies
pip install -r requirements.txt

# Verify installation
python setup.py check
```

### Option 1: Run Directly (Recommended)

```bash
# Windows
python salocoin-wallet.py create my_wallet
python salocoin-miner.py start -a YOUR_ADDRESS
python salocoind-cli.py status

# Linux/macOS
python3 salocoin-wallet.py create my_wallet
python3 salocoin-miner.py start -a YOUR_ADDRESS
python3 salocoind-cli.py status
```

### Option 2: Use Batch Files (Windows)

```batch
salocoin-wallet.bat create my_wallet
salocoin-miner.bat start -a YOUR_ADDRESS
salocoind.bat status
```

### Option 3: Add to PATH

**Windows (PowerShell as Admin):**
```powershell
# Add to PowerShell profile for permanent aliases
Add-Content $PROFILE "function salocoin-wallet { python `"$PWD\salocoin-wallet.py`" @args }"
Add-Content $PROFILE "function salocoin-miner { python `"$PWD\salocoin-miner.py`" @args }"
Add-Content $PROFILE "function salocoind { python `"$PWD\salocoind-cli.py`" @args }"
```

**Linux/macOS:**
```bash
chmod +x salocoin-wallet.py salocoin-miner.py salocoind-cli.py
sudo ln -sf $(pwd)/salocoin-wallet.py /usr/local/bin/salocoin-wallet
sudo ln -sf $(pwd)/salocoin-miner.py /usr/local/bin/salocoin-miner
sudo ln -sf $(pwd)/salocoind-cli.py /usr/local/bin/salocoind
```

### Create Your First Wallet

```bash
salocoin-wallet create default
```

This creates a new HD wallet with a 24-word recovery phrase. **Save your recovery phrase!**

### Start Mining

```bash
python salocoin-miner.py start -a YOUR_ADDRESS

# Or set default address first
python salocoin-miner.py set-address YOUR_ADDRESS
python salocoin-miner.py start
```

The miner automatically syncs with the seed node and submits mined blocks.

### Check Your Balance

```bash
salocoin-wallet balance default
```

---

## CLI Commands

SALOCOIN provides three main CLI tools:

### 🔐 Wallet (`salocoin-wallet.py`)

```bash
# Create a new wallet
python salocoin-wallet.py create <name>

# List all wallets
python salocoin-wallet.py list

# Check balance
python salocoin-wallet.py balance <name>

# Generate new address
python salocoin-wallet.py address new -n <name>

# List all addresses
python salocoin-wallet.py address list -n <name>

# Send SALO to an address
python salocoin-wallet.py send <to_address> <amount> -n <name>

# Send using custom node
python salocoin-wallet.py send <to_address> <amount> -n <name> --seed http://your-node:7339

# Check balance with custom node
python salocoin-wallet.py balance <name> --seed http://your-node:7339

# View transaction history
python salocoin-wallet.py history <name>

# Show receive address (with QR code)
python salocoin-wallet.py receive <name>

# Backup wallet (shows mnemonic)
python salocoin-wallet.py backup <name>

# Restore wallet from mnemonic
python salocoin-wallet.py restore <name>
```

### ⛏️ Miner (`salocoin-miner.py`)

```bash
# Start mining to specific address
python salocoin-miner.py start --address SjioJU3LtAPDgrcQcQvcPH4gukB7yP6Ywg

# Mine a fixed number of blocks
python salocoin-miner.py start -a YOUR_ADDRESS --blocks 10

# Short options
python salocoin-miner.py start -a SjioJU3LtAPDgrcQcQvcPH4gukB7yP6Ywg -b 5

# Use custom seed node
python salocoin-miner.py start -a YOUR_ADDRESS --seed http://your-node:7339

# Skip syncing (mine on local chain)
python salocoin-miner.py start -a YOUR_ADDRESS --nosync

# Set default mining address
python salocoin-miner.py set-address YOUR_ADDRESS

# Then just start (uses saved address)
python salocoin-miner.py start

# Check miner status
python salocoin-miner.py status
```

The miner automatically:
- Syncs blockchain from seed node
- Syncs mempool for pending transactions
- Includes pending TXs in mined blocks
- Submits found blocks to network

### 🖥️ Node Daemon (`salocoind-cli.py`)

```bash
# Start the node daemon (background)
python salocoind-cli.py start

# Stop the daemon
python salocoind-cli.py stop

# Check daemon status
python salocoind-cli.py status

# Get blockchain info
python salocoind-cli.py getinfo

# Sync blockchain from seed node
python salocoind-cli.py sync
```

### 🌐 Full Node (`run_node.py`)

Run a complete SALOCOIN node that serves wallets and miners:

```bash
# Run node (localhost only)
python run_node.py

# Run node with external access (public)
python run_node.py --public

# Run node + solo mining
python run_node.py --mine

# Run node on custom port
python run_node.py --port 7339

# Full public node with mining
python run_node.py --public --port 7339 --mine
```

**Node Options:**

| Option | Description |
|--------|-------------|
| `--port 7339` | Port to listen on (default: 7339) |
| `--public` | Accept external connections |
| `--mine` | Enable solo mining |
| `--datadir ./mydata` | Custom blockchain data directory |

### 🏊 Pool Worker (`pool_worker.py`)

Connect to the mining pool for shared rewards:

```bash
# Connect to official pool
python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_ADDRESS

# With worker name and threads
python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_ADDRESS --worker PC1 --threads 4
```

**Pool Worker Options:**

| Option | Description |
|--------|-------------|
| `--pool HOST:PORT` | Pool server address |
| `--address ADDR` | Your SALOCOIN address for payouts |
| `--worker NAME` | Worker name (default: hostname) |
| `--threads N` | Number of mining threads |

### 🏗️ Pool Server (`pool_server.py`)

Run your own mining pool:

```bash
# Start pool server
python pool_server.py --address YOUR_POOL_ADDRESS --port 7261

# With custom settings
python pool_server.py --address YOUR_ADDRESS --port 7261 --fee 1.0 --difficulty 1
```

**Pool Server Options:**

| Option | Description |
|--------|-------------|
| `--address ADDR` | Pool operator address |
| `--port 7261` | Stratum port |
| `--http-port 7262` | Stats HTTP API port |
| `--fee 5.0` | Base pool fee percentage (default: 5%) |
| `--dynamic-fee` | Enable dynamic fee (1-10% based on workers) |
| `--fixed-fee` | Disable dynamic fee, use fixed fee |
| `--difficulty 1` | Initial share difficulty |

---

## Mining

SALOCOIN uses SHA-256d (double SHA-256) proof-of-work algorithm.

### Solo Mining

```bash
# Create wallet if you haven't
python salocoin-wallet.py create miner

# Start mining (uses wallet address)
python salocoin-miner.py --wallet miner

# Or mine to specific address
python salocoin-miner.py --address SjioJU3LtAPDgrcQcQvcPH4gukB7yP6Ywg
```

Mining rewards: **100 SALO per block** (halves every 210,000 blocks)

### Pool Mining

```bash
# Create wallet for payouts
python salocoin-wallet.py create pool_wallet

# Get your address
python salocoin-wallet.py receive pool_wallet

# Connect to pool
python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_ADDRESS --threads 4
```

### Seed Node Sync

The miner automatically:
- Syncs blockchain from seed node on startup
- Syncs mempool for pending transactions
- Submits mined blocks to seed node
- Background sync every 60 seconds

### Mining Statistics

```bash
salocoin-miner status
```

Shows:
- Total blocks mined
- Total rewards earned
- Current blockchain height
- Mining difficulty

---

## Wallet Management

### HD Wallet (BIP32/39/44)

SALOCOIN uses hierarchical deterministic wallets:

- **24-word mnemonic** - Recovery phrase
- **BIP44 path** - `m/44'/9339'/0'/0/0`
- **Unlimited addresses** - Derived from single seed

### Backup Your Wallet

```bash
salocoin-wallet backup <name>
```

**⚠️ IMPORTANT:** Write down your 24-word recovery phrase and store it safely. This is the ONLY way to recover your wallet!

### Restore From Backup

```bash
salocoin-wallet restore <name>
# Enter your 24-word recovery phrase when prompted
```

---

## Transactions

### Send SALO

```bash
salocoin-wallet send <address> <amount> -n <wallet_name>
```

Example:
```bash
salocoin-wallet send SjioJU3LtAPDgrcQcQvcPH4gukB7yP6Ywg 10.5 -n default
```

### Transaction Auto-Sync

Transactions are automatically:
1. Added to local mempool
2. Submitted to seed node
3. Synced to all miners
4. Confirmed when included in a mined block

```bash
# Mine a block to confirm pending transactions
salocoin-miner start
```

---

## Seed Node Network

SALOCOIN uses a seed node for blockchain synchronization between miners.

### Public Seed Node

| Parameter | Value |
|-----------|-------|
| **URL** | `https://api.salocoin.org` |
| **Port** | `443` (HTTPS) |
| **Backup** | `https://seed.salocoin.org` |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Node status, height, difficulty |
| `/blocks` | GET | List all blocks |
| `/block/<n>` | GET | Block at height n |
| `/mempool` | GET | Pending transactions |
| `/utxos/<address>` | GET | Unspent outputs for address |
| `/balance/<address>` | GET | Balance for address |
| `/pool_stats` | GET | Mining pool statistics |
| `/submit_block` | POST | Submit mined block |
| `/submit_tx` | POST | Submit transaction |
| `/sync` | POST | Sync blocks from height |
| `/sync_mempool` | POST | Sync mempool transactions |

### Check Seed Node Status

```bash
curl https://api.salocoin.org/status
```

---

## Genesis Block

The genesis block is **hardcoded** and cannot be modified. Any attempt to use a different genesis block will be rejected by the network.

```
Genesis Hash: c52fd198c676978ce4d71d325b2e7703dc302e13621efb7efefe527a04793c0b
Genesis Timestamp: January 1, 2025 00:00:00 UTC
Genesis Message: "SALOCOIN Genesis - Enterprise Masternode Cryptocurrency"
```

---

## Configuration

### Data Directories

| OS | Location |
|----|----------|
| Windows | `%APPDATA%\Salocoin\` |
| Linux | `~/.salocoin/` |
| macOS | `~/Library/Application Support/Salocoin/` |

### Local Data Structure

```
salocoin/
├── data/                   # Blockchain data
│   ├── blocks.dat          # Block storage
│   ├── mempool.json        # Pending transactions
│   └── miner.json          # Miner config
├── wallets/                # Wallet files
│   ├── default.json
│   └── my_wallet.json
└── backups/                # Wallet backups
```

---

## API Reference

### RPC Methods

When daemon is running, RPC is available on port 7340:

| Method | Description |
|--------|-------------|
| `getinfo` | Node information |
| `getblockchaininfo` | Blockchain info |
| `getblockcount` | Current block height |
| `getbestblockhash` | Latest block hash |
| `getblock <hash>` | Block details |
| `getmempoolinfo` | Mempool info |
| `stop` | Stop daemon |

---

## Development

### Run Tests

```bash
pytest tests/ -v
```

### Project Structure

```
salocoin/
├── core/                   # Core blockchain logic
│   ├── blockchain.py       # Block & chain management
│   ├── crypto.py           # Cryptographic functions
│   ├── transaction.py      # Transaction handling
│   └── wallet.py           # HD wallet implementation
├── network/                # P2P networking
├── masternode/             # Masternode features
├── rpc/                    # RPC server
├── pool/                   # Mining pool implementation
├── desktop/                # Desktop wallet GUI
│   ├── salocoin_wallet.py  # Main wallet application
│   └── assets/             # Icons and images
├── website/                # Block explorer website
│   ├── index.html          # Landing page
│   ├── explorer.html       # Block explorer
│   ├── wallet.html         # Web wallet
│   └── css/js/assets/      # Static files
├── sync.py                 # Seed node sync client
├── seed_server.py          # Seed node HTTP server
├── pool_server.py          # Mining pool server
├── pool_worker.py          # Mining pool worker
├── salocoin-wallet.py      # Wallet CLI
├── salocoin-miner.py       # Miner CLI
└── salocoind.py            # Daemon CLI
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Support

- **GitHub Issues:** Report bugs and feature requests
- **Documentation:** See `/docs` folder
- **Community:** Join our Discord/Telegram

---

<p align="center">
  <strong>SALOCOIN</strong> - Enterprise-Grade Masternode Cryptocurrency
</p>
