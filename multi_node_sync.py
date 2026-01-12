#!/usr/bin/env python3
"""
SALOCOIN Multi-Node Synchronization

This module enables multiple seed/API nodes to stay synchronized.
Each node periodically syncs with other known nodes.

Usage:
    On each VPS, run seed_server_production.py with PEER_NODES configured.
"""

import os
import sys
import json
import time
import threading
import requests
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.blockchain import Block


# Known peer nodes - add your seed node URLs/IPs here
PEER_NODES = [
    "https://api.salocoin.org",        # Primary API node
    "https://seed.salocoin.org",       # Seed node
    "https://bootstrap.salocoin.org",  # Bootstrap node
    # "http://YOUR_IP:7339",           # Add your node IP here
]


class MultiNodeSync:
    """
    Synchronizes blockchain across multiple nodes.
    
    Each node runs this to:
    1. Periodically check peer heights
    2. Download missing blocks from peers
    3. Broadcast new blocks to peers
    """
    
    def __init__(self, blockchain, local_url: str = None, peer_nodes: List[str] = None):
        self.blockchain = blockchain
        self.local_url = local_url
        self.peer_nodes = peer_nodes or PEER_NODES
        self.running = False
        self.sync_interval = 10  # Check peers every 10 seconds
        self.timeout = 30
        
        # Remove self from peer list
        if self.local_url and self.local_url in self.peer_nodes:
            self.peer_nodes.remove(self.local_url)
        
        # Track peer status
        self.peer_status: Dict[str, dict] = {}
    
    def start(self):
        """Start background sync."""
        if self.running:
            return
        
        self.running = True
        
        # Start sync thread
        thread = threading.Thread(target=self._sync_loop, daemon=True)
        thread.start()
        
        # Start peer health check
        thread = threading.Thread(target=self._health_loop, daemon=True)
        thread.start()
        
        print(f"Multi-node sync started with {len(self.peer_nodes)} peers")
    
    def stop(self):
        """Stop sync."""
        self.running = False
    
    def _sync_loop(self):
        """Main sync loop."""
        while self.running:
            try:
                self._sync_with_peers()
            except Exception as e:
                print(f"Sync error: {e}")
            
            time.sleep(self.sync_interval)
    
    def _health_loop(self):
        """Check peer health."""
        while self.running:
            try:
                for peer in self.peer_nodes:
                    self._check_peer_health(peer)
            except Exception as e:
                pass
            
            time.sleep(60)  # Check health every minute
    
    def _check_peer_health(self, peer_url: str):
        """Check if peer is healthy."""
        try:
            resp = requests.get(f"{peer_url}/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.peer_status[peer_url] = {
                    'alive': True,
                    'height': data.get('height', 0),
                    'last_check': time.time()
                }
            else:
                self.peer_status[peer_url] = {'alive': False, 'last_check': time.time()}
        except:
            self.peer_status[peer_url] = {'alive': False, 'last_check': time.time()}
    
    def _sync_with_peers(self):
        """Sync blockchain with peers."""
        local_height = self.blockchain.get_height()
        
        for peer_url in self.peer_nodes:
            try:
                # Get peer status
                resp = requests.get(f"{peer_url}/status", timeout=self.timeout)
                if resp.status_code != 200:
                    continue
                
                peer_data = resp.json()
                peer_height = peer_data.get('height', 0)
                
                # If peer has more blocks, sync from them
                if peer_height > local_height:
                    print(f"Syncing from {peer_url}: {local_height} -> {peer_height}")
                    self._download_blocks(peer_url, local_height + 1, peer_height)
                    local_height = self.blockchain.get_height()
                
            except Exception as e:
                continue  # Try next peer
    
    def _download_blocks(self, peer_url: str, start_height: int, end_height: int):
        """Download blocks from peer."""
        for height in range(start_height, end_height + 1):
            try:
                resp = requests.get(f"{peer_url}/block/{height}", timeout=self.timeout)
                if resp.status_code != 200:
                    break
                
                block_data = resp.json()
                block = Block.from_dict(block_data)
                
                # Validate and add block
                if self.blockchain.add_block(block):
                    print(f"  + Block {height} synced from {peer_url}")
                else:
                    print(f"  ! Block {height} rejected")
                    break
                    
            except Exception as e:
                print(f"  ! Error downloading block {height}: {e}")
                break
    
    def broadcast_block(self, block: Block) -> int:
        """
        Broadcast a new block to all peers.
        Returns number of peers that accepted it.
        """
        accepted = 0
        
        for peer_url in self.peer_nodes:
            try:
                resp = requests.post(
                    f"{peer_url}/submit_block",
                    json=block.to_dict(),
                    timeout=self.timeout
                )
                
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get('success'):
                        accepted += 1
                        print(f"  ✓ Block accepted by {peer_url}")
                    else:
                        print(f"  ✗ Block rejected by {peer_url}: {result.get('error')}")
                        
            except Exception as e:
                print(f"  ✗ Failed to broadcast to {peer_url}: {e}")
        
        return accepted
    
    def broadcast_transaction(self, tx_data: dict) -> int:
        """Broadcast transaction to all peers."""
        accepted = 0
        
        for peer_url in self.peer_nodes:
            try:
                resp = requests.post(
                    f"{peer_url}/submit_tx",
                    json=tx_data,
                    timeout=10
                )
                
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get('success'):
                        accepted += 1
                        
            except:
                pass
        
        return accepted
    
    def get_best_peer(self) -> Optional[str]:
        """Get the peer with highest block height."""
        best_peer = None
        best_height = 0
        
        for peer_url, status in self.peer_status.items():
            if status.get('alive') and status.get('height', 0) > best_height:
                best_height = status['height']
                best_peer = peer_url
        
        return best_peer
    
    def get_network_height(self) -> int:
        """Get the highest height in the network."""
        heights = [
            status.get('height', 0) 
            for status in self.peer_status.values() 
            if status.get('alive')
        ]
        return max(heights) if heights else 0


def add_multi_node_sync_to_server(app, blockchain):
    """
    Add multi-node sync to Flask app.
    Call this in seed_server_production.py
    """
    syncer = MultiNodeSync(blockchain)
    syncer.start()
    
    # Add endpoint to get peer status
    @app.route('/peers')
    def get_peers():
        return {
            'peers': list(syncer.peer_nodes),
            'status': syncer.peer_status,
            'local_height': blockchain.get_height(),
            'network_height': syncer.get_network_height()
        }
    
    return syncer


# Example usage
if __name__ == '__main__':
    import argparse
    from core.blockchain import Blockchain
    
    parser = argparse.ArgumentParser(description='Multi-node sync test')
    parser.add_argument('--data-dir', default='./data', help='Data directory')
    args = parser.parse_args()
    
    # Load blockchain
    blockchain = Blockchain(data_dir=args.data_dir)
    blockchain.load()
    
    print(f"Local height: {blockchain.get_height()}")
    
    # Start sync
    syncer = MultiNodeSync(blockchain)
    syncer.start()
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        syncer.stop()
