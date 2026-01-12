"""
SALOCOIN Masternode Implementation
Masternode registration, validation, and management.
"""

import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

from core.crypto import (
    sha256d,
    sign_message,
    verify_signature,
    public_key_to_address,
)
from core.blockchain import Blockchain
from core.transaction import Transaction
import config


class MasternodeState(Enum):
    """Masternode states."""
    PRE_ENABLED = 0
    ENABLED = 1
    EXPIRED = 2
    WATCHDOG_EXPIRED = 3
    NEW_START_REQUIRED = 4
    UPDATE_REQUIRED = 5
    POSE_BAN = 6
    OUTPOINT_SPENT = 7


@dataclass
class MasternodeCollateral:
    """Masternode collateral transaction reference."""
    
    txid: str
    vout: int
    amount: int = config.MASTERNODE_COLLATERAL
    confirmations: int = 0
    
    def __str__(self) -> str:
        return f"{self.txid}-{self.vout}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'txid': self.txid,
            'vout': self.vout,
            'amount': self.amount,
            'confirmations': self.confirmations,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MasternodeCollateral':
        return cls(
            txid=data['txid'],
            vout=data['vout'],
            amount=data.get('amount', config.MASTERNODE_COLLATERAL),
            confirmations=data.get('confirmations', 0),
        )


@dataclass
class Masternode:
    """Represents a masternode."""
    
    # Identity
    collateral: MasternodeCollateral
    pubkey_operator: bytes
    pubkey_voting: bytes
    service_address: str  # IP:Port
    
    # Owner and payout
    owner_address: str
    payout_address: str
    
    # State
    state: MasternodeState = MasternodeState.PRE_ENABLED
    registered_height: int = 0
    last_paid_height: int = 0
    last_seen: int = 0
    protocol_version: int = config.PROTOCOL_VERSION
    
    # Proof of Service
    pose_score: int = 0
    pose_ban_score: int = 0
    pose_ban_height: int = 0
    
    # Signature
    signature: bytes = b''
    
    def __post_init__(self):
        if not self.last_seen:
            self.last_seen = int(time.time())
    
    @property
    def vin(self) -> str:
        """Get unique identifier from collateral."""
        return str(self.collateral)
    
    @property
    def ip(self) -> str:
        """Get IP address."""
        return self.service_address.split(':')[0]
    
    @property
    def port(self) -> int:
        """Get port."""
        parts = self.service_address.split(':')
        return int(parts[1]) if len(parts) > 1 else config.MASTERNODE_PORT
    
    def is_valid(self) -> bool:
        """Check if masternode is in valid state."""
        return self.state in [MasternodeState.ENABLED, MasternodeState.PRE_ENABLED]
    
    def is_enabled(self) -> bool:
        """Check if masternode is fully enabled."""
        return self.state == MasternodeState.ENABLED
    
    def check_expired(self, current_time: int = None) -> bool:
        """Check if masternode has expired."""
        if current_time is None:
            current_time = int(time.time())
        
        return (current_time - self.last_seen) > config.MASTERNODE_EXPIRATION_SECONDS
    
    def get_hash(self) -> bytes:
        """Get hash for signing."""
        data = (
            str(self.collateral).encode() +
            self.pubkey_operator +
            self.pubkey_voting +
            self.service_address.encode() +
            self.owner_address.encode() +
            self.payout_address.encode()
        )
        return sha256d(data)
    
    def sign(self, private_key: bytes) -> bytes:
        """Sign masternode announcement."""
        self.signature = sign_message(private_key, self.get_hash())
        return self.signature
    
    def verify_signature(self) -> bool:
        """Verify masternode signature."""
        if not self.signature:
            return False
        
        return verify_signature(
            self.pubkey_operator,
            self.get_hash(),
            self.signature
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'vin': self.vin,
            'collateral': self.collateral.to_dict(),
            'pubkey_operator': self.pubkey_operator.hex(),
            'pubkey_voting': self.pubkey_voting.hex(),
            'service_address': self.service_address,
            'owner_address': self.owner_address,
            'payout_address': self.payout_address,
            'state': self.state.name,
            'registered_height': self.registered_height,
            'last_paid_height': self.last_paid_height,
            'last_seen': self.last_seen,
            'protocol_version': self.protocol_version,
            'pose_score': self.pose_score,
            'signature': self.signature.hex(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Masternode':
        """Create from dictionary."""
        return cls(
            collateral=MasternodeCollateral.from_dict(data['collateral']),
            pubkey_operator=bytes.fromhex(data['pubkey_operator']),
            pubkey_voting=bytes.fromhex(data['pubkey_voting']),
            service_address=data['service_address'],
            owner_address=data['owner_address'],
            payout_address=data['payout_address'],
            state=MasternodeState[data.get('state', 'PRE_ENABLED')],
            registered_height=data.get('registered_height', 0),
            last_paid_height=data.get('last_paid_height', 0),
            last_seen=data.get('last_seen', 0),
            protocol_version=data.get('protocol_version', config.PROTOCOL_VERSION),
            pose_score=data.get('pose_score', 0),
            signature=bytes.fromhex(data.get('signature', '')),
        )


class MasternodeList:
    """Deterministic masternode list."""
    
    def __init__(self):
        self.masternodes: Dict[str, Masternode] = {}  # vin -> Masternode
        self.lock = Lock()
    
    def add(self, masternode: Masternode) -> bool:
        """Add masternode to list."""
        with self.lock:
            if masternode.vin in self.masternodes:
                return False
            
            self.masternodes[masternode.vin] = masternode
            return True
    
    def remove(self, vin: str) -> bool:
        """Remove masternode from list."""
        with self.lock:
            if vin in self.masternodes:
                del self.masternodes[vin]
                return True
            return False
    
    def get(self, vin: str) -> Optional[Masternode]:
        """Get masternode by vin."""
        return self.masternodes.get(vin)
    
    def get_by_address(self, address: str) -> Optional[Masternode]:
        """Get masternode by payout address."""
        for mn in self.masternodes.values():
            if mn.payout_address == address:
                return mn
        return None
    
    def get_by_ip(self, ip: str) -> Optional[Masternode]:
        """Get masternode by IP address."""
        for mn in self.masternodes.values():
            if mn.ip == ip:
                return mn
        return None
    
    def get_enabled_count(self) -> int:
        """Get count of enabled masternodes."""
        return sum(1 for mn in self.masternodes.values() if mn.is_enabled())
    
    def get_all(self) -> List[Masternode]:
        """Get all masternodes."""
        return list(self.masternodes.values())
    
    def get_enabled(self) -> List[Masternode]:
        """Get enabled masternodes."""
        return [mn for mn in self.masternodes.values() if mn.is_enabled()]
    
    def get_valid(self) -> List[Masternode]:
        """Get valid masternodes (enabled or pre-enabled)."""
        return [mn for mn in self.masternodes.values() if mn.is_valid()]
    
    def get_next_payment(self, block_height: int) -> Optional[Masternode]:
        """
        Get next masternode for payment (deterministic selection).
        
        Args:
            block_height: Current block height
            
        Returns:
            Masternode to be paid
        """
        enabled = self.get_enabled()
        if not enabled:
            return None
        
        # Sort by last paid height, then by collateral hash for determinism
        def sort_key(mn: Masternode) -> Tuple[int, str]:
            return (mn.last_paid_height, mn.vin)
        
        sorted_mns = sorted(enabled, key=sort_key)
        
        # Return the one that has been waiting longest
        return sorted_mns[0] if sorted_mns else None
    
    def get_quorum(self, block_hash: str, size: int = 10) -> List[Masternode]:
        """
        Get deterministic quorum of masternodes.
        
        Args:
            block_hash: Block hash for determinism
            size: Quorum size
            
        Returns:
            List of masternodes in quorum
        """
        enabled = self.get_enabled()
        if len(enabled) < size:
            return enabled
        
        # Score each masternode based on hash
        scored = []
        for mn in enabled:
            score_data = block_hash.encode() + mn.vin.encode()
            score = sha256d(score_data)
            scored.append((score, mn))
        
        # Sort by score and take top N
        scored.sort(key=lambda x: x[0])
        return [mn for _, mn in scored[:size]]
    
    def update_state(self, current_height: int):
        """Update masternode states based on current height."""
        current_time = int(time.time())
        
        with self.lock:
            for mn in self.masternodes.values():
                # Check expiration
                if mn.check_expired(current_time):
                    if mn.state == MasternodeState.ENABLED:
                        mn.state = MasternodeState.EXPIRED
                
                # Check watchdog expiration
                if mn.state == MasternodeState.PRE_ENABLED:
                    if (current_time - mn.last_seen) > 3600:  # 1 hour
                        mn.state = MasternodeState.WATCHDOG_EXPIRED
    
    def size(self) -> int:
        """Get total masternode count."""
        return len(self.masternodes)
    
    def to_dict(self) -> List[Dict[str, Any]]:
        """Convert to list of dictionaries."""
        return [mn.to_dict() for mn in self.masternodes.values()]
    
    def save(self, filepath: str):
        """Save masternode list to file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def load(self, filepath: str) -> bool:
        """Load masternode list from file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with self.lock:
                self.masternodes.clear()
                for mn_data in data:
                    mn = Masternode.from_dict(mn_data)
                    self.masternodes[mn.vin] = mn
            
            return True
        except Exception as e:
            print(f"Error loading masternode list: {e}")
            return False


class MasternodeManager:
    """Manages local masternode and interactions with the network."""
    
    def __init__(self, blockchain: Blockchain, masternode_list: MasternodeList = None):
        """
        Initialize masternode manager.
        
        Args:
            blockchain: Blockchain instance
            masternode_list: Optional existing masternode list
        """
        self.blockchain = blockchain
        self.list = masternode_list or MasternodeList()
        
        # Local masternode (if running as masternode)
        self.local_masternode: Optional[Masternode] = None
        self.private_key: Optional[bytes] = None
        
        self.running = False
        self.lock = Lock()
    
    def register_masternode(
        self,
        collateral_txid: str,
        collateral_vout: int,
        owner_address: str,
        payout_address: str,
        service_address: str,
        operator_pubkey: bytes,
        operator_privkey: bytes,
        voting_pubkey: bytes = None,
    ) -> Optional[Masternode]:
        """
        Register a new masternode.
        
        Args:
            collateral_txid: Collateral transaction ID
            collateral_vout: Collateral output index
            owner_address: Owner address
            payout_address: Payout address
            service_address: Service IP:Port
            operator_pubkey: Operator public key
            operator_privkey: Operator private key
            voting_pubkey: Voting public key (defaults to operator)
            
        Returns:
            Registered masternode or None if failed
        """
        # Verify collateral
        if not self._verify_collateral(collateral_txid, collateral_vout):
            print("Invalid collateral")
            return None
        
        collateral = MasternodeCollateral(
            txid=collateral_txid,
            vout=collateral_vout,
        )
        
        # Get confirmations
        tx_result = self.blockchain.get_transaction(collateral_txid)
        if tx_result and tx_result[1]:  # Has block
            collateral.confirmations = self.blockchain.get_height() - tx_result[1].height
        
        if collateral.confirmations < config.MASTERNODE_MIN_CONFIRMATIONS:
            print(f"Insufficient confirmations: {collateral.confirmations} < {config.MASTERNODE_MIN_CONFIRMATIONS}")
            return None
        
        # Create masternode
        masternode = Masternode(
            collateral=collateral,
            pubkey_operator=operator_pubkey,
            pubkey_voting=voting_pubkey or operator_pubkey,
            service_address=service_address,
            owner_address=owner_address,
            payout_address=payout_address,
            registered_height=self.blockchain.get_height(),
        )
        
        # Sign
        masternode.sign(operator_privkey)
        
        # Add to list
        if not self.list.add(masternode):
            print("Failed to add masternode to list")
            return None
        
        return masternode
    
    def _verify_collateral(self, txid: str, vout: int) -> bool:
        """Verify collateral transaction."""
        tx_result = self.blockchain.get_transaction(txid)
        if not tx_result:
            return False
        
        tx, block = tx_result
        
        if vout >= len(tx.outputs):
            return False
        
        output = tx.outputs[vout]
        
        # Check amount
        if output.value != config.MASTERNODE_COLLATERAL:
            return False
        
        return True
    
    def start_local(
        self,
        masternode_key: bytes,
        service_address: str,
    ):
        """
        Start local masternode.
        
        Args:
            masternode_key: Masternode private key
            service_address: Service address (IP:Port)
        """
        from core.crypto import private_key_to_public_key
        
        self.private_key = masternode_key
        pubkey = private_key_to_public_key(masternode_key)
        
        # Find our masternode by pubkey
        for mn in self.list.get_all():
            if mn.pubkey_operator == pubkey:
                self.local_masternode = mn
                break
        
        if not self.local_masternode:
            print("Local masternode not found in list")
            return
        
        # Update state
        self.local_masternode.state = MasternodeState.ENABLED
        self.local_masternode.last_seen = int(time.time())
        self.running = True
        
        print(f"Local masternode started: {self.local_masternode.vin}")
    
    def stop_local(self):
        """Stop local masternode."""
        if self.local_masternode:
            self.local_masternode.state = MasternodeState.EXPIRED
        
        self.running = False
        self.local_masternode = None
        self.private_key = None
    
    def ping(self) -> bool:
        """Send masternode ping to keep alive."""
        if not self.local_masternode or not self.private_key:
            return False
        
        self.local_masternode.last_seen = int(time.time())
        
        # Sign ping
        ping_data = (
            self.local_masternode.vin +
            str(self.local_masternode.last_seen)
        ).encode()
        
        ping_signature = sign_message(self.private_key, ping_data)
        
        # In full implementation, broadcast to network
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get masternode status."""
        if not self.local_masternode:
            return {'status': 'Not configured'}
        
        return {
            'status': self.local_masternode.state.name,
            'vin': self.local_masternode.vin,
            'service': self.local_masternode.service_address,
            'payout': self.local_masternode.payout_address,
            'last_seen': self.local_masternode.last_seen,
            'registered_height': self.local_masternode.registered_height,
            'last_paid_height': self.local_masternode.last_paid_height,
            'pose_score': self.local_masternode.pose_score,
        }
    
    def get_count(self) -> Dict[str, int]:
        """Get masternode counts by state."""
        counts = {
            'total': self.list.size(),
            'enabled': 0,
            'pre_enabled': 0,
            'expired': 0,
            'pose_banned': 0,
        }
        
        for mn in self.list.get_all():
            if mn.state == MasternodeState.ENABLED:
                counts['enabled'] += 1
            elif mn.state == MasternodeState.PRE_ENABLED:
                counts['pre_enabled'] += 1
            elif mn.state in [MasternodeState.EXPIRED, MasternodeState.WATCHDOG_EXPIRED]:
                counts['expired'] += 1
            elif mn.state == MasternodeState.POSE_BAN:
                counts['pose_banned'] += 1
        
        return counts
    
    def process_pose_check(self, mn_vin: str, success: bool):
        """
        Process Proof-of-Service check result.
        
        Args:
            mn_vin: Masternode identifier
            success: Whether check passed
        """
        mn = self.list.get(mn_vin)
        if not mn:
            return
        
        if success:
            # Decrease PoSe score on success
            mn.pose_score = max(0, mn.pose_score - 1)
        else:
            # Increase PoSe score on failure
            mn.pose_score += 1
            
            if mn.pose_score >= config.MASTERNODE_BAN_SCORE_THRESHOLD:
                mn.state = MasternodeState.POSE_BAN
                mn.pose_ban_height = self.blockchain.get_height()
    
    def check_collateral_spent(self):
        """Check if any masternode collaterals have been spent."""
        for mn in self.list.get_all():
            # Get UTXO for collateral
            utxos = self.blockchain.get_utxos(mn.owner_address)
            
            collateral_exists = False
            for utxo in utxos:
                if (utxo['txid'] == mn.collateral.txid and 
                    utxo['vout'] == mn.collateral.vout):
                    collateral_exists = True
                    break
            
            if not collateral_exists:
                mn.state = MasternodeState.OUTPOINT_SPENT
