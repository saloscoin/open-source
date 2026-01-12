#!/usr/bin/env python3
"""
SALOCOIN Full Node
Complete node with wallet, mining, and transaction support.

Usage:
    python run_node.py                    # Run node server
    python run_node.py --mine             # Run node + solo mining
    python run_node.py --public           # Accept external connections

This script:
  - Syncs blockchain from official seed nodes
  - Serves the blockchain to other nodes/wallets
  - Supports wallet operations (balance, send, receive)
  - Solo mining with automatic block submission
  - Transaction broadcasting and mempool management
"""

import sys
import os
import json
import time
import threading
import socket
import argparse
import requests
import hashlib
import struct
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from core.blockchain import Blockchain, Block
from core.transaction import Transaction
from core.wallet import Wallet

# Version
NODE_VERSION = "1.3.0"

# Unique node ID (generated once)
NODE_ID = None

# Data directory
DATA_DIR = None
blockchain = None
wallet = None
lock = threading.Lock()
peers = []  # Connected peer nodes

# Mining state
mining_active = False
mining_threads = []
mining_hashrate = 0
mining_hashes = 0
blocks_found = 0

# Backup directory
BACKUP_DIR = None


def get_data_dir():
    """Get or create data directory."""
    global BACKUP_DIR
    if os.name == 'nt':  # Windows
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        data_dir = os.path.join(base, 'SALOCOIN', 'node')
    else:  # Linux/Mac
        data_dir = os.path.expanduser('~/.salocoin/node')
    
    os.makedirs(data_dir, exist_ok=True)
    
    # Create backup directory
    BACKUP_DIR = os.path.join(data_dir, 'backups')
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    return data_dir


def backup_block(block):
    """Automatically backup a mined block."""
    global BACKUP_DIR
    if not BACKUP_DIR:
        return False
    try:
        # Save individual block file
        block_file = os.path.join(BACKUP_DIR, f'block_{block.height:08d}.json')
        with open(block_file, 'w') as f:
            json.dump(block.to_dict(), f, indent=2)
        
        # Update latest blocks summary
        summary_file = os.path.join(BACKUP_DIR, 'latest_blocks.json')
        try:
            with open(summary_file, 'r') as f:
                latest_blocks = json.load(f)
        except:
            latest_blocks = []
        
        # Keep last 100 blocks in summary
        latest_blocks.append({
            'height': block.height,
            'hash': block.hash,
            'timestamp': block.timestamp,
            'tx_count': len(block.transactions),
            'miner': block.transactions[0].outputs[0]['address'] if block.transactions else 'unknown'
        })
        latest_blocks = latest_blocks[-100:]
        
        with open(summary_file, 'w') as f:
            json.dump(latest_blocks, f, indent=2)
        
        print(f"📦 Block {block.height} backed up")
        return True
    except Exception as e:
        print(f"⚠️ Block backup failed: {e}")
        return False


class NodeHandler(BaseHTTPRequestHandler):
    """Handle node API requests."""
    
    def log_message(self, format, *args):
        # Suppress normal logging, only show important messages
        pass
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        global blockchain
        
        path = self.path.split('?')[0]  # Remove query params
        
        if path == '/status':
            with lock:
                self._send_json({
                    'status': 'online',
                    'version': NODE_VERSION,
                    'height': blockchain.get_height(),
                    'genesis': blockchain.chain[0].hash,
                    'best_block': blockchain.get_latest_block().hash,
                    'difficulty': blockchain.current_difficulty,
                    'mempool_size': blockchain.mempool.size(),
                    'peers': len(peers),
                    'network': 'mainnet',
                })
        
        elif path == '/height':
            self._send_json({'height': blockchain.get_height()})
        
        elif path == '/blocks':
            with lock:
                blocks = [b.to_dict() for b in blockchain.chain]
            self._send_json({'blocks': blocks})
        
        elif path.startswith('/block/'):
            try:
                height = int(path.split('/')[-1])
                with lock:
                    block = blockchain.get_block_by_height(height)
                if block:
                    self._send_json(block.to_dict())
                else:
                    self._send_json({'error': 'Block not found'}, 404)
            except:
                self._send_json({'error': 'Invalid height'}, 400)
        
        elif path == '/genesis':
            self._send_json(blockchain.chain[0].to_dict())
        
        elif path == '/difficulty':
            self._send_json({
                'difficulty': blockchain.current_difficulty,
                'height': blockchain.get_height()
            })
        
        elif path == '/mempool':
            with lock:
                txs = [tx.to_dict() for tx in blockchain.mempool.transactions.values()]
            self._send_json({
                'size': len(txs),
                'transactions': txs
            })
        
        elif path == '/peers':
            self._send_json({'peers': peers, 'count': len(peers)})
        
        elif path == '/info':
            self._send_json({
                'name': config.COIN_NAME,
                'ticker': config.COIN_TICKER,
                'version': NODE_VERSION,
                'protocol': config.PROTOCOL_VERSION,
                'height': blockchain.get_height(),
                'genesis': config.GENESIS_HASH,
                'block_time': config.BLOCK_TIME_TARGET,
                'max_supply': config.MAX_SUPPLY / config.COIN_UNIT,
            })
        
        elif path == '/wallet':
            # Wallet info
            if wallet:
                address = get_wallet_address()
                balance = get_balance(address)
                pending = get_pending_balance(address)
                self._send_json({
                    'address': address,
                    'balance': balance / config.COIN_UNIT,
                    'balance_satoshi': balance,
                    'pending': pending / config.COIN_UNIT,
                    'pending_satoshi': pending,
                })
            else:
                self._send_json({'error': 'No wallet loaded'}, 400)
        
        elif path.startswith('/balance/'):
            # Get balance for any address
            address = path.split('/')[-1]
            balance = get_balance(address)
            pending = get_pending_balance(address)
            self._send_json({
                'address': address,
                'balance': balance / config.COIN_UNIT,
                'balance_satoshi': balance,
                'pending': pending / config.COIN_UNIT,
                'pending_satoshi': pending,
            })
        
        elif path == '/mining':
            # Mining status
            self._send_json({
                'active': mining_active,
                'hashrate': mining_hashrate,
                'blocks_found': blocks_found,
                'height': blockchain.get_height() + 1 if mining_active else 0,
            })
        
        else:
            self._send_json({'error': 'Unknown endpoint', 'endpoints': [
                '/status', '/height', '/blocks', '/block/<n>', '/genesis',
                '/difficulty', '/mempool', '/peers', '/info',
                '/wallet', '/balance/<address>', '/mining'
            ]}, 404)
    
    def do_POST(self):
        """Handle POST requests."""
        global blockchain
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body.decode()) if body else {}
        except:
            self._send_json({'error': 'Invalid JSON'}, 400)
            return
        
        path = self.path.split('?')[0]
        
        if path == '/submit_block':
            with lock:
                try:
                    block = Block.from_dict(data)
                    
                    expected_height = blockchain.get_height() + 1
                    if block.height != expected_height:
                        self._send_json({
                            'error': 'Invalid block height',
                            'expected': expected_height,
                            'received': block.height
                        }, 400)
                        return
                    
                    if block.previous_hash != blockchain.get_latest_block().hash:
                        self._send_json({'error': 'Invalid previous hash'}, 400)
                        return
                    
                    if blockchain.add_block(block):
                        blockchain.save()
                        backup_block(block)  # Auto backup
                        print(f"✓ Block {block.height}: {block.hash[:32]}...")
                        self._send_json({
                            'success': True,
                            'height': blockchain.get_height(),
                            'hash': block.hash
                        })
                        
                        # Relay to peers
                        relay_block_to_peers(block)
                    else:
                        self._send_json({'error': 'Block rejected'}, 400)
                
                except Exception as e:
                    self._send_json({'error': str(e)}, 500)
        
        elif path == '/sync':
            client_height = data.get('height', 0)
            
            with lock:
                blocks_to_send = []
                for i in range(client_height + 1, len(blockchain.chain)):
                    blocks_to_send.append(blockchain.chain[i].to_dict())
            
            self._send_json({
                'height': blockchain.get_height(),
                'blocks': blocks_to_send
            })
        
        elif path == '/submit_tx':
            with lock:
                try:
                    tx_data = data.get('transaction', data)
                    tx = Transaction.from_dict(tx_data)
                    
                    if tx.txid in blockchain.mempool.transactions:
                        self._send_json({
                            'success': True,
                            'txid': tx.txid,
                            'message': 'Already in mempool'
                        })
                        return
                    
                    if blockchain.mempool.add_transaction(tx):
                        blockchain.save()
                        print(f"📥 TX: {tx.txid[:24]}...")
                        self._send_json({
                            'success': True,
                            'txid': tx.txid
                        })
                        
                        # Relay to peers
                        relay_tx_to_peers(tx)
                    else:
                        self._send_json({'error': 'Transaction rejected'}, 400)
                
                except Exception as e:
                    self._send_json({'error': str(e)}, 500)
        
        elif path == '/add_peer':
            peer_url = data.get('url')
            if peer_url and peer_url not in peers:
                peers.append(peer_url)
                print(f"👥 New peer: {peer_url}")
            self._send_json({'success': True, 'peers': len(peers)})
        
        elif path == '/send':
            # Send transaction from node wallet
            if not wallet:
                self._send_json({'error': 'No wallet loaded'}, 400)
                return
            
            to_address = data.get('to') or data.get('address')
            amount = data.get('amount', 0)
            
            if not to_address or not to_address.startswith('S'):
                self._send_json({'error': 'Invalid recipient address'}, 400)
                return
            
            if amount <= 0:
                self._send_json({'error': 'Invalid amount'}, 400)
                return
            
            # Convert to satoshis
            amount_sat = int(amount * config.COIN_UNIT)
            
            result = create_and_send_transaction(to_address, amount_sat)
            if result.get('success'):
                self._send_json(result)
            else:
                self._send_json(result, 400)
        
        elif path == '/mine/start':
            # Start mining
            threads = data.get('threads', 1)
            result = start_mining(threads)
            self._send_json(result)
        
        elif path == '/mine/stop':
            # Stop mining
            result = stop_mining()
            self._send_json(result)
        
        else:
            self._send_json({'error': 'Unknown endpoint'}, 404)


# =============================================================================
# RELAY FUNCTIONS
# =============================================================================

def relay_block_to_peers(block):
    """Relay new block to connected peers."""
    block_data = block.to_dict()
    for peer in peers[:]:
        try:
            requests.post(f"{peer}/submit_block", json=block_data, timeout=5)
        except:
            pass


def relay_tx_to_peers(tx):
    """Relay transaction to connected peers."""
    tx_data = tx.to_dict()
    for peer in peers[:]:
        try:
            requests.post(f"{peer}/submit_tx", json=tx_data, timeout=5)
        except:
            pass


# =============================================================================
# WALLET FUNCTIONS
# =============================================================================

def load_or_create_wallet():
    """Load existing wallet or create new one."""
    global wallet, DATA_DIR
    
    wallet_file = os.path.join(DATA_DIR, 'wallet.json')
    
    if os.path.exists(wallet_file):
        try:
            wallet = Wallet(filepath=wallet_file)
            wallet.load()
            print(f"💳 Wallet loaded: {wallet.addresses[0].address if wallet.addresses else 'No address'}")
            return wallet
        except Exception as e:
            print(f"⚠️  Failed to load wallet: {e}")
    
    # Create new wallet
    wallet = Wallet(filepath=wallet_file, name='Node Wallet')
    wallet.create_hd_wallet()
    wallet.save()
    print(f"💳 New wallet created: {wallet.addresses[0].address if wallet.addresses else 'No address'}")
    return wallet


def get_wallet_address():
    """Get the primary wallet address."""
    global wallet
    if wallet and wallet.addresses:
        return wallet.addresses[0].address
    return None


def get_wallet_private_key():
    """Get the primary wallet private key."""
    global wallet
    if wallet and wallet.addresses:
        return wallet.addresses[0].private_key
    return None
    return wallet


def get_balance(address):
    """Get confirmed balance for address."""
    global blockchain
    
    balance = 0
    with lock:
        utxos = blockchain.utxo_set.get(address, [])
        for utxo in utxos:
            balance += utxo.get('amount', 0)
    return balance


def get_pending_balance(address):
    """Get pending (unconfirmed) balance for address."""
    global blockchain
    
    pending = 0
    with lock:
        for tx in blockchain.mempool.transactions.values():
            # Incoming
            for out in tx.outputs:
                if out.get('address') == address:
                    pending += out.get('amount', 0)
            # Outgoing (negative)
            for inp in tx.inputs:
                # Would need to look up the UTXO to get the address
                pass
    return pending


def create_and_send_transaction(to_address, amount_sat):
    """Create and broadcast a transaction."""
    global wallet, blockchain
    
    if not wallet:
        return {'success': False, 'error': 'No wallet'}
    
    from_address = get_wallet_address()
    balance = get_balance(from_address)
    
    fee = 1000  # 0.00001 SALO fee
    total_needed = amount_sat + fee
    
    if balance < total_needed:
        return {
            'success': False,
            'error': f'Insufficient balance. Have: {balance / config.COIN_UNIT:.8f}, Need: {total_needed / config.COIN_UNIT:.8f}'
        }
    
    # Build transaction
    with lock:
        utxos = blockchain.utxo_set.get(from_address, [])
        
        inputs = []
        input_amount = 0
        
        for utxo in utxos:
            inputs.append({
                'txid': utxo['txid'],
                'vout': utxo['vout'],
                'address': from_address,
                'amount': utxo['amount'],
            })
            input_amount += utxo['amount']
            if input_amount >= total_needed:
                break
        
        if input_amount < total_needed:
            return {'success': False, 'error': 'Could not gather enough inputs'}
        
        outputs = [{'address': to_address, 'amount': amount_sat}]
        
        # Change
        change = input_amount - amount_sat - fee
        if change > 0:
            outputs.append({'address': from_address, 'amount': change})
        
        # Create transaction
        tx = Transaction(inputs=inputs, outputs=outputs)
        
        # Sign using wallet's primary address
        if wallet and wallet.addresses:
            primary_addr = wallet.addresses[0]
            for i, inp in enumerate(tx.inputs):
                sig = primary_addr.sign(tx.txid.encode())
                tx.inputs[i]['signature'] = sig.hex() if isinstance(sig, bytes) else sig
                tx.inputs[i]['pubkey'] = primary_addr.public_key.hex() if isinstance(primary_addr.public_key, bytes) else primary_addr.public_key
        
        # Add to mempool
        if blockchain.mempool.add_transaction(tx):
            blockchain.save()
            print(f"📤 TX sent: {tx.txid[:24]}... ({amount_sat / config.COIN_UNIT:.8f} SALO)")
            
            # Broadcast to peers and seed nodes
            broadcast_transaction(tx)
            
            return {
                'success': True,
                'txid': tx.txid,
                'amount': amount_sat / config.COIN_UNIT,
                'fee': fee / config.COIN_UNIT,
                'to': to_address,
            }
        else:
            return {'success': False, 'error': 'Transaction rejected by mempool'}


def broadcast_transaction(tx):
    """Broadcast transaction to network."""
    tx_data = tx.to_dict()
    
    # Send to seed nodes
    for seed in config.SEED_NODES:
        try:
            if not seed.startswith('http'):
                seed_url = f"http://{seed}"
            else:
                seed_url = seed
            requests.post(f"{seed_url}/submit_tx", json=tx_data, timeout=5)
        except:
            pass
    
    # Send to peers
    relay_tx_to_peers(tx)


# =============================================================================
# MINING FUNCTIONS
# =============================================================================

def start_mining(num_threads=1):
    """Start solo mining."""
    global mining_active, mining_threads, mining_hashes
    
    if mining_active:
        return {'success': False, 'error': 'Mining already active'}
    
    if not wallet:
        return {'success': False, 'error': 'No wallet for mining rewards'}
    
    mining_active = True
    mining_hashes = 0
    
    print(f"⛏️  Starting {num_threads} mining threads...")
    
    for i in range(num_threads):
        t = threading.Thread(target=mining_thread, args=(i, num_threads), daemon=True)
        t.start()
        mining_threads.append(t)
    
    # Start hashrate monitor
    threading.Thread(target=hashrate_monitor, daemon=True).start()
    
    return {
        'success': True,
        'message': f'Mining started with {num_threads} threads',
        'address': get_wallet_address(),
    }


def stop_mining():
    """Stop mining."""
    global mining_active, mining_threads
    
    if not mining_active:
        return {'success': False, 'error': 'Mining not active'}
    
    mining_active = False
    mining_threads = []
    
    print("⏹  Mining stopped")
    
    return {'success': True, 'message': 'Mining stopped'}


def mining_thread(thread_id, total_threads):
    """Solo mining thread."""
    global mining_active, mining_hashes, blocks_found, blockchain, wallet
    
    thread_offset = thread_id * (0xFFFFFFFF // total_threads)
    nonce = random.randint(0, 0x0FFFFFFF) + thread_offset
    
    while mining_active:
        with lock:
            height = blockchain.get_height() + 1
            prev_hash = blockchain.get_latest_block().hash
            difficulty = blockchain.current_difficulty
        
        # Build block template
        timestamp = int(time.time())
        reward = config.calculate_block_reward(height)
        miner_address = get_wallet_address()
        
        # Coinbase transaction
        coinbase_tx = {
            'txid': hashlib.sha256(f"coinbase_{height}_{timestamp}_{thread_id}".encode()).hexdigest(),
            'inputs': [{'txid': '0' * 64, 'vout': 0, 'coinbase': True}],
            'outputs': [{'address': miner_address, 'amount': reward}],
        }
        
        # Include mempool transactions
        with lock:
            mempool_txs = list(blockchain.mempool.transactions.values())[:10]
        
        all_txs = [coinbase_tx] + [tx.to_dict() for tx in mempool_txs]
        
        # Merkle root
        tx_hashes = [hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest() for tx in all_txs]
        merkle_root = tx_hashes[0] if tx_hashes else '0' * 64
        
        # Build header
        version = config.BLOCK_VERSION
        nbits = difficulty
        
        # Calculate target
        exponent = (nbits >> 24) & 0xFF
        coefficient = nbits & 0x007fffff  # 23-bit mantissa (Bitcoin format)
        if exponent <= 3:
            target = coefficient >> (8 * (3 - exponent))
        else:
            target = coefficient << (8 * (exponent - 3))
        
        # Header bytes
        header_prefix = struct.pack('<I', version)
        header_prefix += bytes.fromhex(prev_hash)[::-1][:32]
        header_prefix += bytes.fromhex(merkle_root)[::-1][:32]
        header_prefix += struct.pack('<I', timestamp)
        header_prefix += struct.pack('<I', nbits)
        
        # Mine
        local_hashes = 0
        start_prev_hash = prev_hash
        
        while mining_active and local_hashes < 50000:
            # Check for new block
            if local_hashes % 1000 == 0:
                with lock:
                    if blockchain.get_latest_block().hash != start_prev_hash:
                        break
            
            header = header_prefix + struct.pack('<I', nonce)
            hash1 = hashlib.sha256(header).digest()
            hash2 = hashlib.sha256(hash1).digest()
            hash_int = int.from_bytes(hash2, 'big')
            
            mining_hashes += 1
            local_hashes += 1
            
            if hash_int < target:
                # BLOCK FOUND!
                block_hash = hash2[::-1].hex()
                blocks_found += 1
                
                print(f"\n🎉🎉🎉 BLOCK FOUND! 🎉🎉🎉")
                print(f"   Height: {height}")
                print(f"   Hash: {block_hash[:48]}...")
                print(f"   Reward: {reward / config.COIN_UNIT} SALO\n")
                
                # Submit block
                submit_mined_block(height, prev_hash, merkle_root, timestamp, nbits, nonce, block_hash, all_txs)
                break
            
            nonce = (nonce + 1) & 0xFFFFFFFF
        
        time.sleep(0.001)  # Yield CPU


def submit_mined_block(height, prev_hash, merkle_root, timestamp, nbits, nonce, block_hash, transactions):
    """Submit mined block to network."""
    global blockchain
    
    block_data = {
        'version': config.BLOCK_VERSION,
        'height': height,
        'timestamp': timestamp,
        'previous_hash': prev_hash,
        'merkle_root': merkle_root,
        'difficulty': nbits,
        'nonce': nonce,
        'hash': block_hash,
        'transactions': transactions,
    }
    
    # Add to local blockchain
    with lock:
        try:
            block = Block.from_dict(block_data)
            if blockchain.add_block(block):
                blockchain.save()
                backup_block(block)  # Auto backup
                print(f"✅ Block {height} added to local chain")
        except Exception as e:
            print(f"⚠️  Failed to add block locally: {e}")
    
    # Submit to seed nodes
    for seed in config.SEED_NODES:
        try:
            if not seed.startswith('http'):
                seed_url = f"http://{seed}"
            else:
                seed_url = seed
            
            resp = requests.post(f"{seed_url}/submit_block", json=block_data, timeout=30)
            if resp.status_code == 200:
                print(f"✅ Block accepted by {seed}")
            else:
                print(f"⚠️  Block rejected by {seed}: {resp.text[:100]}")
                # Resync from seed to get correct chain
                print(f"🔄 Resyncing from network...")
                with lock:
                    try:
                        # Remove our invalid block
                        if len(blockchain.chain) > 1 and blockchain.chain[-1].height == height:
                            blockchain.chain.pop()
                        full_sync_from_seeds()
                        print(f"✓ Resynced to height {blockchain.get_height()}")
                    except Exception as sync_err:
                        print(f"⚠️  Resync failed: {sync_err}")
        except Exception as e:
            print(f"⚠️  Failed to submit to {seed}: {e}")


def hashrate_monitor():
    """Monitor and display hashrate."""
    global mining_active, mining_hashes, mining_hashrate
    
    last_hashes = 0
    last_time = time.time()
    
    while mining_active:
        time.sleep(5)
        
        now = time.time()
        elapsed = now - last_time
        hashes_done = mining_hashes - last_hashes
        
        if elapsed > 0:
            mining_hashrate = hashes_done / elapsed
        
        if mining_hashrate >= 1e6:
            hr_str = f"{mining_hashrate / 1e6:.2f} MH/s"
        elif mining_hashrate >= 1e3:
            hr_str = f"{mining_hashrate / 1e3:.2f} KH/s"
        else:
            hr_str = f"{mining_hashrate:.2f} H/s"
        
        print(f"⛏️  Mining: {hr_str} | Block #{blockchain.get_height() + 1} | Found: {blocks_found}")
        
        last_hashes = mining_hashes
        last_time = now


def full_sync_from_seeds():
    """Fully sync blockchain from seed nodes before starting."""
    global blockchain
    
    print("🔄 Downloading blockchain from seed nodes...")
    print("   This may take a while on first run...\n")
    
    synced = False
    
    for seed in config.SEED_NODES:
        try:
            # Try http:// format
            if not seed.startswith('http'):
                seed_url = f"http://{seed}"
            else:
                seed_url = seed
            
            print(f"   🔗 Connecting to {seed}...")
            
            # Get status
            resp = requests.get(f"{seed_url}/status", timeout=10)
            if resp.status_code != 200:
                print(f"   ⚠️  {seed}: Not responding")
                continue
            
            seed_data = resp.json()
            seed_height = seed_data.get('height', 0)
            local_height = blockchain.get_height()
            
            print(f"   📊 Network height: {seed_height}, Local: {local_height}")
            
            if seed_height <= local_height:
                print(f"   ✅ Already up to date!")
                synced = True
                if seed_url not in peers:
                    peers.append(seed_url)
                break
            
            blocks_needed = seed_height - local_height
            print(f"   📥 Downloading {blocks_needed} blocks...\n")
            
            # Sync in batches for large syncs
            batch_size = 100
            while blockchain.get_height() < seed_height:
                current = blockchain.get_height()
                
                try:
                    sync_resp = requests.post(
                        f"{seed_url}/sync",
                        json={'height': current},
                        timeout=120
                    )
                    
                    if sync_resp.status_code != 200:
                        print(f"   ⚠️  Sync request failed")
                        break
                    
                    blocks_data = sync_resp.json().get('blocks', [])
                    
                    if not blocks_data:
                        break
                    
                    with lock:
                        added = 0
                        for block_data in blocks_data:
                            try:
                                block = Block.from_dict(block_data)
                                if blockchain.add_block(block):
                                    backup_block(block)  # Auto backup
                                    added += 1
                            except Exception as e:
                                pass
                        
                        if added > 0:
                            blockchain.save()
                    
                    new_height = blockchain.get_height()
                    progress = (new_height / seed_height) * 100 if seed_height > 0 else 100
                    print(f"   📦 Block {new_height}/{seed_height} ({progress:.1f}%)")
                    
                    if new_height >= seed_height:
                        break
                    
                    if added == 0:
                        break
                        
                except requests.Timeout:
                    print(f"   ⚠️  Timeout, retrying...")
                    continue
                except Exception as e:
                    print(f"   ⚠️  Error: {e}")
                    break
            
            if blockchain.get_height() >= seed_height:
                print(f"\n   ✅ Sync complete! Height: {blockchain.get_height()}")
                synced = True
                if seed_url not in peers:
                    peers.append(seed_url)
                break
            
        except Exception as e:
            print(f"   ⚠️ {seed}: {e}")
            continue
    
    if not synced:
        print("\n   ⚠️  Could not sync from any seed node")
        print("   Starting with local blockchain...")
    
    return synced


def sync_from_seeds():
    """Quick sync check from seed nodes."""
    global blockchain
    
    for seed in config.SEED_NODES:
        try:
            if not seed.startswith('http'):
                seed_url = f"http://{seed}"
            else:
                seed_url = seed
            
            resp = requests.get(f"{seed_url}/status", timeout=10)
            if resp.status_code != 200:
                continue
            
            seed_height = resp.json().get('height', 0)
            local_height = blockchain.get_height()
            
            if seed_height <= local_height:
                continue
            
            # Get new blocks
            sync_resp = requests.post(f"{seed_url}/sync", json={'height': local_height}, timeout=60)
            if sync_resp.status_code == 200:
                blocks_data = sync_resp.json().get('blocks', [])
                
                with lock:
                    for block_data in blocks_data:
                        try:
                            block = Block.from_dict(block_data)
                            if blockchain.add_block(block):
                                backup_block(block)  # Auto backup
                        except:
                            pass
                    blockchain.save()
                
                print(f"📦 Synced to block {blockchain.get_height()}")
            
            break
            
        except:
            continue


def get_node_id():
    """Get or generate unique node ID."""
    global NODE_ID, DATA_DIR
    if NODE_ID:
        return NODE_ID
    
    # Try to load existing node ID
    node_id_file = os.path.join(DATA_DIR or get_data_dir(), 'node_id.txt')
    try:
        with open(node_id_file, 'r') as f:
            NODE_ID = f.read().strip()
            return NODE_ID
    except:
        pass
    
    # Generate new node ID (random 32-byte hex)
    NODE_ID = hashlib.sha256(os.urandom(32)).hexdigest()
    
    # Save it
    try:
        os.makedirs(os.path.dirname(node_id_file), exist_ok=True)
        with open(node_id_file, 'w') as f:
            f.write(NODE_ID)
    except:
        pass
    
    return NODE_ID


def register_with_seed(port=7339, public=False):
    """Register this node with the main seed server."""
    global blockchain
    
    if not public:
        # Don't register if not accepting external connections
        return False
    
    try:
        # Get public IP
        try:
            public_ip = requests.get('https://api.ipify.org', timeout=5).text.strip()
        except:
            public_ip = socket.gethostbyname(socket.gethostname())
        
        node_id = get_node_id()
        
        # Register with main seed
        seed_url = config.SEED_NODES[0].rstrip('/')
        data = {
            'node_id': node_id,
            'host': public_ip,
            'port': port,
            'url': f"http://{public_ip}:{port}",
            'height': blockchain.get_height() if blockchain else 0,
            'version': NODE_VERSION,
        }
        
        resp = requests.post(f"{seed_url}/register_peer", json=data, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            print(f"🌐 Registered with network ({result.get('total_peers', 0)} total peers)")
            return True
        else:
            print(f"⚠️ Failed to register with seed: {resp.status_code}")
    except Exception as e:
        print(f"⚠️ Could not register with seed: {e}")
    
    return False


def send_heartbeat(port=7339):
    """Send heartbeat to seed to stay in peer list."""
    global blockchain
    
    try:
        node_id = get_node_id()
        seed_url = config.SEED_NODES[0].rstrip('/')
        data = {
            'node_id': node_id,
            'height': blockchain.get_height() if blockchain else 0,
        }
        
        requests.post(f"{seed_url}/heartbeat", json=data, timeout=10)
    except:
        pass


def periodic_heartbeat(port=7339):
    """Send periodic heartbeats to stay in peer list."""
    while True:
        time.sleep(300)  # Every 5 minutes
        send_heartbeat(port)


def periodic_sync():
    """Periodically sync with network."""
    while True:
        time.sleep(60)  # Sync every minute
        try:
            sync_from_seeds()
        except:
            pass


def main():
    global DATA_DIR, blockchain
    
    parser = argparse.ArgumentParser(
        description='SALOCOIN Full Node - Wallet, Mining, and Network',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_node.py                     # Run node server
    python run_node.py --mine              # Run node with solo mining
    python run_node.py --mine --threads 4  # Mining with 4 threads
    python run_node.py --public            # Accept external connections
    python run_node.py --datadir ./mydata  # Custom data directory

After starting, your node will:
  1. Sync blockchain from official seeds
  2. Load/create wallet for mining rewards
  3. Serve API endpoints for wallets/miners
  4. Accept and relay new blocks/transactions
  5. Help decentralize the SALOCOIN network!
        """
    )
    
    parser.add_argument('--port', type=int, default=7339, help='Port to listen on (default: 7339)')
    parser.add_argument('--public', action='store_true', help='Accept external connections (bind to 0.0.0.0)')
    parser.add_argument('--datadir', type=str, help='Data directory for blockchain')
    parser.add_argument('--seed', type=str, action='append', help='Additional seed node URL')
    parser.add_argument('--mine', action='store_true', help='Enable solo mining')
    parser.add_argument('--threads', type=int, default=1, help='Mining threads (default: 1)')
    
    args = parser.parse_args()
    
    # Data directory
    DATA_DIR = args.datadir or get_data_dir()
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Initialize blockchain
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║              SALOCOIN FULL NODE v{NODE_VERSION}                         ║
║          Wallet • Mining • Transactions • Network                ║
╠══════════════════════════════════════════════════════════════════╣
║  Port:        {args.port:<52} ║
║  Data Dir:    {DATA_DIR[:50]:<52} ║
║  External:    {'Yes - accepting connections' if args.public else 'No - localhost only':<52} ║
║  Mining:      {'Yes - ' + str(args.threads) + ' threads' if args.mine else 'No':<52} ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    blockchain = Blockchain(data_dir=DATA_DIR)
    blockchain.load()
    
    print(f"📦 Local blockchain: {blockchain.get_height()} blocks")
    
    # Load or create wallet
    load_or_create_wallet()
    
    if wallet:
        balance = get_balance(get_wallet_address())
        print(f"💰 Balance: {balance / config.COIN_UNIT:.8f} SALO\n")
    
    # Add custom seeds
    if args.seed:
        for seed in args.seed:
            if seed not in config.SEED_NODES:
                config.SEED_NODES.append(seed)
    
    # FULL SYNC from network first
    print("=" * 60)
    full_sync_from_seeds()
    print("=" * 60)
    
    # Update balance after sync
    if wallet:
        balance = get_balance(get_wallet_address())
        print(f"💰 Updated balance: {balance / config.COIN_UNIT:.8f} SALO")
    
    # Start periodic sync thread
    threading.Thread(target=periodic_sync, daemon=True).start()
    
    # Register with network if public
    if args.public:
        register_with_seed(args.port, args.public)
        threading.Thread(target=periodic_heartbeat, args=(args.port,), daemon=True).start()
    
    # Start mining if enabled
    if args.mine:
        start_mining(args.threads)
    
    # Bind address
    bind_addr = '0.0.0.0' if args.public else '127.0.0.1'
    
    print(f"""
✅ NODE READY - STARTING API SERVER

📡 API Endpoints:
   GET  /status          - Node status
   GET  /height          - Block height  
   GET  /blocks          - All blocks
   GET  /block/<n>       - Block at height n
   GET  /mempool         - Pending transactions
   GET  /wallet          - Wallet address & balance
   GET  /balance/<addr>  - Balance for any address
   GET  /mining          - Mining status
   
   POST /submit_block    - Submit mined block
   POST /submit_tx       - Submit transaction
   POST /send            - Send SALO (to, amount)
   POST /mine/start      - Start mining
   POST /mine/stop       - Stop mining
   POST /sync            - Sync blocks

🌐 Your node: http://{bind_addr}:{args.port}
   {'🌍 External access enabled!' if args.public else '🔒 Localhost only (use --public for external)'}
{'⛏️  Solo mining active!' if args.mine else ''}
Press Ctrl+C to stop...
""")
    
    # Start server
    server = HTTPServer((bind_addr, args.port), NodeHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹ Shutting down node...")
        if mining_active:
            stop_mining()
        blockchain.save()
        if wallet:
            wallet.save()
        server.shutdown()
        print("✅ Node stopped. Blockchain and wallet saved.")


if __name__ == '__main__':
    main()
