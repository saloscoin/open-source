# 🌐 SALOCOIN Community Seed Node Guide

Run your own SALOCOIN seed node and help decentralize the network!

**Network Status**: 🟢 LIVE (Mainnet launched January 2026)

## Why Run a Seed Node?

- **Strengthen the network** - More nodes = more resilient
- **Support decentralization** - No single point of failure
- **Faster local access** - Your wallet connects to your own node
- **Full blockchain copy** - You own a complete copy of all data
- **No central database** - Pure peer-to-peer architecture

---

## Quick Start (5 Minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/saloscoin/open-source.git salocoin
cd salocoin
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Your Node

```bash
# Sync from main seed and run your node (public mode enables network registration)
python run_node.py --seed https://api.salocoin.org --public --port 7339
```

Your node will:
1. Download the full blockchain from the main seed
2. Verify all blocks and transactions
3. Start serving on port 7339
4. **Auto-register with the main seed** (visible on explorer)
5. Accept connections from wallets and other nodes
6. Send periodic heartbeats to stay in the peer list

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SALOCOIN Network                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐  │
│   │ Main Seed   │◄───►│ Your Node   │◄───►│ Other Nodes │  │
│   │ (VPS)       │     │ (Your PC)   │     │ (Community) │  │
│   └─────────────┘     └─────────────┘     └─────────────┘  │
│         │                   │                   │          │
│         └───────────────────┼───────────────────┘          │
│                             │                              │
│                     ┌───────▼───────┐                      │
│                     │   Wallets     │                      │
│                     │ (Desktop/Web) │                      │
│                     └───────────────┘                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Points:**
- All nodes are equal - no central authority
- Each node stores complete blockchain locally
- Nodes sync with each other automatically
- If one node goes down, network continues

---

## Data Storage

Your node stores everything locally - **no central database needed**:

| File | Description | Location |
|------|-------------|----------|
| `data/blocks.dat` | Full blockchain (all blocks) | Your PC |
| `data/mempool.json` | Pending transactions | Your PC |
| `data/peers.json` | Known peer nodes | Your PC |

**Storage Requirements:**
- Current blockchain: ~1-5 MB (early stage)
- Growth: ~10-50 MB per year (estimated)

---

## Node Options

```bash
python run_node.py [OPTIONS]

Options:
  --seed URL        Initial seed node to sync from (default: https://api.salocoin.org)
  --port PORT       Port to listen on (default: 7339)
  --public          Accept external connections (required for public node)
  --datadir PATH    Custom data directory
```

### Examples

```bash
# Local node (only your PC can connect)
python run_node.py

# Public node (anyone can connect)
python run_node.py --public --port 7339

# Custom data directory
python run_node.py --datadir /path/to/data

# Connect to specific seed
python run_node.py --seed http://other-node:7339
```

---

## API Endpoints

Your node provides these API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Node status and blockchain info |
| `/height` | GET | Current blockchain height |
| `/blocks` | GET | All blocks (paginated) |
| `/block/<n>` | GET | Block at height n |
| `/block/hash/<hash>` | GET | Block by hash |
| `/genesis` | GET | Genesis block |
| `/tip` | GET | Latest block |
| `/mempool` | GET | Pending transactions |
| `/difficulty` | GET | Current mining difficulty |
| `/balance/<address>` | GET | Address balance |
| `/utxos/<address>` | GET | Unspent outputs |
| `/tx/<txid>` | GET | Transaction by ID |
| `/submit_block` | POST | Submit mined block |
| `/submit_tx` | POST | Submit transaction |
| `/peers` | GET | List of active network peers |
| `/fee_estimate` | GET | Dynamic fee estimates (fast/normal/economy) |
| `/fee_estimate/<priority>` | GET | Fee estimate for priority (fast/normal/economy) |
| `/register_peer` | POST | Register as network peer |
| `/heartbeat` | POST | Send heartbeat to stay online |
| `/add_peer` | POST | Add new peer |
| `/sync` | POST | Sync blocks from height |

### Network Visibility

When you run with `--public`, your node automatically:
1. **Registers** with the main seed server
2. **Sends heartbeats** every 5 minutes to stay online
3. **Appears on the explorer** at https://salocoin.org/explorer.html

Your node ID is stored in `node_id.txt` and persists across restarts.

### Test Your Node

```bash
# Check status
curl http://localhost:7339/status

# Get height
curl http://localhost:7339/height

# Get latest block
curl http://localhost:7339/tip

# Get fee estimates
curl http://localhost:7339/fee_estimate
```

### Dynamic Fee Estimation

Your node provides Bitcoin-style dynamic fee estimation:

```bash
# All fee estimates
curl http://localhost:7339/fee_estimate

# Specific priority
curl http://localhost:7339/fee_estimate/fast
curl http://localhost:7339/fee_estimate/normal
curl http://localhost:7339/fee_estimate/economy
```

| Priority | Target Blocks | Multiplier | Description |
|----------|---------------|------------|-------------|
| **fast** | 1-2 | 2.0x | High priority, confirmed quickly |
| **normal** | 3-6 | 1.0x | Standard priority |
| **economy** | 7+ | 0.5x | Low priority, cheaper fees |

**Fee Factors:**
- Mempool size (more pending txs = higher fees)
- Recent block fill rate (>80% full = higher fees)
- Median accepted fees from recent blocks

**Bitcoin-Style Pool Payouts:**
Pool mining payouts use dynamic network fees deducted from the miner's share (not the pool fee). Minimum network fee: 250 sats (0.0000025 SALO).

---

## Run on VPS (Production)

For a 24/7 public node, deploy on a VPS:

### 1. Server Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 core | 2+ cores |
| RAM | 512 MB | 1+ GB |
| Storage | 1 GB | 10+ GB |
| OS | Ubuntu 20.04+ | Ubuntu 22.04 |

### 2. Setup Commands

```bash
# Update system
apt update && apt upgrade -y

# Install Python
apt install python3 python3-pip git -y

# Clone repo
git clone https://github.com/saloscoin/open-source.git /root/salocoin
cd /root/salocoin

# Install dependencies
pip3 install -r requirements.txt

# Run in background
nohup python3 run_node.py --seed https://api.salocoin.org --public --port 7339 > node.log 2>&1 &
```

### 3. Systemd Service (Auto-Start)

Create `/etc/systemd/system/salocoin-node.service`:

```ini
[Unit]
Description=SALOCOIN Seed Node
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/salocoin
ExecStart=/usr/bin/python3 run_node.py --seed https://api.salocoin.org --public --port 7339
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable salocoin-node
systemctl start salocoin-node
systemctl status salocoin-node
```

### 4. Firewall

```bash
ufw allow 7339/tcp
ufw enable
```

---

## 🔄 How Auto-Sync Works

SALOCOIN uses **automatic peer-to-peer synchronization** - no central database required!

### Sync Process

```
┌─────────────────────────────────────────────────────────────┐
│                     AUTO-SYNC PROCESS                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Your node starts → Connects to seed.salocoin.org       │
│  2. Exchanges heights → "I'm at 0, you're at 500"          │
│  3. Requests blocks → Downloads blocks 1-500               │
│  4. Validates each → Checks PoW, transactions, hashes      │
│  5. Synced! → Now at same height as network                │
│  6. Listens → Receives new blocks as they're mined         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### What Happens If Main Seed Goes Down?

```
SCENARIO: Main seed offline, network continues mining

Network Before:
  Main Seed (H:500) ←→ Node A (H:500) ←→ Node B (H:500)

Main Goes Offline:
  Main Seed (OFFLINE) | Node A (H:500) ←→ Node B (H:500)

Network Continues Without Main:
  Mining continues → Node A (H:550) ←→ Node B (H:550)

Main Comes Back Online:
  Main Seed (H:500) → Connects to Node A (H:550)
  Main Seed: "Send me blocks 501-550"
  Node A: Sends blocks 501-550
  Main Seed: Now synced at H:550!
```

**Key Points:**
- ✅ Every node has complete blockchain copy
- ✅ Nodes sync from ANY peer with more blocks
- ✅ Network survives any single node failure
- ✅ "Longest valid chain" rule (most proof-of-work wins)
- ✅ Auto-sync runs every 10 seconds in background

### Sync Messages You'll See

```
Connecting to seed.salocoin.org:9339...
Connected! Local height: 0, Peer height: 500
Syncing blocks...
Received block 1/500
Received block 100/500
Received block 500/500
✓ Sync complete! Height: 500
Listening for new blocks...

[Later]
New block 501 received from peer
New block 502 received from peer
```

---

## Chain Reorganization Protection

SALOCOIN includes Bitcoin-style chain reorganization:

| Parameter | Value | Description |
|-----------|-------|-------------|
| MAX_REORG_DEPTH | 100 blocks | Maximum rollback depth |
| Chain Selection | Most work wins | Longest chain with most PoW |
| Transaction Recovery | Automatic | Rolled back txs return to mempool |

**How it works:**
1. If a competing chain has more work, your node evaluates it
2. If reorg depth ≤ 100 blocks and new chain is valid → Switch
3. Rolled back transactions go back to mempool
4. Deep reorgs (>100 blocks) are rejected for security

---

## Connect Your Wallet

Once your node is running, point your wallet to it:

### Desktop Wallet

Edit settings and change node URL to:
```
http://localhost:7339
```

### Web Wallet

Configure to use your node URL.

---

## Troubleshooting

### Node won't start
```bash
# Check if port is in use
lsof -i :7339

# Kill existing process
pkill -f run_node.py
```

### Not syncing
```bash
# Check connectivity to main seed
curl https://api.salocoin.org/status

# Check your node's height
curl http://localhost:7339/height
```

### View logs
```bash
tail -f node.log
```

---

## Network Stats

Check the official network:

| Service | URL |
|---------|-----|
| Explorer | https://salocoin.org/explorer.html |
| API | https://api.salocoin.org/status |
| Pool | https://pool.salocoin.org |

---

## Contributing

1. Fork the repository
2. Run your own seed node
3. Report issues on GitHub
4. Submit pull requests

---

## Resources

- **Website**: https://salocoin.org
- **GitHub**: https://github.com/salocoin/salocoin
- **Explorer**: https://salocoin.org/explorer.html

---

## ASIC Mining Endpoints

Connect your SHA-256d ASICs to mine SALOCOIN:

**Pool Mining** (shared rewards):
```
# TCP
stratum+tcp://pool.salocoin.org:7261
Worker: YOUR_SALO_ADDRESS.rig1
Password: x

# SSL (recommended)
stratum+ssl://pool.salocoin.org:7263
Worker: YOUR_SALO_ADDRESS.rig1
Password: x
```

**Solo Mining** (100% reward to you):
```
# TCP
stratum+tcp://solo.salocoin.org:3333
Worker: YOUR_SALO_ADDRESS
Password: x

# SSL (recommended)
stratum+ssl://solo.salocoin.org:3334
Worker: YOUR_SALO_ADDRESS
Password: x
```

| Type | TCP Port | SSL Port | Fee | Reward |
|------|----------|----------|-----|--------|
| Pool | 7261 | 7263 | 1-10% | Shared by work |
| Solo | 3333 | 3334 | 0% | 100 SALO to you |

---

## License

MIT License - Free to use, modify, and distribute.

---

**Thank you for supporting SALOCOIN decentralization!** 🚀
