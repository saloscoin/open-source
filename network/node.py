"""
SALOCOIN Node
Full node implementation with P2P networking.
"""

import socket
import time
import threading
import json
import os
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

from .peer import Peer, PeerManager, PeerState
from .protocol import Protocol, Message, MessageType, InvType
from .discovery import PeerDiscovery
from core.blockchain import Blockchain, Block
from core.transaction import Transaction, TransactionPool
from masternode import MasternodeList, MasternodeManager, MasternodePayments
from masternode import Governance, InstantSend, PrivateSend, SporkManager
import config


class NodeState(Enum):
    """Node states."""
    STOPPED = 0
    STARTING = 1
    SYNCING = 2
    READY = 3
    STOPPING = 4


class Node:
    """
    SALOCOIN Full Node.
    
    Handles P2P networking, block/transaction propagation,
    and masternode coordination.
    """
    
    def __init__(
        self,
        data_dir: str = None,
        host: str = "0.0.0.0",
        port: int = config.P2P_PORT,
        testnet: bool = False,
    ):
        """
        Initialize node.
        
        Args:
            data_dir: Data directory
            host: Host to bind to
            port: Port to listen on
            testnet: Use testnet configuration
        """
        self.data_dir = data_dir or config.get_data_dir(testnet)
        self.host = host
        self.port = port
        self.testnet = testnet
        
        # Network magic
        self.magic = config.TESTNET_MAGIC if testnet else config.MAINNET_MAGIC
        
        # State
        self.state = NodeState.STOPPED
        
        # Core components
        self.blockchain = Blockchain(self.data_dir)
        self.mempool = TransactionPool()
        
        # Networking
        self.peer_manager = PeerManager()
        self.discovery = PeerDiscovery(self.peer_manager)
        
        # Server socket
        self._server_socket: Optional[socket.socket] = None
        
        # Masternode components
        self.masternode_list = MasternodeList()
        self.masternode_manager = MasternodeManager(self.blockchain, self.masternode_list)
        self.masternode_payments = MasternodePayments(self.blockchain, self.masternode_list)
        self.governance = Governance(self.blockchain, self.masternode_list)
        self.instantsend = InstantSend(self.blockchain, self.masternode_list)
        self.privatesend = PrivateSend(self.blockchain, self.masternode_list)
        self.spork_manager = SporkManager()
        
        # Sync state
        self.syncing = False
        self.sync_peer: Optional[Peer] = None
        self.best_height = 0
        
        # Threading
        self._running = False
        self._threads: List[threading.Thread] = []
        self._lock = threading.Lock()
        
        # Event handlers
        self.on_block: Optional[Callable[[Block], None]] = None
        self.on_transaction: Optional[Callable[[Transaction], None]] = None
    
    def start(self):
        """Start the node."""
        if self.state != NodeState.STOPPED:
            return
        
        print(f"\n{'='*60}")
        print(f"Starting SALOCOIN Node")
        print(f"Network: {'Testnet' if self.testnet else 'Mainnet'}")
        print(f"Port: {self.port}")
        print(f"Data Dir: {self.data_dir}")
        print(f"{'='*60}\n")
        
        self.state = NodeState.STARTING
        self._running = True
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Load blockchain
        self.blockchain.load()
        print(f"Blockchain height: {self.blockchain.get_height()}")
        
        # Load masternode list
        mn_file = os.path.join(self.data_dir, config.MASTERNODE_FILENAME)
        if os.path.exists(mn_file):
            self.masternode_list.load(mn_file)
            print(f"Loaded {self.masternode_list.size()} masternodes")
        
        # Start server socket
        self._start_server()
        
        # Start peer discovery
        self.discovery.start()
        
        # Start background threads
        self._start_threads()
        
        self.state = NodeState.SYNCING
        print("Node started, syncing...")
    
    def stop(self):
        """Stop the node."""
        if self.state == NodeState.STOPPED:
            return
        
        print("\nStopping node...")
        self.state = NodeState.STOPPING
        self._running = False
        
        # Stop discovery
        self.discovery.stop()
        
        # Close server socket
        if self._server_socket:
            self._server_socket.close()
        
        # Disconnect peers
        for peer in self.peer_manager.get_peers():
            peer.disconnect()
        
        # Wait for threads
        for thread in self._threads:
            thread.join(timeout=5)
        
        # Save state
        self.blockchain.save()
        
        mn_file = os.path.join(self.data_dir, config.MASTERNODE_FILENAME)
        self.masternode_list.save(mn_file)
        
        self.state = NodeState.STOPPED
        print("Node stopped")
    
    def _start_server(self):
        """Start server socket for inbound connections."""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self.host, self.port))
            self._server_socket.listen(100)
            self._server_socket.settimeout(1.0)
            
            # Start listener thread
            thread = threading.Thread(target=self._accept_connections)
            thread.daemon = True
            thread.start()
            self._threads.append(thread)
            
        except Exception as e:
            print(f"Failed to start server: {e}")
    
    def _accept_connections(self):
        """Accept inbound connections."""
        while self._running:
            try:
                client_socket, address = self._server_socket.accept()
                
                ip, port = address
                print(f"Inbound connection from {ip}:{port}")
                
                # Create peer
                peer = self.peer_manager.add_peer(ip, port, inbound=True)
                if peer:
                    peer.set_socket(client_socket)
                    self._setup_peer_handlers(peer)
                else:
                    client_socket.close()
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    print(f"Accept error: {e}")
    
    def _start_threads(self):
        """Start background processing threads."""
        # Main loop thread
        thread = threading.Thread(target=self._main_loop)
        thread.daemon = True
        thread.start()
        self._threads.append(thread)
        
        # Sync thread
        thread = threading.Thread(target=self._sync_loop)
        thread.daemon = True
        thread.start()
        self._threads.append(thread)
        
        # Masternode ping thread
        thread = threading.Thread(target=self._masternode_loop)
        thread.daemon = True
        thread.start()
        self._threads.append(thread)
    
    def _main_loop(self):
        """Main processing loop."""
        while self._running:
            try:
                # Cleanup disconnected peers
                self.peer_manager.cleanup_disconnected()
                
                # Update masternode states
                self.masternode_list.update_state(self.blockchain.get_height())
                
                # Cleanup InstantSend
                self.instantsend.cleanup_expired()
                
                # Cleanup PrivateSend
                self.privatesend.cleanup_sessions()
                
                # Cleanup governance
                self.governance.cleanup_expired()
                
                time.sleep(1)
                
            except Exception as e:
                print(f"Main loop error: {e}")
    
    def _sync_loop(self):
        """Blockchain sync loop."""
        while self._running:
            try:
                if self.state == NodeState.SYNCING:
                    self._sync_blockchain()
                
                time.sleep(10)
                
            except Exception as e:
                print(f"Sync loop error: {e}")
    
    def _masternode_loop(self):
        """Masternode maintenance loop."""
        while self._running:
            try:
                # Send masternode ping if running local masternode
                if self.masternode_manager.running:
                    self.masternode_manager.ping()
                
                time.sleep(60)
                
            except Exception as e:
                print(f"Masternode loop error: {e}")
    
    def _setup_peer_handlers(self, peer: Peer):
        """Set up message handlers for a peer."""
        peer.register_handler(MessageType.INV, self._handle_inv)
        peer.register_handler(MessageType.BLOCK, self._handle_block)
        peer.register_handler(MessageType.TX, self._handle_tx)
        peer.register_handler(MessageType.GETDATA, self._handle_getdata)
        peer.register_handler(MessageType.GETBLOCKS, self._handle_getblocks)
        peer.register_handler(MessageType.GETHEADERS, self._handle_getheaders)
        peer.register_handler(MessageType.ADDR, self._handle_addr)
        peer.register_handler(MessageType.GETADDR, self._handle_getaddr)
        peer.register_handler(MessageType.MEMPOOL, self._handle_mempool)
    
    def _handle_inv(self, peer: Peer, message: Message):
        """Handle INV message."""
        # Parse inventory
        payload = message.payload
        count, offset = Protocol._read_varint(payload)
        
        wanted = []
        
        for _ in range(count):
            if offset + 36 > len(payload):
                break
            
            inv_type = int.from_bytes(payload[offset:offset+4], 'little')
            inv_hash = payload[offset+4:offset+36][::-1].hex()
            offset += 36
            
            # Check if we want this item
            if inv_type == InvType.TX.value:
                if inv_hash not in self.mempool.transactions:
                    wanted.append({'type': InvType.TX, 'hash': inv_hash})
            
            elif inv_type == InvType.BLOCK.value:
                if not self.blockchain.get_block_by_hash(inv_hash):
                    wanted.append({'type': InvType.BLOCK, 'hash': inv_hash})
        
        # Request wanted items
        if wanted:
            getdata = Protocol.create_getdata_message(wanted)
            peer.send_message(getdata)
    
    def _handle_block(self, peer: Peer, message: Message):
        """Handle BLOCK message."""
        # Deserialize block (simplified)
        # Full implementation would properly deserialize the block
        try:
            # For now, just acknowledge
            print(f"Received block from {peer.address}")
            
        except Exception as e:
            print(f"Error handling block: {e}")
    
    def _handle_tx(self, peer: Peer, message: Message):
        """Handle TX message."""
        try:
            # Deserialize and add to mempool
            # Full implementation would properly deserialize
            print(f"Received transaction from {peer.address}")
            
        except Exception as e:
            print(f"Error handling tx: {e}")
    
    def _handle_getdata(self, peer: Peer, message: Message):
        """Handle GETDATA message."""
        payload = message.payload
        count, offset = Protocol._read_varint(payload)
        
        for _ in range(count):
            if offset + 36 > len(payload):
                break
            
            inv_type = int.from_bytes(payload[offset:offset+4], 'little')
            inv_hash = payload[offset+4:offset+36][::-1].hex()
            offset += 36
            
            if inv_type == InvType.TX.value:
                tx = self.mempool.get_transaction(inv_hash)
                if tx:
                    # Send transaction
                    tx_msg = Protocol.create_tx_message(tx.serialize())
                    peer.send_message(tx_msg)
            
            elif inv_type == InvType.BLOCK.value:
                block = self.blockchain.get_block_by_hash(inv_hash)
                if block:
                    # Send block header (simplified)
                    block_msg = Protocol.create_block_message(block.serialize_header())
                    peer.send_message(block_msg)
    
    def _handle_getblocks(self, peer: Peer, message: Message):
        """Handle GETBLOCKS message."""
        # Send INV for blocks
        pass
    
    def _handle_getheaders(self, peer: Peer, message: Message):
        """Handle GETHEADERS message."""
        # Send headers
        pass
    
    def _handle_addr(self, peer: Peer, message: Message):
        """Handle ADDR message."""
        # Parse addresses
        payload = message.payload
        count, offset = Protocol._read_varint(payload)
        
        addresses = []
        for _ in range(count):
            if offset + 30 > len(payload):
                break
            
            timestamp = int.from_bytes(payload[offset:offset+4], 'little')
            services = int.from_bytes(payload[offset+4:offset+12], 'little')
            ip = Protocol._decode_ip(payload[offset+12:offset+28])
            port = int.from_bytes(payload[offset+28:offset+30], 'big')
            offset += 30
            
            addresses.append({
                'ip': ip,
                'port': port,
                'services': services,
                'timestamp': timestamp,
            })
        
        self.discovery.handle_addr_message(addresses)
    
    def _handle_getaddr(self, peer: Peer, message: Message):
        """Handle GETADDR message."""
        addresses = self.discovery.get_addresses_for_share()
        addr_msg = Protocol.create_addr_message(addresses)
        peer.send_message(addr_msg)
    
    def _handle_mempool(self, peer: Peer, message: Message):
        """Handle MEMPOOL message."""
        # Send INV for all mempool transactions
        txs = self.mempool.get_transactions()
        
        if txs:
            inventory = [{'type': InvType.TX, 'hash': tx.txid} for tx in txs]
            inv_msg = Protocol.create_inv_message(inventory)
            peer.send_message(inv_msg)
    
    def _sync_blockchain(self):
        """Sync blockchain with peers."""
        ready_peers = self.peer_manager.get_ready_peers()
        
        if not ready_peers:
            return
        
        # Find best peer
        best_peer = max(ready_peers, key=lambda p: p.start_height)
        
        if best_peer.start_height <= self.blockchain.get_height():
            # We're synced
            if self.state == NodeState.SYNCING:
                self.state = NodeState.READY
                print("Blockchain synced!")
            return
        
        self.best_height = best_peer.start_height
        
        # Request blocks
        block_locator = self._get_block_locator()
        getblocks = Protocol.create_getblocks_message(block_locator)
        best_peer.send_message(getblocks)
    
    def _get_block_locator(self) -> List[str]:
        """Get block locator hashes for sync."""
        locator = []
        height = self.blockchain.get_height()
        
        step = 1
        while height >= 0:
            block = self.blockchain.get_block_by_height(height)
            if block:
                locator.append(block.hash)
            
            if len(locator) >= 10:
                step *= 2
            
            height -= step
        
        # Add genesis
        genesis = self.blockchain.get_block_by_height(0)
        if genesis and genesis.hash not in locator:
            locator.append(genesis.hash)
        
        return locator
    
    def add_block(self, block: Block) -> bool:
        """
        Add a new block to the blockchain.
        
        Args:
            block: Block to add
            
        Returns:
            True if block was added
        """
        if self.blockchain.add_block(block):
            # Announce to peers
            inv = Protocol.create_inv_message([
                {'type': InvType.BLOCK, 'hash': block.hash}
            ])
            self.peer_manager.broadcast(inv)
            
            # Callback
            if self.on_block:
                self.on_block(block)
            
            return True
        
        return False
    
    def add_transaction(self, tx: Transaction) -> bool:
        """
        Add a transaction to the mempool.
        
        Args:
            tx: Transaction to add
            
        Returns:
            True if added to mempool
        """
        if self.mempool.add_transaction(tx):
            # Announce to peers
            inv = Protocol.create_inv_message([
                {'type': InvType.TX, 'hash': tx.txid}
            ])
            self.peer_manager.broadcast(inv)
            
            # Callback
            if self.on_transaction:
                self.on_transaction(tx)
            
            return True
        
        return False
    
    def get_info(self) -> Dict[str, Any]:
        """Get node information."""
        return {
            'version': config.PROTOCOL_VERSION,
            'protocolversion': config.PROTOCOL_VERSION,
            'blocks': self.blockchain.get_height(),
            'timeoffset': 0,
            'connections': self.peer_manager.get_connection_count()['total'],
            'difficulty': self.blockchain.current_difficulty,
            'testnet': self.testnet,
            'relayfee': config.MIN_TX_FEE_PER_BYTE / config.COIN_UNIT,
            'errors': '',
        }
    
    def get_network_info(self) -> Dict[str, Any]:
        """Get network information."""
        return {
            'version': config.PROTOCOL_VERSION,
            'subversion': config.USER_AGENT,
            'protocolversion': config.PROTOCOL_VERSION,
            'connections': self.peer_manager.get_connection_count(),
            'networks': [
                {
                    'name': 'ipv4',
                    'reachable': True,
                    'port': self.port,
                }
            ],
            'relayfee': config.MIN_TX_FEE_PER_BYTE / config.COIN_UNIT,
        }
    
    def get_peer_info(self) -> List[Dict[str, Any]]:
        """Get peer information."""
        return self.peer_manager.get_peer_info()
