"""
SALOCOIN InstantSend Implementation
Instant transaction confirmations via masternode quorums.
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from threading import Lock
from enum import Enum

from .masternode import MasternodeList, Masternode
from core.transaction import Transaction
from core.crypto import sha256d, sign_message, verify_signature
from core.blockchain import Blockchain
import config


class LockStatus(Enum):
    """InstantSend lock status."""
    NONE = 0
    PENDING = 1
    LOCKED = 2
    CONFIRMED = 3
    FAILED = 4


@dataclass
class InstantSendLock:
    """InstantSend transaction lock."""
    
    txid: str
    inputs: List[str]  # List of outpoints (txid:vout)
    cycleHash: str     # Quorum cycle hash
    signature: bytes   # Aggregated signature
    
    # Status
    status: LockStatus = LockStatus.PENDING
    created_at: int = 0
    locked_at: int = 0
    
    # Quorum info
    quorum_hash: str = ''
    signers: List[str] = field(default_factory=list)  # List of masternode vins
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = int(time.time())
    
    def is_locked(self) -> bool:
        """Check if transaction is locked."""
        return self.status == LockStatus.LOCKED
    
    def get_hash(self) -> bytes:
        """Get lock hash for signing."""
        data = (
            bytes.fromhex(self.txid) +
            '|'.join(self.inputs).encode() +
            bytes.fromhex(self.cycleHash)
        )
        return sha256d(data)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'txid': self.txid,
            'inputs': self.inputs,
            'cycleHash': self.cycleHash,
            'signature': self.signature.hex(),
            'status': self.status.name,
            'created_at': self.created_at,
            'locked_at': self.locked_at,
            'quorum_hash': self.quorum_hash,
            'signers': self.signers,
        }


@dataclass
class InputLockVote:
    """Vote to lock a transaction input."""
    
    txid: str
    outpoint: str
    voter_vin: str
    signature: bytes
    timestamp: int = 0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = int(time.time())
    
    def get_hash(self) -> bytes:
        """Get vote hash."""
        data = (
            bytes.fromhex(self.txid) +
            self.outpoint.encode() +
            self.voter_vin.encode()
        )
        return sha256d(data)


class InstantSend:
    """
    InstantSend implementation for instant transaction confirmations.
    
    Uses masternode quorums to lock transaction inputs,
    preventing double-spend attempts.
    """
    
    def __init__(self, blockchain: Blockchain, masternode_list: MasternodeList):
        """
        Initialize InstantSend.
        
        Args:
            blockchain: Blockchain instance
            masternode_list: Masternode list
        """
        self.blockchain = blockchain
        self.mnlist = masternode_list
        
        # Active locks
        self.locks: Dict[str, InstantSendLock] = {}  # txid -> lock
        
        # Input votes (txid -> outpoint -> votes)
        self.input_votes: Dict[str, Dict[str, List[InputLockVote]]] = {}
        
        # Locked inputs (to prevent double-spend)
        self.locked_inputs: Dict[str, str] = {}  # outpoint -> txid
        
        self.lock = Lock()
        self.enabled = True
    
    def request_lock(self, tx: Transaction) -> Optional[InstantSendLock]:
        """
        Request InstantSend lock for a transaction.
        
        Args:
            tx: Transaction to lock
            
        Returns:
            InstantSendLock or None if request failed
        """
        if not self.enabled:
            return None
        
        # Check transaction eligibility
        if not self._is_eligible(tx):
            return None
        
        # Check if already locked
        if tx.txid in self.locks:
            return self.locks[tx.txid]
        
        # Get input outpoints
        inputs = [f"{inp.txid}:{inp.vout}" for inp in tx.inputs]
        
        # Check if any input is already locked by another tx
        for outpoint in inputs:
            if outpoint in self.locked_inputs:
                existing_txid = self.locked_inputs[outpoint]
                if existing_txid != tx.txid:
                    print(f"Input {outpoint} already locked by {existing_txid}")
                    return None
        
        # Get current block hash for quorum selection
        cycle_hash = self.blockchain.get_latest_block().hash
        
        # Create lock request
        is_lock = InstantSendLock(
            txid=tx.txid,
            inputs=inputs,
            cycleHash=cycle_hash,
            signature=b'',
        )
        
        with self.lock:
            self.locks[tx.txid] = is_lock
            self.input_votes[tx.txid] = {inp: [] for inp in inputs}
        
        return is_lock
    
    def _is_eligible(self, tx: Transaction) -> bool:
        """Check if transaction is eligible for InstantSend."""
        # Cannot lock coinbase
        if tx.is_coinbase:
            return False
        
        # Check input count
        if len(tx.inputs) > 10:
            return False
        
        # Check total value
        total_value = tx.get_total_output_value()
        if total_value > config.INSTANTSEND_MAX_VALUE:
            return False
        
        # Check input confirmations
        for inp in tx.inputs:
            tx_result = self.blockchain.get_transaction(inp.txid)
            if tx_result:
                _, block = tx_result
                if block:
                    confirmations = self.blockchain.get_height() - block.height
                    if confirmations < 6:
                        return False
        
        return True
    
    def process_vote(self, vote: InputLockVote) -> bool:
        """
        Process an input lock vote from a masternode.
        
        Args:
            vote: Lock vote
            
        Returns:
            True if vote was accepted
        """
        # Verify voter is in quorum
        mn = self.mnlist.get(vote.voter_vin)
        if not mn or not mn.is_enabled():
            return False
        
        # Verify signature
        if not verify_signature(mn.pubkey_operator, vote.get_hash(), vote.signature):
            return False
        
        with self.lock:
            # Get lock
            is_lock = self.locks.get(vote.txid)
            if not is_lock:
                return False
            
            # Add vote
            if vote.outpoint not in self.input_votes[vote.txid]:
                return False
            
            # Check for duplicate vote
            for existing in self.input_votes[vote.txid][vote.outpoint]:
                if existing.voter_vin == vote.voter_vin:
                    return False
            
            self.input_votes[vote.txid][vote.outpoint].append(vote)
            
            # Check if we have enough votes
            self._check_lock_completion(vote.txid)
        
        return True
    
    def _check_lock_completion(self, txid: str):
        """Check if lock has enough votes to complete."""
        is_lock = self.locks.get(txid)
        if not is_lock or is_lock.status != LockStatus.PENDING:
            return
        
        required_votes = config.INSTANTSEND_QUORUM_SIZE
        
        # Check each input has enough votes
        for outpoint in is_lock.inputs:
            votes = self.input_votes[txid].get(outpoint, [])
            if len(votes) < required_votes:
                return
        
        # All inputs have enough votes - lock is complete
        is_lock.status = LockStatus.LOCKED
        is_lock.locked_at = int(time.time())
        
        # Collect signers
        all_signers = set()
        for outpoint in is_lock.inputs:
            for vote in self.input_votes[txid][outpoint]:
                all_signers.add(vote.voter_vin)
        
        is_lock.signers = list(all_signers)
        
        # Lock the inputs
        for outpoint in is_lock.inputs:
            self.locked_inputs[outpoint] = txid
        
        print(f"InstantSend: Transaction {txid[:16]}... locked with {len(all_signers)} signers")
    
    def get_lock(self, txid: str) -> Optional[InstantSendLock]:
        """Get lock for a transaction."""
        return self.locks.get(txid)
    
    def is_locked(self, txid: str) -> bool:
        """Check if transaction is locked."""
        lock = self.locks.get(txid)
        return lock is not None and lock.is_locked()
    
    def is_input_locked(self, outpoint: str) -> bool:
        """Check if an input is locked."""
        return outpoint in self.locked_inputs
    
    def get_locked_tx_for_input(self, outpoint: str) -> Optional[str]:
        """Get txid that has locked an input."""
        return self.locked_inputs.get(outpoint)
    
    def confirm_lock(self, txid: str):
        """
        Confirm lock after transaction is included in block.
        
        Args:
            txid: Transaction ID
        """
        lock = self.locks.get(txid)
        if lock:
            lock.status = LockStatus.CONFIRMED
    
    def cleanup_confirmed(self, confirmed_txids: List[str]):
        """Clean up locks for confirmed transactions."""
        with self.lock:
            for txid in confirmed_txids:
                lock = self.locks.pop(txid, None)
                if lock:
                    # Remove input locks
                    for outpoint in lock.inputs:
                        self.locked_inputs.pop(outpoint, None)
                
                self.input_votes.pop(txid, None)
    
    def cleanup_expired(self, max_age: int = 3600):
        """Remove expired lock requests."""
        current_time = int(time.time())
        
        with self.lock:
            expired = [
                txid for txid, lock in self.locks.items()
                if (lock.status == LockStatus.PENDING and 
                    current_time - lock.created_at > max_age)
            ]
            
            for txid in expired:
                lock = self.locks.pop(txid)
                lock.status = LockStatus.FAILED
                
                for outpoint in lock.inputs:
                    self.locked_inputs.pop(outpoint, None)
                
                self.input_votes.pop(txid, None)
    
    def get_quorum_for_tx(self, tx: Transaction) -> List[Masternode]:
        """
        Get masternode quorum for transaction locking.
        
        Args:
            tx: Transaction
            
        Returns:
            List of masternodes in quorum
        """
        block_hash = self.blockchain.get_latest_block().hash
        return self.mnlist.get_quorum(block_hash, config.INSTANTSEND_QUORUM_SIZE)
    
    def create_lock_vote(
        self,
        txid: str,
        outpoint: str,
        voter_vin: str,
        private_key: bytes,
    ) -> Optional[InputLockVote]:
        """
        Create a lock vote.
        
        Args:
            txid: Transaction ID
            outpoint: Input outpoint
            voter_vin: Voting masternode vin
            private_key: Masternode private key
            
        Returns:
            Signed vote or None
        """
        lock = self.locks.get(txid)
        if not lock or outpoint not in lock.inputs:
            return None
        
        vote = InputLockVote(
            txid=txid,
            outpoint=outpoint,
            voter_vin=voter_vin,
        )
        
        vote.signature = sign_message(private_key, vote.get_hash())
        
        return vote
    
    def get_status(self) -> Dict[str, Any]:
        """Get InstantSend status."""
        pending = sum(1 for l in self.locks.values() if l.status == LockStatus.PENDING)
        locked = sum(1 for l in self.locks.values() if l.status == LockStatus.LOCKED)
        
        return {
            'enabled': self.enabled,
            'pending_locks': pending,
            'active_locks': locked,
            'locked_inputs': len(self.locked_inputs),
            'quorum_size': config.INSTANTSEND_QUORUM_SIZE,
        }
