#!/usr/bin/env python3
"""
SALOCOIN Blockchain Sync Module
Syncs local blockchain with seed node.
"""

import os
import sys
import json
import time
import threading

# Try to use requests library (better SSL handling), fallback to urllib
try:
    import requests
    USE_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    USE_REQUESTS = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.blockchain import Block


class BlockchainSync:
    """Sync blockchain with seed node."""
    
    def __init__(self, blockchain, seed_url="https://api.salocoin.org"):
        self.blockchain = blockchain
        self.seed_url = seed_url
        self.sync_interval = 60  # seconds
        self.running = False
        self.thread = None
        self.last_sync = 0
        self.timeout = 60  # Increase timeout for slow connections
    
    def _request(self, path, data=None):
        """Make HTTP request to seed node."""
        url = f"{self.seed_url}{path}"
        
        try:
            if USE_REQUESTS:
                # Use requests library (better SSL handling)
                if data:
                    resp = requests.post(url, json=data, timeout=self.timeout)
                else:
                    resp = requests.get(url, timeout=self.timeout)
                
                if resp.status_code == 200:
                    return resp.json()
                else:
                    print(f"⚠ Seed node error: {resp.status_code}")
                    return None
            else:
                # Fallback to urllib
                if data:
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(data).encode(),
                        headers={'Content-Type': 'application/json'},
                        method='POST'
                    )
                else:
                    req = urllib.request.Request(url)
                
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode())
        
        except Exception as e:
            print(f"⚠ Sync error: {e}")
            return None
    
    def get_status(self):
        """Get seed node status."""
        return self._request('/status')
    
    def submit_block(self, block):
        """Submit a new block to seed node."""
        result = self._request('/submit_block', block.to_dict())
        
        if result and result.get('success'):
            print(f"✓ Block {block.height} submitted to seed node")
            return True
        elif result and result.get('error'):
            print(f"⚠ Block rejected: {result['error']}")
            return False
        else:
            print("⚠ Failed to submit block to seed node")
            return False
    
    def submit_transaction(self, tx):
        """Submit a transaction to seed node."""
        result = self._request('/submit_tx', tx.to_dict())
        
        if result and result.get('success'):
            print(f"✓ TX {tx.txid[:16]}... submitted to seed node")
            return True
        elif result and result.get('error'):
            print(f"⚠ TX rejected: {result['error']}")
            return False
        else:
            print("⚠ Failed to submit TX to seed node")
            return False
    
    def sync_mempool(self):
        """Sync mempool from seed node."""
        # Get our local txids
        local_txids = list(self.blockchain.mempool.transactions.keys())
        
        result = self._request('/sync_mempool', {'txids': local_txids})
        
        if not result:
            return False
        
        txs = result.get('transactions', [])
        if txs:
            print(f"📥 Syncing {len(txs)} transactions from seed node...")
            for tx_data in txs:
                try:
                    from core.transaction import Transaction
                    tx = Transaction.from_dict(tx_data)
                    if self.blockchain.mempool.add_transaction(tx):
                        print(f"  + TX {tx.txid[:16]}...")
                except Exception as e:
                    print(f"  ✗ Error: {e}")
            self.blockchain.save()
        
        return True
    
    def sync_from_seed(self, quiet=False):
        """Sync blocks from seed node. Set quiet=True to suppress output."""
        local_height = self.blockchain.get_height()
        
        # First sync: validate genesis matches
        if local_height == 0:
            status = self.get_status()
            if status:
                remote_genesis = status.get('genesis', '')
                local_genesis = self.blockchain.chain[0].hash if self.blockchain.chain else ''
                
                if remote_genesis and local_genesis and remote_genesis != local_genesis:
                    if not quiet:
                        print(f"❌ GENESIS MISMATCH! Network rejected.")
                        print(f"   Local:  {local_genesis[:32]}...")
                        print(f"   Remote: {remote_genesis[:32]}...")
                        print(f"   Your blockchain is invalid. Delete data/ folder and restart.")
                    return False
        
        # Get status to check remote height
        status = self.get_status()
        if not status:
            return False
        
        remote_height = status.get('height', 0)
        
        if remote_height <= local_height:
            if not quiet:
                print(f"✓ Already at latest height ({local_height})")
            self.last_sync = time.time()
            return True
        
        # Fetch blocks from our height using /blocks endpoint
        result = self._request(f'/blocks?start={local_height + 1}&limit=500')
        
        if not result:
            return False
        
        blocks = result.get('blocks', [])
        
        if blocks:
            if not quiet:
                print(f"📥 Syncing {len(blocks)} blocks from seed node...")
            
            for block_data in blocks:
                try:
                    block = Block.from_dict(block_data)
                    
                    if self.blockchain.add_block(block):
                        if not quiet:
                            print(f"  + Block {block.height}: {block.hash[:24]}...")
                    else:
                        if not quiet:
                            print(f"  ✗ Failed to add block {block.height}")
                        return False
                
                except Exception as e:
                    if not quiet:
                        print(f"  ✗ Error parsing block: {e}")
                    return False
            
            self.blockchain.save()
            if not quiet:
                print(f"✓ Synced to height {self.blockchain.get_height()}")
            
            # If there are more blocks, continue syncing
            if self.blockchain.get_height() < remote_height:
                return self.sync_from_seed(quiet)
        
        self.last_sync = time.time()
        return True
    
    def resync_chain(self):
        """Force resync - used when our block was rejected (someone else found a block).
        This removes our last block(s) that were rejected and syncs the network's blocks."""
        print("🔄 Chain diverged - performing resync...")
        
        # Get seed status to compare chains
        status = self.get_status()
        if not status:
            print("⚠ Cannot reach seed node for resync")
            return False
        
        remote_height = status.get('height', 0)
        local_height = self.blockchain.get_height()
        
        # If we're ahead or at same height but our block was rejected,
        # we need to rollback to find common ancestor
        if local_height >= remote_height:
            # Rollback our chain by 1 block to the previous state
            if len(self.blockchain.chain) > 1:
                removed_block = self.blockchain.chain.pop()
                print(f"  ⏪ Rolled back block {removed_block.height}: {removed_block.hash[:24]}...")
                
                # Update UTXO set for the rollback
                if hasattr(self.blockchain, 'utxo_set'):
                    for tx in removed_block.transactions:
                        # Remove outputs from this block
                        for i in range(len(tx.outputs)):
                            key = f"{tx.txid}:{i}"
                            if key in self.blockchain.utxo_set:
                                del self.blockchain.utxo_set[key]
                        # Restore inputs (simplified - may need improvement)
                        for inp in tx.inputs:
                            if inp.txid != "0" * 64:  # Not coinbase
                                # We don't have the original output data, so skip
                                pass
        
        # Now sync from seed to get the correct chain
        self.blockchain.save()
        return self.sync_from_seed()
    
    def _sync_loop(self):
        """Background sync loop."""
        while self.running:
            try:
                self.sync_from_seed()
                self.sync_mempool()  # Also sync mempool
            except Exception as e:
                print(f"⚠ Sync loop error: {e}")
            
            # Wait for next sync interval
            for _ in range(self.sync_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def start_background_sync(self):
        """Start background sync thread."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.thread.start()
        print(f"📡 Background sync started (every {self.sync_interval}s)")
    
    def stop(self):
        """Stop background sync."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)


def main():
    """Test sync functionality."""
    import config
    from core.blockchain import Blockchain
    
    DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    blockchain = Blockchain(data_dir=DATA_DIR)
    blockchain.load()
    
    sync = BlockchainSync(blockchain)
    
    print(f"Local height: {blockchain.get_height()}")
    
    status = sync.get_status()
    if status:
        print(f"Seed node: {status}")
        sync.sync_from_seed()
    else:
        print("Seed node not reachable")


if __name__ == '__main__':
    main()
