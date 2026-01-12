# SALOCOIN Seed Node Setup Guide

This guide explains how to run your own SALOCOIN seed node and connect to the main network.

## 🌐 Network Overview

- **Coin**: SALOCOIN (SALO)
- **Algorithm**: SHA-256d (double SHA-256)
- **Block Time**: 150 seconds (2.5 minutes)
- **Block Reward**: 100 SALO (halves every 210,000 blocks)
- **Max Supply**: 39,000,000 SALO
- **P2P Port**: 7339
- **RPC Port**: 7340

## 🔒 Genesis Block (HARDCODED)

All nodes MUST use this exact genesis block to be on the same network:

```
Genesis Hash: c52fd198c676978ce4d71d325b2e7703dc302e13621efb7efefe527a04793c0b
Merkle Root: ab259459bfb5bd1fce4297f6f031c33769ec1980cb7c4a510eaf838d8b2789ff
Timestamp: 1735689600 (January 1, 2025 00:00:00 UTC)
```

This is already hardcoded in `config.py` - do not modify it!

---

## 📦 Quick Setup (VPS/Server)

### 1. Requirements

- Ubuntu 20.04/22.04 or Debian 11+
- Python 3.11+
- 2GB RAM minimum
- 20GB disk space
- Open ports: 7339 (P2P), 7340 (RPC)

### 2. Clone Repository

```bash
# Clone the official repo
git clone https://github.com/saloscoin/open-source.git salocoin
cd salocoin

# Install Python dependencies
pip3 install -r requirements.txt
```

### 3. Run Seed Node

```bash
# Simple start
python3 salocoind.py

# With RPC enabled for API access
python3 salocoind.py --rpcbind=0.0.0.0 --rpcuser=admin --rpcpassword=YOUR_SECURE_PASSWORD

# As background daemon (Linux only)
python3 salocoind.py --daemon --printtoconsole
```

### 4. Verify Genesis

Your node will automatically use the correct genesis block from `config.py`. Check the logs:

```
SALOCOIN Core v1.0.0
Network: Mainnet
Genesis: c52fd198c676978ce4d71d325b2e7703dc302e13621efb7efefe527a04793c0b
```

---

## 🖥️ Detailed VPS Setup

### Step 1: Prepare Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y python3.11 python3.11-pip python3.11-venv git

# Create non-root user (recommended)
sudo adduser salocoin
sudo usermod -aG sudo salocoin
su - salocoin
```

### Step 2: Install SALOCOIN

```bash
# Clone repository
cd ~
git clone https://github.com/saloscoin/open-source.git salocoin
cd salocoin

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Firewall

```bash
# Allow P2P and RPC ports
sudo ufw allow 7339/tcp  # P2P
sudo ufw allow 7340/tcp  # RPC (optional, for API)
sudo ufw enable
```

### Step 4: Create Systemd Service

```bash
sudo nano /etc/systemd/system/salocoind.service
```

Paste this content:

```ini
[Unit]
Description=SALOCOIN Daemon
After=network.target

[Service]
Type=simple
User=salocoin
WorkingDirectory=/home/salocoin/salocoin
ExecStart=/home/salocoin/salocoin/venv/bin/python salocoind.py --rpcbind=0.0.0.0 --rpcuser=admin --rpcpassword=CHANGE_THIS_PASSWORD
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable salocoind
sudo systemctl start salocoind

# Check status
sudo systemctl status salocoind

# View logs
journalctl -u salocoind -f
```

---

## 🔗 Connect to Main Network

### Add Seed Nodes

Edit `config.py` and add known seed nodes:

```python
SEED_NODES = [
    "api.salocoin.org:7339",   # Official seed node
    "YOUR_IP:7339",            # Your node
]
```

Or connect via command line:

```bash
python3 salocoind.py --addnode=api.salocoin.org:7339
```

### Sync Blockchain

Your node will automatically:
1. Connect to seed nodes
2. Download the blockchain
3. Verify all blocks against the genesis hash
4. Start accepting/relaying transactions

---

## 🌍 Expose as Public API (Optional)

To run a public API like `api.salocoin.org`:

### 1. Install Nginx

```bash
sudo apt install nginx
```

### 2. Configure Nginx Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/salocoin-api
```

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:7340;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. Enable HTTPS with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.yourdomain.com
```

---

## 🔧 RPC API Endpoints

Once running, your node exposes these endpoints:

| Endpoint | Description |
|----------|-------------|
| GET `/status` | Network status (height, difficulty, mempool) |
| GET `/blocks` | Recent blocks with transactions |
| GET `/block/{height}` | Single block by height |
| POST `/submit_block` | Submit mined block |
| POST `/submit_tx` | Submit transaction |

Example:
```bash
curl http://localhost:7340/status
```

---

## ⛏️ Mining to Your Node

Once your node is synced, anyone can mine to it:

```bash
# Point miner at your node
python3 salocoin-miner.py start --address YOUR_SALO_ADDRESS --node http://YOUR_IP:7340
```

---

## 📋 Checklist for New Seed Node Operators

- [ ] Clone from official GitHub: `github.com/saloscoin/open-source`
- [ ] Do NOT modify `config.py` genesis block settings
- [ ] Open port 7339 (P2P) for peer connections
- [ ] Sync fully before enabling mining
- [ ] Add your node to `SEED_NODES` and submit PR to help network

---

## 🤝 Adding Your Node to the Network

To add your seed node to the official list:

1. Run your node 24/7 reliably
2. Fork the GitHub repo
3. Add your IP to `SEED_NODES` in `config.py`
4. Submit a Pull Request

Your node will then be discovered by all SALOCOIN users!

---

## 🆘 Troubleshooting

### "Genesis block mismatch"
- You modified `config.py` - reset to original from GitHub
- Wrong branch - use `main` branch

### "Cannot connect to peers"
- Check firewall: `sudo ufw status`
- Verify port 7339 is open
- Try adding seed node manually: `--addnode=api.salocoin.org:7339`

### "Blockchain not syncing"
- Check internet connection
- Verify seed nodes are online
- Run with `--printtoconsole` to see detailed logs

---

## 📞 Contact

- GitHub: https://github.com/saloscoin/open-source
- Website: https://salocoin.org
