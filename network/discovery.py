"""
SALOCOIN Peer Discovery
DNS seeds and peer discovery mechanisms.
"""

import socket
import time
import threading
import random
from typing import List, Dict, Optional, Any

from .peer import PeerInfo, PeerManager
import config


class PeerDiscovery:
    """
    Peer discovery using DNS seeds and address propagation.
    """
    
    def __init__(
        self,
        peer_manager: PeerManager,
        dns_seeds: List[str] = None,
        seed_nodes: List[str] = None,
    ):
        """
        Initialize peer discovery.
        
        Args:
            peer_manager: Peer manager instance
            dns_seeds: List of DNS seed hostnames
            seed_nodes: List of hardcoded seed node addresses
        """
        self.peer_manager = peer_manager
        self.dns_seeds = dns_seeds or config.DNS_SEEDS
        self.seed_nodes = seed_nodes or config.SEED_NODES
        
        self._running = False
        self._discovery_thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start peer discovery."""
        self._running = True
        
        self._discovery_thread = threading.Thread(target=self._discovery_loop)
        self._discovery_thread.daemon = True
        self._discovery_thread.start()
    
    def stop(self):
        """Stop peer discovery."""
        self._running = False
    
    def _discovery_loop(self):
        """Background discovery loop."""
        # Initial discovery
        self._discover_peers()
        
        while self._running:
            time.sleep(config.PEER_DISCOVERY_INTERVAL)
            
            # Check if we need more peers
            counts = self.peer_manager.get_connection_count()
            
            if counts['outbound'] < 8:
                self._connect_to_peers()
    
    def _discover_peers(self):
        """Discover peers from all sources."""
        print("Starting peer discovery...")
        
        # Try DNS seeds
        dns_peers = self.query_dns_seeds()
        for info in dns_peers:
            self.peer_manager.add_known_peer(info)
        
        # Add hardcoded seeds
        for addr in self.seed_nodes:
            parts = addr.split(':')
            ip = parts[0]
            port = int(parts[1]) if len(parts) > 1 else config.P2P_PORT
            
            info = PeerInfo(ip=ip, port=port, source='seed')
            self.peer_manager.add_known_peer(info)
        
        print(f"Discovered {len(self.peer_manager.known_peers)} potential peers")
        
        # Try to connect
        self._connect_to_peers()
    
    def query_dns_seeds(self) -> List[PeerInfo]:
        """
        Query DNS seeds for peer addresses.
        
        Returns:
            List of peer info from DNS
        """
        peers = []
        
        for seed in self.dns_seeds:
            try:
                # Query DNS
                results = socket.getaddrinfo(
                    seed,
                    config.P2P_PORT,
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                )
                
                for result in results:
                    ip = result[4][0]
                    port = result[4][1]
                    
                    info = PeerInfo(
                        ip=ip,
                        port=port,
                        source=f'dns:{seed}',
                    )
                    peers.append(info)
                
            except socket.gaierror as e:
                print(f"DNS lookup failed for {seed}: {e}")
            except Exception as e:
                print(f"Error querying {seed}: {e}")
        
        return peers
    
    def _connect_to_peers(self, max_attempts: int = 5):
        """Try to connect to known peers."""
        # Get peers we're not connected to
        connected = set(self.peer_manager.peers.keys())
        available = [
            info for addr, info in self.peer_manager.known_peers.items()
            if addr not in connected and not self.peer_manager.is_banned(info.ip)
        ]
        
        if not available:
            return
        
        # Shuffle for randomness
        random.shuffle(available)
        
        attempts = 0
        for info in available:
            if attempts >= max_attempts:
                break
            
            counts = self.peer_manager.get_connection_count()
            if counts['outbound'] >= 8:
                break
            
            # Try to connect
            peer = self.peer_manager.add_peer(info.ip, info.port, inbound=False)
            if peer:
                if peer.connect():
                    print(f"Connected to {info.address}")
                    
                    # Send version
                    peer.send_version()
                else:
                    self.peer_manager.remove_peer(info.address)
            
            attempts += 1
    
    def request_addresses(self):
        """Request addresses from connected peers."""
        from .protocol import Protocol
        
        message = Protocol.create_getaddr_message()
        
        for peer in self.peer_manager.get_ready_peers()[:3]:
            peer.send_message(message)
    
    def handle_addr_message(self, addresses: List[Dict[str, Any]]):
        """
        Handle received address message.
        
        Args:
            addresses: List of address dictionaries
        """
        current_time = int(time.time())
        
        for addr_data in addresses:
            # Check timestamp (not too old, not in future)
            timestamp = addr_data.get('timestamp', 0)
            
            if timestamp > current_time + 600:  # More than 10 min in future
                continue
            
            if timestamp < current_time - config.MAX_PEER_AGE:
                continue
            
            info = PeerInfo(
                ip=addr_data['ip'],
                port=addr_data['port'],
                services=addr_data.get('services', 1),
                timestamp=timestamp,
                source='addr',
            )
            
            self.peer_manager.add_known_peer(info)
    
    def get_addresses_for_share(self, count: int = 1000) -> List[Dict[str, Any]]:
        """
        Get addresses to share with peers.
        
        Args:
            count: Maximum addresses to return
            
        Returns:
            List of address dictionaries
        """
        # Get recent known peers
        known = self.peer_manager.get_known_peers(count)
        
        # Also add currently connected peers
        for peer in self.peer_manager.get_ready_peers():
            info = PeerInfo(
                ip=peer.ip,
                port=peer.port,
                services=peer.services,
                timestamp=peer.last_seen,
            )
            known.append(info)
        
        # Convert to dict format
        addresses = []
        seen = set()
        
        for info in known:
            if info.address not in seen:
                addresses.append({
                    'ip': info.ip,
                    'port': info.port,
                    'services': info.services,
                    'timestamp': info.timestamp,
                })
                seen.add(info.address)
        
        return addresses[:count]
