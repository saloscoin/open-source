"""
SALOCOIN Spork System
Network-wide feature activation controlled by masternodes.
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from threading import Lock

from core.crypto import sha256d, sign_message, verify_signature
import config


@dataclass
class Spork:
    """Network spork (feature flag)."""
    
    spork_id: int
    value: int
    timestamp: int
    signature: bytes = b''
    
    def is_active(self) -> bool:
        """Check if spork is active."""
        if self.value == 0:
            return True  # 0 means enabled
        
        if self.value > 0 and self.value < int(time.time()):
            return True  # Activated after timestamp
        
        return False
    
    def get_hash(self) -> bytes:
        """Get spork hash for signing."""
        data = (
            self.spork_id.to_bytes(4, 'little') +
            self.value.to_bytes(8, 'little') +
            self.timestamp.to_bytes(8, 'little')
        )
        return sha256d(data)
    
    def sign(self, private_key: bytes):
        """Sign the spork."""
        self.signature = sign_message(private_key, self.get_hash())
    
    def verify(self, public_key: bytes) -> bool:
        """Verify spork signature."""
        return verify_signature(public_key, self.get_hash(), self.signature)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.spork_id,
            'value': self.value,
            'timestamp': self.timestamp,
            'active': self.is_active(),
        }


class SporkManager:
    """
    Manages network sporks for feature activation.
    
    Sporks allow network-wide feature activation/deactivation
    without requiring software updates.
    """
    
    # Spork definitions
    SPORK_NAMES = {
        config.SPORK_INSTANTSEND_ENABLED: "INSTANTSEND_ENABLED",
        config.SPORK_INSTANTSEND_BLOCK_FILTERING: "INSTANTSEND_BLOCK_FILTERING",
        config.SPORK_MASTERNODE_PAYMENT_ENFORCEMENT: "MASTERNODE_PAYMENT_ENFORCEMENT",
        config.SPORK_RECONSIDER_BLOCKS: "RECONSIDER_BLOCKS",
        config.SPORK_GOVERNANCE_ENABLED: "GOVERNANCE_ENABLED",
        config.SPORK_PRIVATESEND_ENABLED: "PRIVATESEND_ENABLED",
    }
    
    def __init__(self, spork_pubkey: bytes = None):
        """
        Initialize spork manager.
        
        Args:
            spork_pubkey: Public key for verifying spork signatures
        """
        self.sporks: Dict[int, Spork] = {}
        self.spork_pubkey = spork_pubkey
        self.lock = Lock()
        
        # Initialize with defaults
        self._init_defaults()
    
    def _init_defaults(self):
        """Initialize sporks with default values."""
        for spork_id, default_value in config.SPORK_DEFAULTS.items():
            self.sporks[spork_id] = Spork(
                spork_id=spork_id,
                value=default_value,
                timestamp=int(time.time()),
            )
    
    def get_spork(self, spork_id: int) -> Optional[Spork]:
        """Get spork by ID."""
        return self.sporks.get(spork_id)
    
    def get_spork_value(self, spork_id: int) -> int:
        """Get spork value."""
        spork = self.sporks.get(spork_id)
        if spork:
            return spork.value
        return config.SPORK_DEFAULTS.get(spork_id, 0)
    
    def is_spork_active(self, spork_id: int) -> bool:
        """Check if spork is active."""
        spork = self.sporks.get(spork_id)
        if spork:
            return spork.is_active()
        
        # Default behavior
        default = config.SPORK_DEFAULTS.get(spork_id)
        if default == 0:
            return True
        return False
    
    def update_spork(self, spork: Spork) -> bool:
        """
        Update a spork value.
        
        Args:
            spork: New spork data
            
        Returns:
            True if update was accepted
        """
        # Verify signature if we have the public key
        if self.spork_pubkey:
            if not spork.verify(self.spork_pubkey):
                print(f"Invalid spork signature for {spork.spork_id}")
                return False
        
        # Check if this is newer than existing
        existing = self.sporks.get(spork.spork_id)
        if existing and existing.timestamp >= spork.timestamp:
            return False
        
        with self.lock:
            self.sporks[spork.spork_id] = spork
        
        name = self.SPORK_NAMES.get(spork.spork_id, f"UNKNOWN_{spork.spork_id}")
        print(f"Spork updated: {name} = {spork.value}")
        
        return True
    
    def set_spork(
        self,
        spork_id: int,
        value: int,
        private_key: bytes,
    ) -> Optional[Spork]:
        """
        Set a spork value (admin only).
        
        Args:
            spork_id: Spork to set
            value: New value
            private_key: Admin private key
            
        Returns:
            Signed spork or None if failed
        """
        spork = Spork(
            spork_id=spork_id,
            value=value,
            timestamp=int(time.time()),
        )
        
        spork.sign(private_key)
        
        if self.update_spork(spork):
            return spork
        
        return None
    
    # Convenience methods for checking specific sporks
    
    def is_instantsend_enabled(self) -> bool:
        """Check if InstantSend is enabled."""
        return self.is_spork_active(config.SPORK_INSTANTSEND_ENABLED)
    
    def is_instantsend_block_filtering_enabled(self) -> bool:
        """Check if InstantSend block filtering is enabled."""
        return self.is_spork_active(config.SPORK_INSTANTSEND_BLOCK_FILTERING)
    
    def is_masternode_payment_enforcement_enabled(self) -> bool:
        """Check if masternode payment enforcement is enabled."""
        return self.is_spork_active(config.SPORK_MASTERNODE_PAYMENT_ENFORCEMENT)
    
    def is_governance_enabled(self) -> bool:
        """Check if governance is enabled."""
        return self.is_spork_active(config.SPORK_GOVERNANCE_ENABLED)
    
    def is_privatesend_enabled(self) -> bool:
        """Check if PrivateSend is enabled."""
        return self.is_spork_active(config.SPORK_PRIVATESEND_ENABLED)
    
    def get_reconsider_blocks(self) -> int:
        """Get number of blocks to reconsider."""
        return self.get_spork_value(config.SPORK_RECONSIDER_BLOCKS)
    
    def get_all_sporks(self) -> List[Dict[str, Any]]:
        """Get all sporks as list."""
        result = []
        
        for spork_id in sorted(self.SPORK_NAMES.keys()):
            spork = self.sporks.get(spork_id)
            
            info = {
                'id': spork_id,
                'name': self.SPORK_NAMES[spork_id],
                'value': spork.value if spork else config.SPORK_DEFAULTS.get(spork_id, 0),
                'active': self.is_spork_active(spork_id),
            }
            
            if spork:
                info['timestamp'] = spork.timestamp
            
            result.append(info)
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            spork_id: spork.to_dict()
            for spork_id, spork in self.sporks.items()
        }
