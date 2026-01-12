"""
SALOCOIN Peer Management
Handles individual peer connections and peer list management.
"""

import socket
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from .protocol import Protocol, Message, MessageType
import config


class PeerState(Enum):
    """Peer connection states."""
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    VERSION_SENT = 3
    READY = 4
    DISCONNECTING = 5
    BANNED = 6


@dataclass
class PeerInfo:
    """Peer address information."""
    
    ip: str
    port: int
    services: int = 1
    timestamp: int = 0
    source: str = ''  # How we learned about this peer
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = int(time.time())
    
    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ip': self.ip,
            'port': self.port,
            'services': self.services,
            'timestamp': self.timestamp,
            'source': self.source,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PeerInfo':
        return cls(
            ip=data['ip'],
            port=data['port'],
            services=data.get('services', 1),
            timestamp=data.get('timestamp', 0),
            source=data.get('source', ''),
        )


class Peer:
    """
    Represents a connection to a peer node.
    
    Handles message sending/receiving and connection management.
    """
    
    def __init__(
        self,
        ip: str,
        port: int,
        inbound: bool = False,
        magic: bytes = config.MAINNET_MAGIC,
    ):
        """
        Initialize peer connection.
        
        Args:
            ip: Peer IP address
            port: Peer port
            inbound: True if peer connected to us
            magic: Network magic bytes
        """
        self.ip = ip
        self.port = port
        self.inbound = inbound
        self.magic = magic
        
        self.socket: Optional[socket.socket] = None
        self.state = PeerState.DISCONNECTED
        
        # Connection info
        self.connected_at: int = 0
        self.last_seen: int = 0
        self.last_send: int = 0
        self.last_recv: int = 0
        
        # Peer capabilities
        self.version: int = 0
        self.services: int = 0
        self.user_agent: str = ''
        self.start_height: int = 0
        self.relay: bool = True
        self.nonce: int = 0
        
        # Statistics
        self.bytes_sent: int = 0
        self.bytes_recv: int = 0
        self.messages_sent: int = 0
        self.messages_recv: int = 0
        
        # Ping tracking
        self.ping_nonce: int = 0
        self.ping_time: int = 0
        self.ping_wait: int = 0
        self.min_ping: int = 0
        
        # Sync state
        self.synced_headers: int = 0
        self.synced_blocks: int = 0
        
        # Ban score
        self.ban_score: int = 0
        
        # Message handlers
        self.message_handlers: Dict[MessageType, Callable] = {}
        
        # Receive buffer
        self._recv_buffer = b''
        
        # Threading
        self._lock = threading.Lock()
        self._recv_thread: Optional[threading.Thread] = None
        self._running = False
    
    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"
    
    def connect(self, timeout: int = config.CONNECTION_TIMEOUT) -> bool:
        """
        Connect to peer.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            True if connected successfully
        """
        if self.state != PeerState.DISCONNECTED:
            return False
        
        try:
            self.state = PeerState.CONNECTING
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            self.socket.connect((self.ip, self.port))
            
            self.state = PeerState.CONNECTED
            self.connected_at = int(time.time())
            self.last_seen = self.connected_at
            
            # Start receive thread
            self._running = True
            self._recv_thread = threading.Thread(target=self._receive_loop)
            self._recv_thread.daemon = True
            self._recv_thread.start()
            
            return True
            
        except Exception as e:
            print(f"Failed to connect to {self.address}: {e}")
            self.disconnect()
            return False
    
    def disconnect(self, reason: str = ""):
        """Disconnect from peer."""
        self._running = False
        self.state = PeerState.DISCONNECTING
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        self.state = PeerState.DISCONNECTED
        
        if reason:
            print(f"Disconnected from {self.address}: {reason}")
    
    def set_socket(self, sock: socket.socket):
        """Set socket for inbound connection."""
        self.socket = sock
        self.state = PeerState.CONNECTED
        self.connected_at = int(time.time())
        self.last_seen = self.connected_at
        
        # Start receive thread
        self._running = True
        self._recv_thread = threading.Thread(target=self._receive_loop)
        self._recv_thread.daemon = True
        self._recv_thread.start()
    
    def send_message(self, message: Message) -> bool:
        """
        Send a message to peer.
        
        Args:
            message: Message to send
            
        Returns:
            True if sent successfully
        """
        if self.state not in [PeerState.CONNECTED, PeerState.VERSION_SENT, PeerState.READY]:
            return False
        
        try:
            data = message.serialize()
            
            with self._lock:
                self.socket.sendall(data)
            
            self.bytes_sent += len(data)
            self.messages_sent += 1
            self.last_send = int(time.time())
            
            return True
            
        except Exception as e:
            print(f"Error sending to {self.address}: {e}")
            self.disconnect("Send error")
            return False
    
    def _receive_loop(self):
        """Background thread for receiving messages."""
        self.socket.settimeout(1.0)
        
        while self._running and self.state != PeerState.DISCONNECTED:
            try:
                data = self.socket.recv(8192)
                
                if not data:
                    self.disconnect("Connection closed")
                    break
                
                self._recv_buffer += data
                self.bytes_recv += len(data)
                self.last_recv = int(time.time())
                self.last_seen = self.last_recv
                
                # Process complete messages
                self._process_buffer()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    self.disconnect(f"Receive error: {e}")
                break
    
    def _process_buffer(self):
        """Process messages in receive buffer."""
        while len(self._recv_buffer) >= 24:  # Minimum message size
            # Check for valid message
            message = Message.deserialize(self._recv_buffer, self.magic)
            
            if message is None:
                # Not enough data or invalid message
                if len(self._recv_buffer) > 24:
                    # Check magic
                    if self._recv_buffer[:4] != self.magic:
                        # Invalid magic, try to find valid start
                        idx = self._recv_buffer.find(self.magic, 1)
                        if idx > 0:
                            self._recv_buffer = self._recv_buffer[idx:]
                        else:
                            self._recv_buffer = b''
                break
            
            # Calculate message size and remove from buffer
            payload_len = int.from_bytes(self._recv_buffer[16:20], 'little')
            msg_size = 24 + payload_len
            self._recv_buffer = self._recv_buffer[msg_size:]
            
            self.messages_recv += 1
            self._handle_message(message)
    
    def _handle_message(self, message: Message):
        """Handle received message."""
        msg_type = message.get_type()
        
        # Call registered handler if exists
        if msg_type in self.message_handlers:
            try:
                self.message_handlers[msg_type](self, message)
            except Exception as e:
                print(f"Error handling {msg_type}: {e}")
        
        # Built-in handling for some messages
        if msg_type == MessageType.VERSION:
            self._handle_version(message)
        elif msg_type == MessageType.VERACK:
            self._handle_verack(message)
        elif msg_type == MessageType.PING:
            self._handle_ping(message)
        elif msg_type == MessageType.PONG:
            self._handle_pong(message)
    
    def _handle_version(self, message: Message):
        """Handle VERSION message."""
        version_data = Protocol.parse_version_message(message.payload)
        
        if version_data:
            self.version = version_data['version']
            self.services = version_data['services']
            self.user_agent = version_data['user_agent']
            self.start_height = version_data['start_height']
            self.relay = version_data['relay']
            self.nonce = version_data['nonce']
            
            # Send VERACK
            self.send_message(Protocol.create_verack_message())
            
            if self.state == PeerState.CONNECTED:
                self.state = PeerState.VERSION_SENT
    
    def _handle_verack(self, message: Message):
        """Handle VERACK message."""
        if self.state == PeerState.VERSION_SENT:
            self.state = PeerState.READY
    
    def _handle_ping(self, message: Message):
        """Handle PING message."""
        if len(message.payload) >= 8:
            nonce = int.from_bytes(message.payload[:8], 'little')
            self.send_message(Protocol.create_pong_message(nonce))
    
    def _handle_pong(self, message: Message):
        """Handle PONG message."""
        if len(message.payload) >= 8:
            nonce = int.from_bytes(message.payload[:8], 'little')
            
            if nonce == self.ping_nonce:
                ping_time = int((time.time() * 1000) - self.ping_time)
                self.ping_wait = ping_time
                
                if self.min_ping == 0 or ping_time < self.min_ping:
                    self.min_ping = ping_time
    
    def send_ping(self):
        """Send PING message."""
        import random
        self.ping_nonce = random.randint(0, 2**64 - 1)
        self.ping_time = int(time.time() * 1000)
        self.send_message(Protocol.create_ping_message(self.ping_nonce))
    
    def send_version(self, start_height: int = 0):
        """Send VERSION message."""
        import random
        
        message = Protocol.create_version_message(
            addr_recv=self.ip,
            port_recv=self.port,
            start_height=start_height,
            nonce=random.randint(0, 2**64 - 1),
        )
        
        self.send_message(message)
        self.state = PeerState.VERSION_SENT
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """Register a message handler."""
        self.message_handlers[msg_type] = handler
    
    def add_ban_score(self, score: int, reason: str = ""):
        """Add to ban score."""
        self.ban_score += score
        
        if self.ban_score >= 100:
            self.state = PeerState.BANNED
            self.disconnect(f"Banned: {reason}")
    
    def is_ready(self) -> bool:
        """Check if peer is ready for normal communication."""
        return self.state == PeerState.READY
    
    def is_connected(self) -> bool:
        """Check if peer is connected."""
        return self.state in [PeerState.CONNECTED, PeerState.VERSION_SENT, PeerState.READY]
    
    def get_info(self) -> Dict[str, Any]:
        """Get peer information."""
        return {
            'address': self.address,
            'inbound': self.inbound,
            'state': self.state.name,
            'version': self.version,
            'user_agent': self.user_agent,
            'services': self.services,
            'start_height': self.start_height,
            'synced_headers': self.synced_headers,
            'synced_blocks': self.synced_blocks,
            'bytes_sent': self.bytes_sent,
            'bytes_recv': self.bytes_recv,
            'ping': self.ping_wait,
            'min_ping': self.min_ping,
            'connected_at': self.connected_at,
            'last_seen': self.last_seen,
        }


class PeerManager:
    """
    Manages all peer connections.
    
    Handles peer discovery, connection management, and message routing.
    """
    
    def __init__(
        self,
        max_connections: int = config.MAX_CONNECTIONS,
        max_outbound: int = 8,
        max_inbound: int = 117,
    ):
        """
        Initialize peer manager.
        
        Args:
            max_connections: Maximum total connections
            max_outbound: Maximum outbound connections
            max_inbound: Maximum inbound connections
        """
        self.max_connections = max_connections
        self.max_outbound = max_outbound
        self.max_inbound = max_inbound
        
        self.peers: Dict[str, Peer] = {}
        self.known_peers: Dict[str, PeerInfo] = {}
        self.banned_peers: Dict[str, int] = {}  # ip -> ban_until timestamp
        
        self._lock = threading.Lock()
    
    def add_peer(self, ip: str, port: int, inbound: bool = False) -> Optional[Peer]:
        """
        Add a new peer connection.
        
        Args:
            ip: Peer IP
            port: Peer port
            inbound: True if inbound connection
            
        Returns:
            Peer object or None if failed
        """
        address = f"{ip}:{port}"
        
        # Check if already connected
        if address in self.peers:
            return self.peers[address]
        
        # Check limits
        outbound_count = sum(1 for p in self.peers.values() if not p.inbound)
        inbound_count = sum(1 for p in self.peers.values() if p.inbound)
        
        if inbound and inbound_count >= self.max_inbound:
            return None
        
        if not inbound and outbound_count >= self.max_outbound:
            return None
        
        if len(self.peers) >= self.max_connections:
            return None
        
        # Check if banned
        if self.is_banned(ip):
            return None
        
        peer = Peer(ip, port, inbound)
        
        with self._lock:
            self.peers[address] = peer
        
        return peer
    
    def remove_peer(self, address: str):
        """Remove a peer."""
        with self._lock:
            peer = self.peers.pop(address, None)
            if peer:
                peer.disconnect()
    
    def get_peer(self, address: str) -> Optional[Peer]:
        """Get peer by address."""
        return self.peers.get(address)
    
    def get_peers(self) -> List[Peer]:
        """Get all connected peers."""
        return list(self.peers.values())
    
    def get_ready_peers(self) -> List[Peer]:
        """Get peers in ready state."""
        return [p for p in self.peers.values() if p.is_ready()]
    
    def add_known_peer(self, info: PeerInfo):
        """Add peer to known peers list."""
        address = info.address
        
        if address not in self.known_peers:
            self.known_peers[address] = info
        else:
            # Update timestamp if newer
            if info.timestamp > self.known_peers[address].timestamp:
                self.known_peers[address].timestamp = info.timestamp
    
    def get_known_peers(self, count: int = 100) -> List[PeerInfo]:
        """Get known peers for sharing."""
        peers = list(self.known_peers.values())
        
        # Sort by timestamp (most recent first)
        peers.sort(key=lambda p: p.timestamp, reverse=True)
        
        return peers[:count]
    
    def ban_peer(self, ip: str, duration: int = 86400):
        """
        Ban a peer.
        
        Args:
            ip: IP to ban
            duration: Ban duration in seconds
        """
        self.banned_peers[ip] = int(time.time()) + duration
        
        # Disconnect if connected
        to_remove = [addr for addr, peer in self.peers.items() if peer.ip == ip]
        for addr in to_remove:
            self.remove_peer(addr)
    
    def is_banned(self, ip: str) -> bool:
        """Check if IP is banned."""
        ban_until = self.banned_peers.get(ip, 0)
        if ban_until > int(time.time()):
            return True
        
        # Remove expired ban
        if ip in self.banned_peers:
            del self.banned_peers[ip]
        
        return False
    
    def broadcast(self, message: Message, exclude: List[str] = None):
        """
        Broadcast message to all ready peers.
        
        Args:
            message: Message to broadcast
            exclude: List of addresses to exclude
        """
        exclude = exclude or []
        
        for peer in self.get_ready_peers():
            if peer.address not in exclude:
                peer.send_message(message)
    
    def get_connection_count(self) -> Dict[str, int]:
        """Get connection counts."""
        outbound = sum(1 for p in self.peers.values() if not p.inbound and p.is_connected())
        inbound = sum(1 for p in self.peers.values() if p.inbound and p.is_connected())
        
        return {
            'total': len(self.peers),
            'outbound': outbound,
            'inbound': inbound,
        }
    
    def get_peer_info(self) -> List[Dict[str, Any]]:
        """Get info for all peers."""
        return [peer.get_info() for peer in self.peers.values()]
    
    def cleanup_disconnected(self):
        """Remove disconnected peers."""
        with self._lock:
            to_remove = [
                addr for addr, peer in self.peers.items()
                if peer.state == PeerState.DISCONNECTED
            ]
            
            for addr in to_remove:
                del self.peers[addr]
