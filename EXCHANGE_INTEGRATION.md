# SALOCOIN Exchange Integration Guide

## Overview

SALOCOIN is a SHA-256 Proof of Work cryptocurrency designed for fast, secure transactions. This document provides all information needed for exchange integration.

## Coin Specifications

| Property | Value |
|----------|-------|
| **Name** | SALOCOIN |
| **Ticker** | SALO |
| **Algorithm** | SHA-256 |
| **Consensus** | Proof of Work |
| **Block Time** | 150 seconds (2.5 minutes) |
| **Block Reward** | 100 SALO |
| **Max Supply** | 21,000,000 SALO |
| **Decimals** | 8 |
| **Address Prefix** | S (P2PKH), 3 (P2SH) |
| **Coinbase Maturity** | 100 blocks |
| **Recommended Confirmations** | 6 |

## Network Information

### Mainnet

| Service | Port | Protocol |
|---------|------|----------|
| P2P | 9339 | TCP Socket |
| JSON-RPC | 7340 | HTTP |
| REST API | 7339 | HTTP |

### Testnet

| Service | Port | Protocol |
|---------|------|----------|
| P2P | 17339 | TCP Socket |
| JSON-RPC | 17340 | HTTP |
| REST API | 17339 | HTTP |

### Seed Nodes

```
api.salocoin.org:9339
seed.salocoin.org:9339
bootstrap.salocoin.org:9339
```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Exchange Node

**Windows:**
```batch
exchange-node.bat --rpcuser exchange --rpcpassword YOUR_SECRET_PASSWORD
```

**Linux:**
```bash
python exchange_node.py --rpcuser exchange --rpcpassword YOUR_SECRET_PASSWORD
```

### 3. Verify Node is Running

```bash
curl http://localhost:7339/health
```

Response:
```json
{
  "status": "healthy",
  "uptime": 120,
  "checks": {
    "blockchain": true,
    "mempool": true,
    "p2p": true,
    "rpc": true
  }
}
```

---

## JSON-RPC Interface

SALOCOIN's RPC interface is Bitcoin-compatible. Exchanges can use existing Bitcoin integration code with minimal modifications.

### Authentication

```
URL: http://rpcuser:rpcpassword@localhost:7340/
```

### Example Request

```bash
curl -X POST http://rpcuser:rpcpassword@localhost:7340/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getblockcount","params":[]}'
```

### Supported RPC Methods

#### Blockchain

| Method | Description |
|--------|-------------|
| `getblockcount` | Get current block height |
| `getbestblockhash` | Get hash of latest block |
| `getblock` | Get block data by hash |
| `getblockhash` | Get block hash by height |
| `getblockheader` | Get block header |
| `getdifficulty` | Get current mining difficulty |
| `getchaintips` | Get chain tips information |
| `verifychain` | Verify blockchain integrity |

#### Transactions

| Method | Description |
|--------|-------------|
| `getrawtransaction` | Get raw transaction data |
| `sendrawtransaction` | Broadcast transaction |
| `decoderawtransaction` | Decode raw transaction |
| `gettxout` | Get transaction output |
| `gettxoutsetinfo` | Get UTXO set information |

#### Mempool

| Method | Description |
|--------|-------------|
| `getmempoolinfo` | Get mempool statistics |
| `getrawmempool` | Get mempool transactions |

#### Wallet (if enabled)

| Method | Description |
|--------|-------------|
| `getbalance` | Get wallet balance |
| `listunspent` | List unspent outputs |
| `getnewaddress` | Generate new address |
| `sendtoaddress` | Send coins to address |
| `validateaddress` | Validate address format |

#### Network

| Method | Description |
|--------|-------------|
| `getnetworkinfo` | Get network information |
| `getpeerinfo` | Get connected peers |
| `getconnectioncount` | Get peer count |
| `addnode` | Add peer connection |
| `disconnectnode` | Disconnect peer |

---

## REST API Reference

The REST API provides a simpler interface for integration.

### Health & Status

#### GET /health
Health check for load balancers.

```bash
curl http://localhost:7339/health
```

Response:
```json
{
  "status": "healthy",
  "uptime": 3600,
  "checks": {
    "blockchain": true,
    "mempool": true,
    "p2p": true,
    "rpc": true
  },
  "timestamp": 1700000000
}
```

#### GET /status
Detailed node status.

```bash
curl http://localhost:7339/status
```

#### GET /readiness
Kubernetes/Docker readiness probe.

```bash
curl http://localhost:7339/readiness
```

#### GET /sync
Synchronization status.

```bash
curl http://localhost:7339/sync
```

### Blockchain

#### GET /height
Get current block height.

```bash
curl http://localhost:7339/height
```

Response:
```json
{"height": 12345}
```

#### GET /block/{height_or_hash}
Get block by height or hash.

```bash
curl http://localhost:7339/block/100
curl http://localhost:7339/block/000000abc123...
```

#### GET /blocks?limit=10&offset=0
Get recent blocks with pagination.

```bash
curl "http://localhost:7339/blocks?limit=10&offset=0"
```

### Transactions

#### GET /tx/{txid}
Get transaction by ID.

```bash
curl http://localhost:7339/tx/abc123...
```

Response:
```json
{
  "txid": "abc123...",
  "confirmations": 6,
  "block_height": 12340,
  "block_hash": "000000...",
  "inputs": [...],
  "outputs": [...],
  "in_mempool": false
}
```

#### POST /tx/send
Broadcast a raw transaction.

```bash
curl -X POST http://localhost:7339/tx/send \
  -H "Content-Type: application/json" \
  -d '{"hex": "0100000001..."}'
```

Response:
```json
{
  "success": true,
  "txid": "abc123...",
  "message": "Transaction accepted"
}
```

#### POST /tx/decode
Decode raw transaction without broadcasting.

```bash
curl -X POST http://localhost:7339/tx/decode \
  -H "Content-Type: application/json" \
  -d '{"hex": "0100000001..."}'
```

### Addresses & Balances

#### GET /balance/{address}
Get address balance.

```bash
curl http://localhost:7339/balance/S1abcd...
```

Response:
```json
{
  "address": "S1abcd...",
  "balance": 1000.50000000,
  "balance_satoshi": 100050000000,
  "pending": 50.00000000,
  "pending_satoshi": 5000000000,
  "total": 1050.50000000,
  "total_satoshi": 105050000000
}
```

#### GET /utxos/{address}
Get unspent transaction outputs.

```bash
curl http://localhost:7339/utxos/S1abcd...
```

Response:
```json
{
  "address": "S1abcd...",
  "utxos": [
    {
      "txid": "abc123...",
      "vout": 0,
      "amount": 10000000000,
      "confirmations": 150,
      "is_coinbase": true,
      "is_mature": true,
      "spendable": true
    }
  ],
  "count": 1,
  "total": 100.00000000
}
```

#### GET /validate/{address}
Validate address format.

```bash
curl http://localhost:7339/validate/S1abcd...
```

Response:
```json
{
  "address": "S1abcd...",
  "isvalid": true,
  "type": "p2pkh"
}
```

### Exchange-Specific

#### GET /confirmations/{txid}
Get confirmation count for transaction.

```bash
curl http://localhost:7339/confirmations/abc123...
```

Response:
```json
{
  "txid": "abc123...",
  "confirmations": 6,
  "confirmed": true,
  "block_height": 12340,
  "block_hash": "000000...",
  "is_coinbase": false,
  "mature": true
}
```

#### GET /info
Get coin information for listing.

```bash
curl http://localhost:7339/info
```

Response:
```json
{
  "name": "SALOCOIN",
  "ticker": "SALO",
  "algorithm": "SHA-256",
  "consensus": "Proof of Work",
  "block_time_seconds": 150,
  "block_reward": 100,
  "max_supply": 21000000,
  "decimals": 8,
  "min_confirmations": 6,
  "coinbase_maturity": 100,
  "address_prefix": "S"
}
```

---

## Exchange Integration Workflow

### Deposit Detection

1. Generate unique deposit address for each user
2. Monitor address for incoming transactions
3. Wait for 6 confirmations before crediting

```python
import requests

def check_deposit(address, min_confirmations=6):
    resp = requests.get(f"http://localhost:7339/utxos/{address}")
    data = resp.json()
    
    confirmed_balance = 0
    for utxo in data['utxos']:
        if utxo['confirmations'] >= min_confirmations:
            if utxo['is_coinbase'] and not utxo['is_mature']:
                continue  # Skip immature coinbase
            confirmed_balance += utxo['amount']
    
    return confirmed_balance / 100000000  # Convert to SALO
```

### Withdrawal Processing

1. Create raw transaction with inputs/outputs
2. Sign transaction with private key
3. Broadcast via `/tx/send` or `sendrawtransaction`
4. Monitor for confirmations

```python
import requests

def send_withdrawal(raw_tx_hex):
    resp = requests.post(
        "http://localhost:7339/tx/send",
        json={"hex": raw_tx_hex}
    )
    data = resp.json()
    
    if data.get('success'):
        return data['txid']
    else:
        raise Exception(data.get('error', 'Transaction rejected'))
```

### Balance Monitoring

```python
import requests

def get_hot_wallet_balance(address):
    resp = requests.get(f"http://localhost:7339/balance/{address}")
    data = resp.json()
    
    return {
        'confirmed': data['balance'],
        'pending': data['pending'],
        'total': data['total']
    }
```

---

## Security Recommendations

### Node Security

1. **Firewall**: Only expose necessary ports
   ```bash
   # Allow P2P from anywhere (for blockchain sync)
   ufw allow 9339/tcp
   
   # Restrict RPC to localhost or trusted IPs
   ufw allow from 10.0.0.0/8 to any port 7340
   ```

2. **RPC Authentication**: Use strong passwords
   ```bash
   python exchange_node.py --rpcuser exchange --rpcpassword $(openssl rand -hex 32)
   ```

3. **HTTPS**: Use reverse proxy with TLS for production
   ```nginx
   server {
       listen 443 ssl;
       server_name node.exchange.com;
       
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       
       location / {
           proxy_pass http://127.0.0.1:7339;
       }
   }
   ```

### Wallet Security

1. Use **cold storage** for majority of funds
2. Hot wallet should only hold ~10% for withdrawals
3. Implement **multi-signature** for large withdrawals
4. Regular **backup** of wallet files

---

## High Availability Setup

### Multiple Nodes

Run multiple nodes for redundancy:

```bash
# Node 1 (Primary)
python exchange_node.py --p2p-port 9339 --rpc-port 7340 --api-port 7339

# Node 2 (Secondary)
python exchange_node.py --p2p-port 9340 --rpc-port 7341 --api-port 7340

# Node 3 (Backup)
python exchange_node.py --p2p-port 9341 --rpc-port 7342 --api-port 7341
```

### Load Balancer

Use HAProxy or nginx to distribute requests:

```nginx
upstream salocoin_nodes {
    server 127.0.0.1:7339;
    server 127.0.0.1:7340;
    server 127.0.0.1:7341;
}

server {
    listen 80;
    
    location /health {
        proxy_pass http://salocoin_nodes;
    }
    
    location / {
        proxy_pass http://salocoin_nodes;
    }
}
```

### Health Monitoring

Use `/health` endpoint for load balancer health checks:

```bash
# Check node health
curl -f http://localhost:7339/health || echo "Node unhealthy"
```

---

## Troubleshooting

### Common Issues

#### Node Not Syncing

1. Check peer connections:
   ```bash
   curl http://localhost:7339/sync
   ```

2. Add seed nodes manually:
   ```bash
   curl -X POST http://rpcuser:rpcpassword@localhost:7340/ \
     -d '{"method":"addnode","params":["seed.salocoin.org:9339","add"]}'
   ```

#### Transaction Not Confirming

1. Check if in mempool:
   ```bash
   curl http://localhost:7339/tx/{txid}
   ```

2. Rebroadcast transaction:
   ```bash
   curl -X POST http://localhost:7339/tx/broadcast \
     -d '{"txid": "abc123..."}'
   ```

#### Balance Not Updating

1. Check confirmations:
   ```bash
   curl http://localhost:7339/confirmations/{txid}
   ```

2. Ensure coinbase maturity (100 blocks) for mining rewards

---

## Support

- **Website**: https://salocoin.org
- **GitHub**: https://github.com/salocoin/salocoin
- **Discord**: https://discord.gg/salocoin
- **Email**: support@salocoin.org

---

## Appendix: Address Validation

### Python

```python
import hashlib
import base58

def validate_address(address):
    """Validate SALOCOIN address."""
    try:
        # Decode base58
        decoded = base58.b58decode(address)
        
        # Check length (1 version + 20 hash + 4 checksum)
        if len(decoded) != 25:
            return False
        
        # Verify checksum
        payload = decoded[:-4]
        checksum = decoded[-4:]
        expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        
        if checksum != expected:
            return False
        
        # Check version byte (S = 0x3F for SALOCOIN)
        version = decoded[0]
        if version not in [0x3F, 0x05]:  # P2PKH or P2SH
            return False
        
        return True
    except:
        return False
```

### JavaScript

```javascript
const bs58 = require('bs58');
const crypto = require('crypto');

function validateAddress(address) {
    try {
        const decoded = bs58.decode(address);
        
        if (decoded.length !== 25) return false;
        
        const payload = decoded.slice(0, -4);
        const checksum = decoded.slice(-4);
        
        const hash1 = crypto.createHash('sha256').update(payload).digest();
        const hash2 = crypto.createHash('sha256').update(hash1).digest();
        const expected = hash2.slice(0, 4);
        
        if (!checksum.equals(expected)) return false;
        
        const version = decoded[0];
        if (version !== 0x3F && version !== 0x05) return false;
        
        return true;
    } catch {
        return false;
    }
}
```
