"""
SALOCOIN P2P Protocol
Message types and serialization for network communication.
"""

import struct
import hashlib
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

import config


class MessageType(Enum):
    """P2P message types."""
    
    # Control messages
    VERSION = b'version'
    VERACK = b'verack'
    PING = b'ping'
    PONG = b'pong'
    REJECT = b'reject'
    
    # Address messages
    ADDR = b'addr'
    GETADDR = b'getaddr'
    
    # Inventory messages
    INV = b'inv'
    GETDATA = b'getdata'
    NOTFOUND = b'notfound'
    
    # Block messages
    GETBLOCKS = b'getblocks'
    GETHEADERS = b'getheaders'
    HEADERS = b'headers'
    BLOCK = b'block'
    
    # Transaction messages
    TX = b'tx'
    MEMPOOL = b'mempool'
    
    # Masternode messages
    MNANNOUNCE = b'mnannounce'
    MNPING = b'mnping'
    MNWINNER = b'mnwinner'
    MNLIST = b'mnlist'
    MNLISTSYNC = b'mnlistsync'
    
    # Governance messages
    GOVOBJ = b'govobj'
    GOVOBJVOTE = b'govobjvote'
    GOVOBJSYNC = b'govobjsync'
    
    # InstantSend messages
    ISLOCK = b'islock'
    ISDLOCK = b'isdlock'
    
    # PrivateSend messages
    DSACCEPT = b'dsaccept'
    DSQUEUE = b'dsqueue'
    DSSIGNFINAL = b'dssignfinal'
    
    # Spork messages
    SPORK = b'spork'
    GETSPORKS = b'getsporks'


class InvType(Enum):
    """Inventory item types."""
    ERROR = 0
    TX = 1
    BLOCK = 2
    FILTERED_BLOCK = 3
    MASTERNODE_ANNOUNCE = 4
    MASTERNODE_PING = 5
    GOVERNANCE_OBJECT = 6
    GOVERNANCE_VOTE = 7
    INSTANTSEND_LOCK = 8


@dataclass
class Message:
    """P2P Network message."""
    
    command: bytes
    payload: bytes = b''
    magic: bytes = config.MAINNET_MAGIC
    
    def serialize(self) -> bytes:
        """Serialize message for transmission."""
        # Magic (4 bytes)
        data = self.magic
        
        # Command (12 bytes, null-padded)
        command = self.command[:12].ljust(12, b'\x00')
        data += command
        
        # Payload length (4 bytes)
        data += struct.pack('<I', len(self.payload))
        
        # Checksum (4 bytes) - first 4 bytes of double SHA256
        checksum = hashlib.sha256(hashlib.sha256(self.payload).digest()).digest()[:4]
        data += checksum
        
        # Payload
        data += self.payload
        
        return data
    
    @classmethod
    def deserialize(cls, data: bytes, magic: bytes = config.MAINNET_MAGIC) -> Optional['Message']:
        """
        Deserialize message from bytes.
        
        Args:
            data: Raw message data
            magic: Expected magic bytes
            
        Returns:
            Message or None if invalid
        """
        if len(data) < 24:
            return None
        
        # Magic
        msg_magic = data[:4]
        if msg_magic != magic:
            return None
        
        # Command
        command = data[4:16].rstrip(b'\x00')
        
        # Payload length
        payload_len = struct.unpack('<I', data[16:20])[0]
        
        # Checksum
        checksum = data[20:24]
        
        # Payload
        if len(data) < 24 + payload_len:
            return None
        
        payload = data[24:24 + payload_len]
        
        # Verify checksum
        expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        if checksum != expected:
            return None
        
        return cls(command=command, payload=payload, magic=magic)
    
    def get_type(self) -> Optional[MessageType]:
        """Get message type enum."""
        for msg_type in MessageType:
            if msg_type.value == self.command:
                return msg_type
        return None


class Protocol:
    """P2P Protocol implementation."""
    
    @staticmethod
    def create_version_message(
        version: int = config.PROTOCOL_VERSION,
        services: int = 1,
        timestamp: int = None,
        addr_recv: str = "0.0.0.0",
        port_recv: int = config.P2P_PORT,
        addr_from: str = "0.0.0.0",
        port_from: int = config.P2P_PORT,
        nonce: int = None,
        user_agent: str = config.USER_AGENT,
        start_height: int = 0,
        relay: bool = True,
    ) -> Message:
        """
        Create VERSION message.
        
        This is the first message sent when connecting to a peer.
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        if nonce is None:
            import random
            nonce = random.randint(0, 2**64 - 1)
        
        payload = struct.pack('<I', version)           # Protocol version
        payload += struct.pack('<Q', services)          # Services
        payload += struct.pack('<Q', timestamp)         # Timestamp
        
        # Address of receiver
        payload += struct.pack('<Q', services)          # Services
        payload += Protocol._encode_ip(addr_recv)       # IP
        payload += struct.pack('>H', port_recv)         # Port (big-endian)
        
        # Address of sender
        payload += struct.pack('<Q', services)          # Services
        payload += Protocol._encode_ip(addr_from)       # IP
        payload += struct.pack('>H', port_from)         # Port (big-endian)
        
        payload += struct.pack('<Q', nonce)             # Nonce
        
        # User agent
        ua_bytes = user_agent.encode()
        payload += Protocol._varint(len(ua_bytes))
        payload += ua_bytes
        
        payload += struct.pack('<I', start_height)      # Start height
        payload += struct.pack('<?', relay)             # Relay flag
        
        return Message(command=MessageType.VERSION.value, payload=payload)
    
    @staticmethod
    def parse_version_message(payload: bytes) -> Optional[Dict[str, Any]]:
        """Parse VERSION message payload."""
        if len(payload) < 85:
            return None
        
        try:
            offset = 0
            
            version = struct.unpack('<I', payload[offset:offset+4])[0]
            offset += 4
            
            services = struct.unpack('<Q', payload[offset:offset+8])[0]
            offset += 8
            
            timestamp = struct.unpack('<Q', payload[offset:offset+8])[0]
            offset += 8
            
            # Skip receiver address (26 bytes)
            offset += 26
            
            # Skip sender address (26 bytes)
            offset += 26
            
            nonce = struct.unpack('<Q', payload[offset:offset+8])[0]
            offset += 8
            
            # User agent (variable length)
            ua_len, varint_size = Protocol._read_varint(payload[offset:])
            offset += varint_size
            user_agent = payload[offset:offset+ua_len].decode('utf-8', errors='ignore')
            offset += ua_len
            
            start_height = struct.unpack('<I', payload[offset:offset+4])[0]
            offset += 4
            
            relay = True
            if offset < len(payload):
                relay = struct.unpack('<?', payload[offset:offset+1])[0]
            
            return {
                'version': version,
                'services': services,
                'timestamp': timestamp,
                'nonce': nonce,
                'user_agent': user_agent,
                'start_height': start_height,
                'relay': relay,
            }
            
        except Exception:
            return None
    
    @staticmethod
    def create_verack_message() -> Message:
        """Create VERACK message."""
        return Message(command=MessageType.VERACK.value, payload=b'')
    
    @staticmethod
    def create_ping_message(nonce: int = None) -> Message:
        """Create PING message."""
        if nonce is None:
            import random
            nonce = random.randint(0, 2**64 - 1)
        
        payload = struct.pack('<Q', nonce)
        return Message(command=MessageType.PING.value, payload=payload)
    
    @staticmethod
    def create_pong_message(nonce: int) -> Message:
        """Create PONG message in response to PING."""
        payload = struct.pack('<Q', nonce)
        return Message(command=MessageType.PONG.value, payload=payload)
    
    @staticmethod
    def create_getaddr_message() -> Message:
        """Create GETADDR message to request peer addresses."""
        return Message(command=MessageType.GETADDR.value, payload=b'')
    
    @staticmethod
    def create_addr_message(addresses: List[Dict[str, Any]]) -> Message:
        """
        Create ADDR message with peer addresses.
        
        Args:
            addresses: List of address dicts with ip, port, services, timestamp
        """
        payload = Protocol._varint(len(addresses))
        
        for addr in addresses:
            payload += struct.pack('<I', addr.get('timestamp', int(time.time())))
            payload += struct.pack('<Q', addr.get('services', 1))
            payload += Protocol._encode_ip(addr['ip'])
            payload += struct.pack('>H', addr['port'])
        
        return Message(command=MessageType.ADDR.value, payload=payload)
    
    @staticmethod
    def create_inv_message(inventory: List[Dict[str, Any]]) -> Message:
        """
        Create INV message announcing inventory items.
        
        Args:
            inventory: List of {type: InvType, hash: str} dicts
        """
        payload = Protocol._varint(len(inventory))
        
        for item in inventory:
            inv_type = item['type'].value if isinstance(item['type'], InvType) else item['type']
            payload += struct.pack('<I', inv_type)
            payload += bytes.fromhex(item['hash'])[::-1]  # Reversed hash
        
        return Message(command=MessageType.INV.value, payload=payload)
    
    @staticmethod
    def create_getdata_message(inventory: List[Dict[str, Any]]) -> Message:
        """Create GETDATA message requesting specific items."""
        payload = Protocol._varint(len(inventory))
        
        for item in inventory:
            inv_type = item['type'].value if isinstance(item['type'], InvType) else item['type']
            payload += struct.pack('<I', inv_type)
            payload += bytes.fromhex(item['hash'])[::-1]
        
        return Message(command=MessageType.GETDATA.value, payload=payload)
    
    @staticmethod
    def create_block_message(block_data: bytes) -> Message:
        """Create BLOCK message with serialized block."""
        return Message(command=MessageType.BLOCK.value, payload=block_data)
    
    @staticmethod
    def create_tx_message(tx_data: bytes) -> Message:
        """Create TX message with serialized transaction."""
        return Message(command=MessageType.TX.value, payload=tx_data)
    
    @staticmethod
    def create_getblocks_message(
        block_locator: List[str],
        hash_stop: str = '0' * 64,
    ) -> Message:
        """Create GETBLOCKS message."""
        payload = struct.pack('<I', config.PROTOCOL_VERSION)
        payload += Protocol._varint(len(block_locator))
        
        for block_hash in block_locator:
            payload += bytes.fromhex(block_hash)[::-1]
        
        payload += bytes.fromhex(hash_stop)[::-1]
        
        return Message(command=MessageType.GETBLOCKS.value, payload=payload)
    
    @staticmethod
    def create_getheaders_message(
        block_locator: List[str],
        hash_stop: str = '0' * 64,
    ) -> Message:
        """Create GETHEADERS message."""
        payload = struct.pack('<I', config.PROTOCOL_VERSION)
        payload += Protocol._varint(len(block_locator))
        
        for block_hash in block_locator:
            payload += bytes.fromhex(block_hash)[::-1]
        
        payload += bytes.fromhex(hash_stop)[::-1]
        
        return Message(command=MessageType.GETHEADERS.value, payload=payload)
    
    @staticmethod
    def create_headers_message(headers: List[bytes]) -> Message:
        """Create HEADERS message with block headers."""
        payload = Protocol._varint(len(headers))
        
        for header in headers:
            payload += header
            payload += b'\x00'  # Transaction count (always 0 for headers)
        
        return Message(command=MessageType.HEADERS.value, payload=payload)
    
    @staticmethod
    def create_mempool_message() -> Message:
        """Create MEMPOOL message to request mempool contents."""
        return Message(command=MessageType.MEMPOOL.value, payload=b'')
    
    @staticmethod
    def create_reject_message(
        message: str,
        ccode: int,
        reason: str,
        data: bytes = b'',
    ) -> Message:
        """Create REJECT message."""
        msg_bytes = message.encode()
        reason_bytes = reason.encode()
        
        payload = Protocol._varint(len(msg_bytes))
        payload += msg_bytes
        payload += struct.pack('B', ccode)
        payload += Protocol._varint(len(reason_bytes))
        payload += reason_bytes
        payload += data
        
        return Message(command=MessageType.REJECT.value, payload=payload)
    
    # Masternode messages
    
    @staticmethod
    def create_mnannounce_message(masternode_data: bytes) -> Message:
        """Create masternode announcement message."""
        return Message(command=MessageType.MNANNOUNCE.value, payload=masternode_data)
    
    @staticmethod
    def create_mnping_message(ping_data: bytes) -> Message:
        """Create masternode ping message."""
        return Message(command=MessageType.MNPING.value, payload=ping_data)
    
    @staticmethod
    def create_getsporks_message() -> Message:
        """Create GETSPORKS message."""
        return Message(command=MessageType.GETSPORKS.value, payload=b'')
    
    @staticmethod
    def create_spork_message(spork_data: bytes) -> Message:
        """Create SPORK message."""
        return Message(command=MessageType.SPORK.value, payload=spork_data)
    
    # Helper methods
    
    @staticmethod
    def _encode_ip(ip: str) -> bytes:
        """Encode IP address to 16 bytes (IPv6 format)."""
        parts = ip.split('.')
        if len(parts) == 4:
            # IPv4 - encode as IPv4-mapped IPv6
            return b'\x00' * 10 + b'\xff\xff' + bytes(int(p) for p in parts)
        else:
            # IPv6 - parse properly
            return b'\x00' * 16  # Placeholder
    
    @staticmethod
    def _decode_ip(data: bytes) -> str:
        """Decode 16 bytes to IP address string."""
        if data[:12] == b'\x00' * 10 + b'\xff\xff':
            # IPv4-mapped IPv6
            return '.'.join(str(b) for b in data[12:16])
        else:
            # IPv6
            return ':'.join(format(int.from_bytes(data[i:i+2], 'big'), 'x')
                          for i in range(0, 16, 2))
    
    @staticmethod
    def _varint(n: int) -> bytes:
        """Encode integer as Bitcoin-style varint."""
        if n < 0xfd:
            return bytes([n])
        elif n <= 0xffff:
            return b'\xfd' + struct.pack('<H', n)
        elif n <= 0xffffffff:
            return b'\xfe' + struct.pack('<I', n)
        else:
            return b'\xff' + struct.pack('<Q', n)
    
    @staticmethod
    def _read_varint(data: bytes) -> tuple:
        """Read varint from bytes, return (value, bytes_consumed)."""
        if not data:
            return 0, 0
        
        first = data[0]
        
        if first < 0xfd:
            return first, 1
        elif first == 0xfd:
            return struct.unpack('<H', data[1:3])[0], 3
        elif first == 0xfe:
            return struct.unpack('<I', data[1:5])[0], 5
        else:
            return struct.unpack('<Q', data[1:9])[0], 9
