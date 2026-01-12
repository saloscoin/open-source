#!/usr/bin/env python3
"""
SALOCOIN Exchange-Ready Node

A full node implementation designed for exchange integration:
- Full P2P networking (port 9339)
- Bitcoin-compatible JSON-RPC (port 7340)
- HTTP REST API (port 7339)
- Health monitoring
- Multiple confirmations tracking
- Transaction broadcast/rebroadcast

Exchange Requirements Checklist:
✓ getblock, getblockhash, getblockheader
✓ getrawtransaction, sendrawtransaction
✓ getbalance, listunspent
✓ validateaddress
✓ getmempoolinfo, getrawmempool
✓ getnetworkinfo, getpeerinfo
✓ Multi-confirmation tracking
✓ Transaction rebroadcast
✓ Health endpoints
"""

import os
import sys
import json
import time
import socket
import signal
import hashlib
import threading
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Any, Optional
from datetime import datetime
from decimal import Decimal

# Import SALOCOIN modules
import config
from core.blockchain import Blockchain, Block
from core.transaction import Transaction, TransactionPool
from core.wallet import Wallet
from network.node import Node
from network.discovery import PeerDiscovery
from rpc.server import RPCServer
from rpc.methods import RPCMethods

# ============================================================================
# CONFIGURATION
# ============================================================================

VERSION = "1.0.0"
NODE_NAME = "SALOCOIN Exchange Node"

# Default ports
DEFAULT_P2P_PORT = 9339      # P2P networking
DEFAULT_RPC_PORT = 7340      # JSON-RPC (exchange integration)
DEFAULT_API_PORT = 7339      # HTTP REST API

# Exchange-specific settings
MIN_CONFIRMATIONS = 6        # Minimum confirmations for deposits
WITHDRAW_CONFIRMATIONS = 2   # Confirmations before withdrawal is considered safe
REBROADCAST_INTERVAL = 300   # Rebroadcast stuck transactions every 5 minutes
HEALTH_CHECK_INTERVAL = 30   # Health check every 30 seconds

# ============================================================================
# GLOBALS
# ============================================================================

blockchain: Optional[Blockchain] = None
mempool: Optional[TransactionPool] = None
p2p_node: Optional[Node] = None
rpc_server: Optional[RPCServer] = None
wallet: Optional[Wallet] = None

node_start_time = 0
is_synced = False
lock = threading.RLock()

# Tracking for exchange
pending_deposits: Dict[str, Dict] = {}  # txid -> {address, amount, confirmations}
pending_withdrawals: Dict[str, Dict] = {}  # txid -> {address, amount, timestamp}

# ============================================================================
# HTTP REST API HANDLER
# ============================================================================

class ExchangeAPIHandler(BaseHTTPRequestHandler):
    """REST API for exchange integration and monitoring."""
    
    def log_message(self, format, *args):
        # Only log errors
        if '400' in format or '500' in format:
            print(f"API: {format % args}")
    
    def _send_json(self, data: Dict, status: int = 200):
        response = json.dumps(data, default=str, indent=2)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(response.encode())
    
    def _send_error(self, message: str, status: int = 400):
        self._send_json({'error': message}, status)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
    
    def do_GET(self):
        path = self.path.split('?')[0]
        
        try:
            # ================================================================
            # Health & Status Endpoints
            # ================================================================
            
            if path == '/health':
                self._handle_health()
            
            elif path == '/status':
                self._handle_status()
            
            elif path == '/readiness':
                self._handle_readiness()
            
            elif path == '/sync':
                self._handle_sync_status()
            
            # ================================================================
            # Blockchain Endpoints
            # ================================================================
            
            elif path == '/height':
                self._send_json({'height': blockchain.get_height()})
            
            elif path == '/difficulty':
                self._send_json({
                    'difficulty': blockchain.current_difficulty,
                    'height': blockchain.get_height(),
                    'target': format(int(blockchain.current_difficulty * 2**224), '064x')
                })
            
            elif path.startswith('/block/'):
                self._handle_get_block(path)
            
            elif path == '/blocks':
                self._handle_get_blocks()
            
            elif path == '/genesis':
                self._send_json(blockchain.chain[0].to_dict())
            
            elif path == '/tip':
                tip = blockchain.get_latest_block()
                self._send_json({
                    'height': tip.height,
                    'hash': tip.hash,
                    'timestamp': tip.timestamp,
                    'difficulty': tip.bits
                })
            
            # ================================================================
            # Transaction Endpoints
            # ================================================================
            
            elif path.startswith('/tx/'):
                self._handle_get_transaction(path)
            
            elif path == '/mempool':
                self._handle_mempool()
            
            elif path == '/mempool/info':
                self._handle_mempool_info()
            
            # ================================================================
            # Address & Balance Endpoints
            # ================================================================
            
            elif path.startswith('/address/'):
                self._handle_address(path)
            
            elif path.startswith('/balance/'):
                self._handle_balance(path)
            
            elif path.startswith('/utxos/'):
                self._handle_utxos(path)
            
            elif path.startswith('/validate/'):
                self._handle_validate_address(path)
            
            # ================================================================
            # Network Endpoints
            # ================================================================
            
            elif path == '/peers':
                self._handle_peers()
            
            elif path == '/network':
                self._handle_network_info()
            
            # ================================================================
            # Exchange-Specific Endpoints
            # ================================================================
            
            elif path.startswith('/confirmations/'):
                self._handle_confirmations(path)
            
            elif path == '/pending':
                self._handle_pending()
            
            elif path == '/info':
                self._handle_info()
            
            else:
                self._send_error(f"Unknown endpoint: {path}", 404)
                
        except Exception as e:
            print(f"API Error: {e}")
            self._send_error(str(e), 500)
    
    def do_POST(self):
        path = self.path.split('?')[0]
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode() if content_length else '{}'
            data = json.loads(body) if body else {}
            
            if path == '/tx/send':
                self._handle_send_transaction(data)
            
            elif path == '/tx/broadcast':
                self._handle_broadcast_transaction(data)
            
            elif path == '/tx/decode':
                self._handle_decode_transaction(data)
            
            else:
                self._send_error(f"Unknown endpoint: {path}", 404)
                
        except json.JSONDecodeError:
            self._send_error("Invalid JSON", 400)
        except Exception as e:
            print(f"API Error: {e}")
            self._send_error(str(e), 500)
    
    # ========================================================================
    # Health & Status Handlers
    # ========================================================================
    
    def _handle_health(self):
        """Health check endpoint for load balancers."""
        uptime = time.time() - node_start_time
        
        # Check various health indicators
        checks = {
            'blockchain': blockchain is not None and blockchain.get_height() > 0,
            'mempool': mempool is not None,
            'p2p': p2p_node is not None,
            'rpc': rpc_server is not None,
        }
        
        healthy = all(checks.values())
        
        self._send_json({
            'status': 'healthy' if healthy else 'unhealthy',
            'uptime': int(uptime),
            'checks': checks,
            'timestamp': int(time.time())
        }, 200 if healthy else 503)
    
    def _handle_status(self):
        """Detailed node status."""
        uptime = time.time() - node_start_time
        
        with lock:
            self._send_json({
                'node': {
                    'version': VERSION,
                    'name': NODE_NAME,
                    'uptime': int(uptime),
                    'synced': is_synced,
                },
                'blockchain': {
                    'height': blockchain.get_height(),
                    'best_block': blockchain.get_latest_block().hash,
                    'difficulty': blockchain.current_difficulty,
                    'genesis': blockchain.chain[0].hash,
                },
                'mempool': {
                    'size': blockchain.mempool.size(),
                    'bytes': sum(len(tx.serialize()) for tx in blockchain.mempool.transactions.values()),
                },
                'network': {
                    'peers': p2p_node.peer_manager.get_connection_count() if p2p_node else {'total': 0},
                    'protocol': config.PROTOCOL_VERSION,
                },
                'coin': {
                    'name': config.COIN_NAME,
                    'ticker': config.COIN_TICKER,
                    'block_time': config.BLOCK_TIME_TARGET,
                    'max_supply': config.MAX_SUPPLY / config.COIN_UNIT,
                },
                'timestamp': int(time.time())
            })
    
    def _handle_readiness(self):
        """Readiness check - is node ready to serve requests?"""
        ready = (
            blockchain is not None and
            blockchain.get_height() > 0 and
            is_synced
        )
        
        self._send_json({
            'ready': ready,
            'synced': is_synced,
            'height': blockchain.get_height() if blockchain else 0,
        }, 200 if ready else 503)
    
    def _handle_sync_status(self):
        """Sync status for monitoring."""
        tip = blockchain.get_latest_block()
        age = int(time.time()) - tip.timestamp
        
        self._send_json({
            'synced': is_synced,
            'height': blockchain.get_height(),
            'tip_hash': tip.hash,
            'tip_time': tip.timestamp,
            'tip_age_seconds': age,
            'peers': p2p_node.peer_manager.get_connection_count()['total'] if p2p_node else 0,
        })
    
    # ========================================================================
    # Blockchain Handlers
    # ========================================================================
    
    def _handle_get_block(self, path: str):
        """Get block by height or hash."""
        identifier = path.split('/')[-1]
        
        with lock:
            # Try as height first
            try:
                height = int(identifier)
                block = blockchain.get_block_by_height(height)
            except ValueError:
                # Try as hash
                block = blockchain.get_block_by_hash(identifier)
            
            if block:
                data = block.to_dict()
                data['confirmations'] = blockchain.get_height() - block.height + 1
                self._send_json(data)
            else:
                self._send_error("Block not found", 404)
    
    def _handle_get_blocks(self):
        """Get recent blocks."""
        query = self.path.split('?')[-1] if '?' in self.path else ''
        params = dict(p.split('=') for p in query.split('&') if '=' in p)
        
        limit = min(int(params.get('limit', 10)), 100)
        offset = int(params.get('offset', 0))
        
        with lock:
            height = blockchain.get_height()
            blocks = []
            for h in range(max(0, height - offset - limit + 1), height - offset + 1):
                block = blockchain.get_block_by_height(h)
                if block:
                    blocks.append({
                        'height': block.height,
                        'hash': block.hash,
                        'timestamp': block.timestamp,
                        'tx_count': len(block.transactions),
                        'difficulty': block.bits,
                        'confirmations': height - block.height + 1
                    })
            
            blocks.reverse()
        
        self._send_json({
            'blocks': blocks,
            'total': height + 1,
            'limit': limit,
            'offset': offset
        })
    
    # ========================================================================
    # Transaction Handlers
    # ========================================================================
    
    def _handle_get_transaction(self, path: str):
        """Get transaction by txid."""
        txid = path.split('/')[-1]
        
        with lock:
            # Check mempool first
            tx = blockchain.mempool.get_transaction(txid)
            if tx:
                data = tx.to_dict()
                data['confirmations'] = 0
                data['in_mempool'] = True
                self._send_json(data)
                return
            
            # Search in blocks
            for block in reversed(blockchain.chain):
                for tx in block.transactions:
                    if tx.txid == txid:
                        data = tx.to_dict()
                        data['confirmations'] = blockchain.get_height() - block.height + 1
                        data['block_hash'] = block.hash
                        data['block_height'] = block.height
                        data['in_mempool'] = False
                        self._send_json(data)
                        return
        
        self._send_error("Transaction not found", 404)
    
    def _handle_mempool(self):
        """Get mempool transactions."""
        with lock:
            txs = []
            for txid, tx in blockchain.mempool.transactions.items():
                txs.append({
                    'txid': txid,
                    'size': len(tx.serialize()),
                    'fee': getattr(tx, 'fee', 0),
                    'time': int(time.time())
                })
        
        self._send_json({
            'size': len(txs),
            'transactions': txs
        })
    
    def _handle_mempool_info(self):
        """Get mempool information."""
        with lock:
            txs = blockchain.mempool.transactions.values()
            total_size = sum(len(tx.serialize()) for tx in txs)
            total_fee = sum(getattr(tx, 'fee', 0) for tx in txs)
        
        self._send_json({
            'size': len(txs),
            'bytes': total_size,
            'total_fee': total_fee / config.COIN_UNIT,
            'min_fee_per_byte': config.MIN_TX_FEE_PER_BYTE / config.COIN_UNIT,
        })
    
    def _handle_send_transaction(self, data: Dict):
        """Send/broadcast a raw transaction."""
        if 'raw_tx' not in data and 'hex' not in data:
            self._send_error("Missing 'raw_tx' or 'hex' field")
            return
        
        raw_hex = data.get('raw_tx') or data.get('hex')
        
        try:
            # Deserialize transaction
            raw_bytes = bytes.fromhex(raw_hex)
            tx = Transaction.deserialize(raw_bytes)
            
            with lock:
                # Validate and add to mempool
                if blockchain.mempool.add_transaction(tx, blockchain):
                    # Broadcast to peers
                    if p2p_node:
                        p2p_node.broadcast_transaction(tx)
                    
                    self._send_json({
                        'success': True,
                        'txid': tx.txid,
                        'message': 'Transaction accepted'
                    })
                else:
                    self._send_error("Transaction rejected", 400)
                    
        except Exception as e:
            self._send_error(f"Invalid transaction: {e}", 400)
    
    def _handle_broadcast_transaction(self, data: Dict):
        """Rebroadcast a transaction."""
        if 'txid' not in data:
            self._send_error("Missing 'txid' field")
            return
        
        txid = data['txid']
        
        with lock:
            tx = blockchain.mempool.get_transaction(txid)
            if tx and p2p_node:
                p2p_node.broadcast_transaction(tx)
                self._send_json({
                    'success': True,
                    'txid': txid,
                    'message': 'Transaction rebroadcast'
                })
            else:
                self._send_error("Transaction not found in mempool", 404)
    
    def _handle_decode_transaction(self, data: Dict):
        """Decode a raw transaction."""
        if 'raw_tx' not in data and 'hex' not in data:
            self._send_error("Missing 'raw_tx' or 'hex' field")
            return
        
        raw_hex = data.get('raw_tx') or data.get('hex')
        
        try:
            raw_bytes = bytes.fromhex(raw_hex)
            tx = Transaction.deserialize(raw_bytes)
            self._send_json(tx.to_dict())
        except Exception as e:
            self._send_error(f"Failed to decode: {e}", 400)
    
    # ========================================================================
    # Address & Balance Handlers
    # ========================================================================
    
    def _handle_address(self, path: str):
        """Get address information."""
        address = path.split('/')[-1]
        
        with lock:
            balance = self._get_balance(address)
            pending = self._get_pending_balance(address)
            utxos = self._get_utxos(address)
            
            # Get transaction history
            tx_count = 0
            for block in blockchain.chain:
                for tx in block.transactions:
                    for inp in tx.inputs:
                        if inp.get('address') == address:
                            tx_count += 1
                            break
                    for out in tx.outputs:
                        if out.get('address') == address:
                            tx_count += 1
                            break
        
        self._send_json({
            'address': address,
            'balance': balance / config.COIN_UNIT,
            'balance_satoshi': balance,
            'pending': pending / config.COIN_UNIT,
            'pending_satoshi': pending,
            'utxo_count': len(utxos),
            'tx_count': tx_count,
        })
    
    def _handle_balance(self, path: str):
        """Get address balance."""
        address = path.split('/')[-1]
        
        with lock:
            balance = self._get_balance(address)
            pending = self._get_pending_balance(address)
        
        self._send_json({
            'address': address,
            'balance': balance / config.COIN_UNIT,
            'balance_satoshi': balance,
            'pending': pending / config.COIN_UNIT,
            'pending_satoshi': pending,
            'total': (balance + pending) / config.COIN_UNIT,
            'total_satoshi': balance + pending,
        })
    
    def _handle_utxos(self, path: str):
        """Get UTXOs for address."""
        address = path.split('/')[-1]
        
        with lock:
            utxos = self._get_utxos(address)
        
        self._send_json({
            'address': address,
            'utxos': utxos,
            'count': len(utxos),
            'total': sum(u['amount'] for u in utxos) / config.COIN_UNIT,
        })
    
    def _handle_validate_address(self, path: str):
        """Validate an address."""
        address = path.split('/')[-1]
        
        is_valid = False
        address_type = None
        
        try:
            if address.startswith('S'):
                is_valid = len(address) >= 26 and len(address) <= 35
                address_type = 'p2pkh'
            elif address.startswith('3'):
                is_valid = len(address) >= 26 and len(address) <= 35
                address_type = 'p2sh'
            # Add more validation as needed
        except:
            is_valid = False
        
        self._send_json({
            'address': address,
            'isvalid': is_valid,
            'type': address_type,
            'ismine': False,  # Exchange nodes don't track ownership here
        })
    
    # ========================================================================
    # Exchange-Specific Handlers
    # ========================================================================
    
    def _handle_confirmations(self, path: str):
        """Get confirmation count for a transaction."""
        txid = path.split('/')[-1]
        
        with lock:
            # Check mempool
            if blockchain.mempool.get_transaction(txid):
                self._send_json({
                    'txid': txid,
                    'confirmations': 0,
                    'confirmed': False,
                    'mature': False,
                })
                return
            
            # Search blocks
            for block in reversed(blockchain.chain):
                for tx in block.transactions:
                    if tx.txid == txid:
                        confirmations = blockchain.get_height() - block.height + 1
                        is_coinbase = len(tx.inputs) == 1 and not tx.inputs[0].get('txid')
                        
                        self._send_json({
                            'txid': txid,
                            'confirmations': confirmations,
                            'confirmed': confirmations >= MIN_CONFIRMATIONS,
                            'block_height': block.height,
                            'block_hash': block.hash,
                            'is_coinbase': is_coinbase,
                            'mature': confirmations >= config.COINBASE_MATURITY if is_coinbase else True,
                        })
                        return
        
        self._send_error("Transaction not found", 404)
    
    def _handle_pending(self):
        """Get pending deposits/withdrawals."""
        self._send_json({
            'deposits': pending_deposits,
            'withdrawals': pending_withdrawals,
        })
    
    def _handle_info(self):
        """Get coin information for exchange listing."""
        self._send_json({
            'name': config.COIN_NAME,
            'ticker': config.COIN_TICKER,
            'algorithm': 'SHA-256',
            'consensus': 'Proof of Work',
            'block_time_seconds': config.BLOCK_TIME_TARGET,
            'block_reward': config.BLOCK_REWARD / config.COIN_UNIT,
            'max_supply': config.MAX_SUPPLY / config.COIN_UNIT,
            'current_supply': blockchain.get_height() * config.BLOCK_REWARD / config.COIN_UNIT if blockchain else 0,
            'decimals': 8,
            'min_confirmations': MIN_CONFIRMATIONS,
            'coinbase_maturity': config.COINBASE_MATURITY,
            'address_prefix': 'S',
            'ports': {
                'p2p': DEFAULT_P2P_PORT,
                'rpc': DEFAULT_RPC_PORT,
                'api': DEFAULT_API_PORT,
            },
            'rpc_methods': [
                'getblock', 'getblockhash', 'getblockheader', 'getblockcount',
                'getrawtransaction', 'sendrawtransaction', 'decoderawtransaction',
                'getbalance', 'listunspent', 'validateaddress',
                'getmempoolinfo', 'getrawmempool',
                'getnetworkinfo', 'getpeerinfo', 'getconnectioncount',
            ]
        })
    
    # ========================================================================
    # Network Handlers
    # ========================================================================
    
    def _handle_peers(self):
        """Get peer information."""
        if p2p_node:
            peers = p2p_node.get_peer_info()
            self._send_json({
                'peers': peers,
                'count': len(peers),
            })
        else:
            self._send_json({'peers': [], 'count': 0})
    
    def _handle_network_info(self):
        """Get network information."""
        if p2p_node:
            info = p2p_node.get_network_info()
            self._send_json(info)
        else:
            self._send_json({
                'version': VERSION,
                'subversion': f'/{NODE_NAME}:{VERSION}/',
                'protocolversion': config.PROTOCOL_VERSION,
                'connections': 0,
            })
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _get_balance(self, address: str) -> int:
        """Get confirmed balance for address."""
        balance = 0
        current_height = blockchain.get_height()
        
        for key, utxo in blockchain.utxo_set.items():
            if utxo.get('address') == address:
                # Check if spendable (matured if coinbase)
                confirmations = current_height - utxo.get('height', 0) + 1
                is_coinbase = utxo.get('coinbase', False)
                
                if is_coinbase and confirmations < config.COINBASE_MATURITY:
                    continue  # Skip immature coinbase
                
                balance += utxo.get('amount', 0)
        
        return balance
    
    def _get_pending_balance(self, address: str) -> int:
        """Get pending (mempool) balance for address."""
        pending = 0
        
        for tx in blockchain.mempool.transactions.values():
            for out in tx.outputs:
                if out.get('address') == address:
                    pending += out.get('amount', 0)
        
        return pending
    
    def _get_utxos(self, address: str) -> List[Dict]:
        """Get UTXOs for address."""
        utxos = []
        current_height = blockchain.get_height()
        
        for key, utxo in blockchain.utxo_set.items():
            if utxo.get('address') == address:
                confirmations = current_height - utxo.get('height', 0) + 1
                is_coinbase = utxo.get('coinbase', False)
                is_mature = not is_coinbase or confirmations >= config.COINBASE_MATURITY
                
                parts = key.split(':')
                utxos.append({
                    'txid': parts[0],
                    'vout': int(parts[1]),
                    'address': address,
                    'amount': utxo.get('amount', 0),
                    'confirmations': confirmations,
                    'is_coinbase': is_coinbase,
                    'is_mature': is_mature,
                    'spendable': is_mature and confirmations >= 1,
                })
        
        return utxos


# ============================================================================
# MAIN NODE CLASS
# ============================================================================

class ExchangeNode:
    """Main exchange node combining P2P, RPC, and REST API."""
    
    def __init__(
        self,
        data_dir: str = None,
        p2p_port: int = DEFAULT_P2P_PORT,
        rpc_port: int = DEFAULT_RPC_PORT,
        api_port: int = DEFAULT_API_PORT,
        rpc_user: str = "rpcuser",
        rpc_password: str = "rpcpassword",
        testnet: bool = False,
    ):
        self.data_dir = data_dir or config.get_data_dir(testnet)
        self.p2p_port = p2p_port
        self.rpc_port = rpc_port
        self.api_port = api_port
        self.rpc_user = rpc_user
        self.rpc_password = rpc_password
        self.testnet = testnet
        
        self._running = False
        self._threads = []
        
        # Initialize components
        self._init_blockchain()
        self._init_p2p()
        self._init_rpc()
    
    def _init_blockchain(self):
        """Initialize blockchain."""
        global blockchain, mempool
        
        print(f"📁 Data directory: {self.data_dir}")
        os.makedirs(self.data_dir, exist_ok=True)
        
        blockchain = Blockchain(data_dir=self.data_dir)
        blockchain.load()
        mempool = blockchain.mempool
        
        print(f"📊 Blockchain height: {blockchain.get_height()}")
        print(f"📦 Genesis: {blockchain.chain[0].hash[:16]}...")
    
    def _init_p2p(self):
        """Initialize P2P node."""
        global p2p_node
        
        p2p_node = Node(
            host='0.0.0.0',
            port=self.p2p_port,
            data_dir=self.data_dir,
            testnet=self.testnet,
        )
        
        # Share blockchain
        p2p_node.blockchain = blockchain
        p2p_node.mempool = mempool
        
        print(f"🌐 P2P port: {self.p2p_port}")
    
    def _init_rpc(self):
        """Initialize RPC server."""
        global rpc_server
        
        # RPC server uses the P2P node
        rpc_server = RPCServer(
            host='0.0.0.0',
            port=self.rpc_port,
            username=self.rpc_user,
            password=self.rpc_password,
        )
        rpc_server.node = p2p_node
        
        print(f"🔌 RPC port: {self.rpc_port} (user: {self.rpc_user})")
    
    def start(self):
        """Start all node components."""
        global node_start_time, is_synced
        
        print(f"\n{'='*60}")
        print(f"  {NODE_NAME} v{VERSION}")
        print(f"  Network: {'Testnet' if self.testnet else 'Mainnet'}")
        print(f"{'='*60}\n")
        
        self._running = True
        node_start_time = time.time()
        
        # Start P2P node
        print("Starting P2P node...")
        p2p_node.start()
        
        # Start RPC server
        print("Starting RPC server...")
        rpc_thread = threading.Thread(target=rpc_server.start)
        rpc_thread.daemon = True
        rpc_thread.start()
        self._threads.append(rpc_thread)
        
        # Start REST API
        print(f"Starting REST API on port {self.api_port}...")
        api_server = HTTPServer(('0.0.0.0', self.api_port), ExchangeAPIHandler)
        api_thread = threading.Thread(target=api_server.serve_forever)
        api_thread.daemon = True
        api_thread.start()
        self._threads.append(api_thread)
        
        # Start sync monitor
        sync_thread = threading.Thread(target=self._sync_monitor)
        sync_thread.daemon = True
        sync_thread.start()
        self._threads.append(sync_thread)
        
        # Start health monitor
        health_thread = threading.Thread(target=self._health_monitor)
        health_thread.daemon = True
        health_thread.start()
        self._threads.append(health_thread)
        
        print(f"\n✅ Node started successfully!")
        print(f"   P2P:  0.0.0.0:{self.p2p_port}")
        print(f"   RPC:  0.0.0.0:{self.rpc_port}")
        print(f"   API:  0.0.0.0:{self.api_port}")
        print(f"\n📖 Exchange Integration:")
        print(f"   Health:    http://localhost:{self.api_port}/health")
        print(f"   Status:    http://localhost:{self.api_port}/status")
        print(f"   Info:      http://localhost:{self.api_port}/info")
        print(f"   RPC:       http://{self.rpc_user}:{self.rpc_password}@localhost:{self.rpc_port}/\n")
        
        is_synced = True  # Will be updated by sync monitor
    
    def stop(self):
        """Stop all node components."""
        print("\n🛑 Stopping node...")
        self._running = False
        
        if p2p_node:
            p2p_node.stop()
        
        if rpc_server:
            rpc_server.stop()
        
        # Save blockchain
        if blockchain:
            blockchain.save()
        
        print("✅ Node stopped")
    
    def _sync_monitor(self):
        """Monitor sync status."""
        global is_synced
        
        while self._running:
            try:
                tip = blockchain.get_latest_block()
                age = int(time.time()) - tip.timestamp
                
                # Consider synced if tip is less than 10 minutes old
                is_synced = age < 600
                
            except Exception as e:
                print(f"Sync monitor error: {e}")
            
            time.sleep(10)
    
    def _health_monitor(self):
        """Periodic health checks."""
        while self._running:
            try:
                # Log status periodically
                if blockchain:
                    height = blockchain.get_height()
                    mempool_size = blockchain.mempool.size()
                    peers = p2p_node.peer_manager.get_connection_count()['total'] if p2p_node else 0
                    
                    if height % 10 == 0:  # Log every 10 blocks
                        print(f"📊 Height: {height} | Mempool: {mempool_size} | Peers: {peers}")
                
            except Exception as e:
                print(f"Health monitor error: {e}")
            
            time.sleep(HEALTH_CHECK_INTERVAL)
    
    def run(self):
        """Run the node until interrupted."""
        self.start()
        
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        
        self.stop()


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description=NODE_NAME)
    
    # Network options
    parser.add_argument('--testnet', action='store_true', help='Use testnet')
    parser.add_argument('--datadir', type=str, help='Data directory')
    
    # Port options
    parser.add_argument('--p2p-port', type=int, default=DEFAULT_P2P_PORT, help=f'P2P port (default: {DEFAULT_P2P_PORT})')
    parser.add_argument('--rpc-port', type=int, default=DEFAULT_RPC_PORT, help=f'RPC port (default: {DEFAULT_RPC_PORT})')
    parser.add_argument('--api-port', type=int, default=DEFAULT_API_PORT, help=f'API port (default: {DEFAULT_API_PORT})')
    
    # RPC options
    parser.add_argument('--rpcuser', type=str, default='rpcuser', help='RPC username')
    parser.add_argument('--rpcpassword', type=str, default='rpcpassword', help='RPC password')
    
    # Other options
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    
    args = parser.parse_args()
    
    # Create and run node
    node = ExchangeNode(
        data_dir=args.datadir,
        p2p_port=args.p2p_port,
        rpc_port=args.rpc_port,
        api_port=args.api_port,
        rpc_user=args.rpcuser,
        rpc_password=args.rpcpassword,
        testnet=args.testnet,
    )
    
    # Handle signals
    def signal_handler(sig, frame):
        node.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    node.run()


if __name__ == '__main__':
    main()
