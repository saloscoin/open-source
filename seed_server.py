#!/usr/bin/env python3
"""
SALOCOIN Seed Node Server - Production Version
Uses Flask + Gunicorn for handling thousands of concurrent miners.
"""

import sys
import os
import json
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
import requests as http_requests

import config
from core.blockchain import Blockchain, Block
from core.transaction import Transaction

# Data directory
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# Global blockchain
blockchain = Blockchain(data_dir=DATA_DIR)
blockchain.load()

# Lock for thread safety
lock = threading.Lock()

# Flask app
app = Flask(__name__)

# Pool server URL
POOL_SERVER_URL = 'http://127.0.0.1:7262'

# Active peers tracking (IP -> last_seen timestamp)
active_peers = {}
PEER_TIMEOUT = 300  # 5 minutes - consider peer inactive after this


def track_peer():
    """Track the requesting peer's IP and last seen time."""
    ip = request.remote_addr
    # Skip localhost
    if ip and ip not in ('127.0.0.1', '::1'):
        active_peers[ip] = {
            'ip': ip,
            'last_seen': time.time(),
            'user_agent': request.headers.get('User-Agent', 'Unknown')[:50]
        }


def get_active_peers():
    """Get list of active peers (seen in last PEER_TIMEOUT seconds)."""
    now = time.time()
    cutoff = now - PEER_TIMEOUT
    # Clean up old peers and return active ones
    active = []
    to_remove = []
    for ip, info in active_peers.items():
        if info['last_seen'] >= cutoff:
            active.append({
                'ip': ip,
                'last_seen': int(info['last_seen']),
                'ago': int(now - info['last_seen'])
            })
        else:
            to_remove.append(ip)
    for ip in to_remove:
        del active_peers[ip]
    return active


def enrich_block_with_sender_addresses(block_dict):
    """
    Enrich block transactions with sender (from) addresses.
    Looks up the previous output for each input to find the sender address.
    """
    if 'transactions' not in block_dict:
        return block_dict
    
    for tx in block_dict['transactions']:
        if tx.get('is_coinbase'):
            # Coinbase transactions don't have a sender
            continue
        
        for inp in tx.get('inputs', []):
            # Skip if address is already populated
            if inp.get('address'):
                continue
            
            prev_txid = inp.get('txid', '')
            prev_vout = inp.get('vout', 0)
            
            if prev_txid == '0' * 64:
                continue  # Coinbase input
            
            # Look up previous transaction to find sender address
            result = blockchain.get_transaction(prev_txid)
            if result:
                prev_tx, _ = result  # Unpack tuple (tx, block)
                if prev_tx.outputs and prev_vout < len(prev_tx.outputs):
                    prev_output = prev_tx.outputs[prev_vout]
                    inp['address'] = prev_output.address
                    inp['value'] = prev_output.value
    
    return block_dict


@app.route('/pool_stats', methods=['GET'])
def pool_stats():
    """Get mining pool stats - proxied from pool server."""
    try:
        resp = http_requests.get(POOL_SERVER_URL, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            data['pool_online'] = True
            return jsonify(data)
        else:
            return jsonify({
                'pool_online': False,
                'error': 'Pool unavailable',
                'authorized_workers': 0,
                'hashrate_formatted': '0 H/s',
                'blocks_found': 0,
                'total_shares': 0,
                'total_rewards_formatted': '0 SALO',
                'pool_fee': 1,
                'workers': [],
                'pending_payouts': [],
            })
    except Exception as e:
        return jsonify({
            'pool_online': False,
            'error': str(e),
            'authorized_workers': 0,
            'hashrate_formatted': '0 H/s',
            'blocks_found': 0,
            'total_shares': 0,
            'total_rewards_formatted': '0 SALO',
            'pool_fee': 1,
            'workers': [],
            'pending_payouts': [],
        })


@app.route('/status', methods=['GET'])
def status():
    """Get node status."""
    track_peer()  # Track this peer
    ttl = blockchain.mempool.tx_ttl
    ttl_display = "Forever" if ttl == 0 else f"{ttl // 60} minutes"
    
    # Calculate network age from first real block (block 1), not genesis placeholder
    if len(blockchain.chain) > 1:
        start_time = blockchain.chain[1].timestamp  # First mined block
    else:
        start_time = blockchain.chain[0].timestamp
    
    network_age_seconds = int(time.time()) - start_time
    days = network_age_seconds // 86400
    hours = (network_age_seconds % 86400) // 3600
    if days > 0:
        network_age = f"{days}d {hours}h"
    else:
        network_age = f"{hours}h {(network_age_seconds % 3600) // 60}m"
    
    return jsonify({
        'status': 'online',
        'height': blockchain.get_height(),
        'genesis': blockchain.chain[0].hash,
        'start_time': start_time,
        'best_block': blockchain.get_latest_block().hash,
        'difficulty': blockchain.current_difficulty,
        'mempool_size': blockchain.mempool.size(),
        'mempool_ttl': ttl,
        'mempool_ttl_display': ttl_display,
        'network_age': network_age,
        'network_age_seconds': network_age_seconds,
    })


@app.route('/height', methods=['GET'])
def height():
    """Get current blockchain height."""
    return jsonify({'height': blockchain.get_height()})


@app.route('/blocks', methods=['GET'])
def get_blocks():
    """Get all blocks (paginated)."""
    start = request.args.get('start', 0, type=int)
    limit = request.args.get('limit', 100, type=int)
    limit = min(limit, 500)  # Max 500 blocks per request
    
    blocks = []
    for i in range(start, min(start + limit, len(blockchain.chain))):
        block_dict = blockchain.chain[i].to_dict()
        # Enrich with sender addresses for non-coinbase transactions
        enrich_block_with_sender_addresses(block_dict)
        blocks.append(block_dict)
    
    return jsonify({
        'blocks': blocks,
        'start': start,
        'count': len(blocks),
        'total': len(blockchain.chain),
    })


@app.route('/block/<int:height>', methods=['GET'])
def get_block(height):
    """Get block at specific height."""
    if 0 <= height < len(blockchain.chain):
        block_dict = blockchain.chain[height].to_dict()
        enrich_block_with_sender_addresses(block_dict)
        return jsonify(block_dict)
    else:
        return jsonify({'error': 'Block not found'}), 404


@app.route('/block/hash/<block_hash>', methods=['GET'])
def get_block_by_hash(block_hash):
    """Get block by hash."""
    block = blockchain.get_block_by_hash(block_hash)
    if block:
        block_dict = block.to_dict()
        enrich_block_with_sender_addresses(block_dict)
        return jsonify(block_dict)
    else:
        return jsonify({'error': 'Block not found'}), 404


@app.route('/genesis', methods=['GET'])
def genesis():
    """Get genesis block."""
    return jsonify(blockchain.chain[0].to_dict())


@app.route('/tip', methods=['GET'])
def tip():
    """Get chain tip."""
    return jsonify(blockchain.get_latest_block().to_dict())


@app.route('/difficulty', methods=['GET'])
def difficulty():
    """Get current difficulty."""
    return jsonify({
        'difficulty': blockchain.current_difficulty,
        'height': blockchain.get_height(),
    })


@app.route('/mempool', methods=['GET'])
def mempool():
    """Get mempool transactions."""
    txs = blockchain.mempool.get_transactions()
    tx_list = []
    for tx in txs:
        tx_dict = tx.to_dict()
        # Enrich with sender addresses
        if not tx_dict.get('is_coinbase'):
            for inp in tx_dict.get('inputs', []):
                if inp.get('address'):
                    continue
                prev_txid = inp.get('txid', '')
                prev_vout = inp.get('vout', 0)
                if prev_txid == '0' * 64:
                    continue
                result = blockchain.get_transaction(prev_txid)
                if result:
                    prev_tx, _ = result
                    if prev_tx.outputs and prev_vout < len(prev_tx.outputs):
                        inp['address'] = prev_tx.outputs[prev_vout].address
                        inp['value'] = prev_tx.outputs[prev_vout].value
        tx_list.append(tx_dict)
    return jsonify({
        'size': len(tx_list),
        'transactions': tx_list,
    })


@app.route('/utxos/<address>', methods=['GET'])
def get_utxos(address):
    """Get UTXOs for an address."""
    # Include immature coins to show all UTXOs
    utxos = blockchain.get_utxos(address, include_immature=True)
    
    result = []
    for utxo in utxos:
        utxo_data = {
            'txid': utxo['txid'],
            'vout': utxo['vout'],
            'value': utxo['value'],
            'address': utxo.get('address', address),
            'confirmations': utxo['confirmations'],  # Already computed in get_utxos
        }
        
        # Check coinbase maturity
        if utxo.get('is_coinbase', False):
            utxo_data['is_coinbase'] = True
            utxo_data['mature'] = blockchain.is_coinbase_mature(utxo['txid'])
        else:
            utxo_data['mature'] = True
            
        result.append(utxo_data)
    
    return jsonify({
        'address': address,
        'utxos': result,
        'count': len(result),
    })


@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    """Get balance for an address."""
    # Include immature coins to show all balances
    utxos = blockchain.get_utxos(address, include_immature=True)
    current_height = blockchain.get_height()
    
    total = 0
    confirmed = 0
    immature = 0
    
    for utxo in utxos:
        value = utxo['value']
        total += value
        
        if utxo.get('is_coinbase', False):
            if blockchain.is_coinbase_mature(utxo['txid']):
                confirmed += value
            else:
                immature += value
        else:
            confirmed += value
    
    return jsonify({
        'address': address,
        'balance': total,
        'confirmed': confirmed,
        'immature': immature,
        'balance_display': f"{total / config.COIN_UNIT:.8f} SALO",
    })


@app.route('/address/<address>/stats', methods=['GET'])
def get_address_stats(address):
    """Get detailed stats for an address."""
    try:
        utxos = blockchain.get_utxos(address, include_immature=True)
        
        total = 0
        confirmed = 0
        immature = 0
        
        for utxo in utxos:
            value = utxo['value']
            total += value
            
            if utxo.get('is_coinbase', False):
                if blockchain.is_coinbase_mature(utxo['txid']):
                    confirmed += value
                else:
                    immature += value
            else:
                confirmed += value
        
        # Get transaction count from UTXO set (simplified - avoids scanning all blocks)
        tx_count = len(utxos)
        total_received = total  # Approximation from current balance
        total_sent = 0  # Would require full history scan
        
        return jsonify({
            'address': address,
            'balance': total,
            'confirmed': confirmed,
            'immature': immature,
            'balance_display': f"{total / config.COIN_UNIT:.8f} SALO",
            'tx_count': tx_count,
            'total_received': total_received,
            'total_sent': total_sent,
            'total_received_display': f"{total_received / config.COIN_UNIT:.8f} SALO",
            'total_sent_display': f"{total_sent / config.COIN_UNIT:.8f} SALO",
        })
    except Exception as e:
        return jsonify({
            'address': address,
            'balance': 0,
            'confirmed': 0,
            'immature': 0,
            'balance_display': "0.00000000 SALO",
            'tx_count': 0,
            'total_received': 0,
            'total_sent': 0,
            'total_received_display': "0.00000000 SALO",
            'total_sent_display': "0.00000000 SALO",
            'error': str(e)
        })


@app.route('/submit_block', methods=['POST'])
def submit_block():
    """Submit a new block."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        block = Block.from_dict(data)
        
        with lock:
            # Validate block
            if block.height != blockchain.get_height() + 1:
                return jsonify({
                    'error': 'Invalid block height',
                    'expected': blockchain.get_height() + 1,
                    'received': block.height,
                }), 400
            
            if block.previous_hash != blockchain.get_latest_block().hash:
                return jsonify({'error': 'Invalid previous hash'}), 400
            
            # Add block - with detailed error capture
            import io
            import sys
            
            # Capture stdout to get validation error messages
            old_stdout = sys.stdout
            sys.stdout = captured_output = io.StringIO()
            
            success = blockchain.add_block(block)
            
            output = captured_output.getvalue()
            sys.stdout = old_stdout
            
            if success:
                blockchain.save()
                print(f"✓ Block {block.height} added: {block.hash[:16]}...")
                return jsonify({
                    'success': True,
                    'height': block.height,
                    'hash': block.hash,
                })
            else:
                # Print the validation error
                if output:
                    print(f"Block {block.height} rejected: {output.strip()}")
                return jsonify({
                    'error': 'Block validation failed',
                    'details': output.strip() if output else 'Unknown validation error'
                }), 400
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/submit_tx', methods=['POST'])
def submit_tx():
    """Submit a transaction to mempool."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Handle both {'transaction': {...}} and direct {...} format
        tx_data = data.get('transaction', data)
        tx = Transaction.from_dict(tx_data)
        
        # Pre-verify transaction signature
        if not tx.verify():
            print(f"[submit_tx] REJECTED {tx.txid[:16]}... - signature verification failed")
            return jsonify({'error': 'Invalid signature'}), 400
        
        with lock:
            # Capture rejection reason
            import io
            import sys
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            buffer = io.StringIO()
            sys.stdout = buffer
            sys.stderr = buffer  # Also capture stderr
            
            result = blockchain.mempool.add_transaction(tx)
            
            output = buffer.getvalue()
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
            # Log all debug output
            if output:
                for line in output.strip().split('\n'):
                    print(f"[mempool_debug] {line}")
            
            if result:
                print(f"[submit_tx] ACCEPTED {tx.txid[:16]}...")
                return jsonify({
                    'success': True,
                    'txid': tx.txid,
                })
            else:
                # Extract reason from captured output
                reason = "unknown"
                if output:
                    # Get the last line with rejection reason
                    for line in output.strip().split('\n'):
                        if 'rejected' in line.lower():
                            reason = line.split(' - ')[-1] if ' - ' in line else line
                print(f"[submit_tx] REJECTED {tx.txid[:16]}... - {reason}")
                return jsonify({'error': f'Transaction rejected: {reason}'}), 400
                
    except Exception as e:
        print(f"[submit_tx] ERROR: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/sync', methods=['POST'])
def sync():
    """Sync blocks from another node."""
    try:
        data = request.get_json()
        if not data or 'blocks' not in data:
            return jsonify({'error': 'No blocks provided'}), 400
        
        blocks = data['blocks']
        added = 0
        
        with lock:
            for block_data in blocks:
                block = Block.from_dict(block_data)
                
                if block.height == blockchain.get_height() + 1:
                    if blockchain.add_block(block):
                        added += 1
                    else:
                        break
                elif block.height <= blockchain.get_height():
                    continue
                else:
                    break
            
            if added > 0:
                blockchain.save()
        
        return jsonify({
            'success': True,
            'added': added,
            'height': blockchain.get_height(),
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/peers', methods=['GET'])
def peers():
    """Get known peers including official seed nodes."""
    active = get_active_peers()
    
    current_height = blockchain.get_height()
    now = int(time.time())
    
    # Official SALOCOIN nodes - Update these IPs for your deployment
    # These are example entries - replace with your actual seed node IPs
    OFFICIAL_NODE_IP = os.environ.get('SALOCOIN_NODE_IP', '127.0.0.1')
    
    official_nodes = [
        {
            'node_id': 'seed',
            'host': 'seed.salocoin.org',
            'ip': OFFICIAL_NODE_IP,
            'version': '1.1.0',
            'height': current_height,
            'last_seen': now,
            'is_official': True,
            'official': True,
            'type': 'seed'
        },
        {
            'node_id': 'bootstrap',
            'host': 'bootstrap.salocoin.org',
            'ip': OFFICIAL_NODE_IP,
            'version': '1.1.0',
            'height': current_height,
            'last_seen': now,
            'is_official': True,
            'official': True,
            'type': 'bootstrap'
        },
        {
            'node_id': 'api',
            'host': 'api.salocoin.org',
            'ip': OFFICIAL_NODE_IP,
            'version': '1.1.0',
            'height': current_height,
            'last_seen': now,
            'is_official': True,
            'official': True,
            'type': 'api'
        }
    ]
    
    # Format other peers to match expected structure
    formatted_peers = official_nodes.copy()
    for p in active:
        # Skip if it's the server itself
        if p['ip'] == OFFICIAL_NODE_IP:
            continue
        formatted_peers.append({
            'node_id': f"node-{p['ip'].replace('.', '-')}",
            'host': p['ip'],
            'ip': p['ip'],
            'version': '1.0+',
            'height': current_height,
            'last_seen': p['last_seen'],
            'is_official': False,
            'official': False,
            'type': 'peer'
        })
    
    # Calculate network uptime from first real block (block 1), not genesis
    # Genesis has a placeholder timestamp, block 1 is when mining actually started
    if len(blockchain.chain) > 1:
        start_time = blockchain.chain[1].timestamp  # First mined block
    else:
        start_time = blockchain.chain[0].timestamp
    
    network_age_seconds = now - start_time
    days = network_age_seconds // 86400
    hours = (network_age_seconds % 86400) // 3600
    if days > 0:
        uptime_str = f"{days}d {hours}h"
    else:
        uptime_str = f"{hours}h {(network_age_seconds % 3600) // 60}m"
    
    return jsonify({
        'peers': formatted_peers,
        'count': len(formatted_peers),
        'uptime_str': uptime_str,
        'network_age': uptime_str,
        'network_age_seconds': network_age_seconds,
    })


@app.route('/fee_estimate', methods=['GET'])
def fee_estimate():
    """Get fee estimates for all priorities."""
    return jsonify(blockchain.mempool.get_fee_estimates(blockchain))


@app.route('/fee_estimate/<priority>', methods=['GET'])
def fee_estimate_priority(priority):
    """Get fee estimate for a specific priority."""
    estimates = blockchain.mempool.get_fee_estimates(blockchain)
    if priority in estimates:
        return jsonify({priority: estimates[priority]})
    else:
        return jsonify({'error': f'Unknown priority: {priority}'}), 400


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


def mempool_maintenance():
    """Clean up expired transactions periodically."""
    while True:
        time.sleep(60)
        try:
            with lock:
                blockchain.mempool.remove_expired()
        except Exception as e:
            print(f"Mempool maintenance error: {e}")


def main():
    """Start the seed server (development mode)."""
    port = int(os.environ.get('PORT', 7339))
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║           SALOCOIN Seed Node (Production)                 ║
╚═══════════════════════════════════════════════════════════╝
Port: {port}
Blockchain Height: {blockchain.get_height()}
Genesis: {blockchain.chain[0].hash[:32]}...

For production, run with Gunicorn:
  gunicorn -w 4 -b 0.0.0.0:{port} seed_server_production:app

Waiting for connections...
""")
    
    # Start mempool maintenance thread
    threading.Thread(target=mempool_maintenance, daemon=True).start()
    
    # Run Flask dev server (for testing only)
    app.run(host='0.0.0.0', port=port, threaded=True)


if __name__ == '__main__':
    main()
