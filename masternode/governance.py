"""
SALOCOIN Governance System
Proposal creation, voting, and budget management.
"""

import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

from .masternode import MasternodeList, Masternode
from core.crypto import sha256d, sign_message, verify_signature
from core.blockchain import Blockchain
import config


class ProposalType(Enum):
    """Governance proposal types."""
    BUDGET = 1           # Treasury budget proposal
    DEVELOPMENT = 2      # Development funding
    MARKETING = 3        # Marketing funding
    INFRASTRUCTURE = 4   # Infrastructure funding
    PROTOCOL = 5         # Protocol changes
    COMMUNITY = 6        # Community initiatives


class VoteOutcome(Enum):
    """Vote outcomes."""
    YES = 1
    NO = 2
    ABSTAIN = 3


@dataclass
class Vote:
    """Governance vote."""
    
    proposal_hash: str
    voter_vin: str
    outcome: VoteOutcome
    timestamp: int
    signature: bytes = b''
    
    def get_hash(self) -> bytes:
        """Get vote hash for signing."""
        data = (
            self.proposal_hash.encode() +
            self.voter_vin.encode() +
            self.outcome.value.to_bytes(1, 'little') +
            self.timestamp.to_bytes(8, 'little')
        )
        return sha256d(data)
    
    def sign(self, private_key: bytes):
        """Sign the vote."""
        self.signature = sign_message(private_key, self.get_hash())
    
    def verify(self, public_key: bytes) -> bool:
        """Verify vote signature."""
        return verify_signature(public_key, self.get_hash(), self.signature)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'proposal_hash': self.proposal_hash,
            'voter_vin': self.voter_vin,
            'outcome': self.outcome.name,
            'timestamp': self.timestamp,
            'signature': self.signature.hex(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Vote':
        return cls(
            proposal_hash=data['proposal_hash'],
            voter_vin=data['voter_vin'],
            outcome=VoteOutcome[data['outcome']],
            timestamp=data['timestamp'],
            signature=bytes.fromhex(data.get('signature', '')),
        )


@dataclass
class Proposal:
    """Governance proposal."""
    
    name: str
    description: str
    proposal_type: ProposalType
    
    # Funding details
    payment_address: str
    payment_amount: int  # In satoshis
    
    # Proposer
    proposer_address: str
    
    # Fields with defaults must come after non-default fields
    payment_count: int = 1  # Number of superblocks
    
    # Timing
    start_epoch: int = 0  # When voting starts
    end_epoch: int = 0    # When voting ends
    
    # Status
    creation_time: int = 0
    fee_txid: str = ''  # Proposal fee transaction
    
    # Computed
    hash: str = ''
    
    # Votes
    votes: Dict[str, Vote] = field(default_factory=dict)  # voter_vin -> Vote
    
    def __post_init__(self):
        if not self.creation_time:
            self.creation_time = int(time.time())
        
        if not self.start_epoch:
            self.start_epoch = self.creation_time
        
        if not self.end_epoch:
            # Default voting period
            self.end_epoch = self.start_epoch + (config.GOVERNANCE_VOTING_PERIOD * config.BLOCK_TIME_TARGET)
        
        if not self.hash:
            self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """Calculate proposal hash."""
        data = (
            self.name.encode() +
            self.description[:500].encode() +
            self.proposal_type.value.to_bytes(1, 'little') +
            self.payment_address.encode() +
            self.payment_amount.to_bytes(8, 'little') +
            self.proposer_address.encode() +
            self.creation_time.to_bytes(8, 'little')
        )
        return sha256d(data).hex()
    
    def is_active(self) -> bool:
        """Check if proposal is in active voting period."""
        now = int(time.time())
        return self.start_epoch <= now <= self.end_epoch
    
    def is_expired(self) -> bool:
        """Check if proposal has expired."""
        return int(time.time()) > self.end_epoch
    
    def add_vote(self, vote: Vote) -> bool:
        """Add a vote to the proposal."""
        if vote.proposal_hash != self.hash:
            return False
        
        if vote.voter_vin in self.votes:
            # Update existing vote
            pass
        
        self.votes[vote.voter_vin] = vote
        return True
    
    def get_vote_counts(self) -> Dict[str, int]:
        """Get vote counts."""
        counts = {
            'yes': 0,
            'no': 0,
            'abstain': 0,
            'total': len(self.votes),
        }
        
        for vote in self.votes.values():
            if vote.outcome == VoteOutcome.YES:
                counts['yes'] += 1
            elif vote.outcome == VoteOutcome.NO:
                counts['no'] += 1
            else:
                counts['abstain'] += 1
        
        return counts
    
    def get_net_votes(self) -> int:
        """Get net yes votes (yes - no)."""
        counts = self.get_vote_counts()
        return counts['yes'] - counts['no']
    
    def is_passing(self, total_masternodes: int) -> bool:
        """Check if proposal is passing."""
        if total_masternodes == 0:
            return False
        
        min_votes = max(1, (total_masternodes * config.GOVERNANCE_MIN_VOTES_PERCENT) // 100)
        net_votes = self.get_net_votes()
        
        return net_votes >= min_votes
    
    def get_funding_status(self, total_masternodes: int) -> Dict[str, Any]:
        """Get comprehensive funding status."""
        counts = self.get_vote_counts()
        net_votes = self.get_net_votes()
        
        min_votes_required = max(1, (total_masternodes * config.GOVERNANCE_MIN_VOTES_PERCENT) // 100)
        
        return {
            'votes_yes': counts['yes'],
            'votes_no': counts['no'],
            'votes_abstain': counts['abstain'],
            'net_votes': net_votes,
            'min_required': min_votes_required,
            'is_passing': net_votes >= min_votes_required,
            'total_amount': self.payment_amount * self.payment_count,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hash': self.hash,
            'name': self.name,
            'description': self.description,
            'type': self.proposal_type.name,
            'payment_address': self.payment_address,
            'payment_amount': self.payment_amount,
            'payment_count': self.payment_count,
            'proposer_address': self.proposer_address,
            'start_epoch': self.start_epoch,
            'end_epoch': self.end_epoch,
            'creation_time': self.creation_time,
            'fee_txid': self.fee_txid,
            'votes': {k: v.to_dict() for k, v in self.votes.items()},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Proposal':
        proposal = cls(
            name=data['name'],
            description=data['description'],
            proposal_type=ProposalType[data['type']],
            payment_address=data['payment_address'],
            payment_amount=data['payment_amount'],
            payment_count=data.get('payment_count', 1),
            proposer_address=data['proposer_address'],
            start_epoch=data.get('start_epoch', 0),
            end_epoch=data.get('end_epoch', 0),
            creation_time=data.get('creation_time', 0),
            fee_txid=data.get('fee_txid', ''),
        )
        proposal.hash = data.get('hash', proposal.calculate_hash())
        
        # Load votes
        for vin, vote_data in data.get('votes', {}).items():
            proposal.votes[vin] = Vote.from_dict(vote_data)
        
        return proposal


class Governance:
    """
    Governance system for SALOCOIN.
    
    Manages proposals, voting, and treasury budget allocation.
    """
    
    def __init__(self, blockchain: Blockchain, masternode_list: MasternodeList):
        """
        Initialize governance.
        
        Args:
            blockchain: Blockchain instance
            masternode_list: Masternode list
        """
        self.blockchain = blockchain
        self.mnlist = masternode_list
        
        self.proposals: Dict[str, Proposal] = {}  # hash -> Proposal
        self.lock = Lock()
    
    def create_proposal(
        self,
        name: str,
        description: str,
        proposal_type: ProposalType,
        payment_address: str,
        payment_amount: int,
        proposer_address: str,
        payment_count: int = 1,
    ) -> Optional[Proposal]:
        """
        Create a new governance proposal.
        
        Args:
            name: Proposal name
            description: Proposal description
            proposal_type: Type of proposal
            payment_address: Address to receive funds
            payment_amount: Amount per payment
            proposer_address: Address of proposer
            payment_count: Number of payments
            
        Returns:
            Created proposal or None if failed
        """
        # Validate
        if len(name) < 3 or len(name) > 100:
            print("Invalid proposal name length")
            return None
        
        if len(description) < 10:
            print("Description too short")
            return None
        
        if payment_amount <= 0:
            print("Invalid payment amount")
            return None
        
        proposal = Proposal(
            name=name,
            description=description,
            proposal_type=proposal_type,
            payment_address=payment_address,
            payment_amount=payment_amount,
            payment_count=payment_count,
            proposer_address=proposer_address,
        )
        
        with self.lock:
            self.proposals[proposal.hash] = proposal
        
        return proposal
    
    def submit_proposal(self, proposal_hash: str, fee_txid: str) -> bool:
        """
        Submit proposal after paying fee.
        
        Args:
            proposal_hash: Proposal hash
            fee_txid: Fee transaction ID
            
        Returns:
            True if submission successful
        """
        proposal = self.proposals.get(proposal_hash)
        if not proposal:
            return False
        
        # Verify fee transaction
        tx_result = self.blockchain.get_transaction(fee_txid)
        if not tx_result:
            return False
        
        tx, _ = tx_result
        
        # Check fee amount (OP_RETURN output with proposal hash)
        fee_paid = False
        for output in tx.outputs:
            if output.value >= config.GOVERNANCE_PROPOSAL_FEE:
                fee_paid = True
                break
        
        if not fee_paid:
            return False
        
        proposal.fee_txid = fee_txid
        return True
    
    def vote(
        self,
        proposal_hash: str,
        voter_vin: str,
        outcome: VoteOutcome,
        private_key: bytes,
    ) -> Optional[Vote]:
        """
        Cast a vote on a proposal.
        
        Args:
            proposal_hash: Proposal to vote on
            voter_vin: Voting masternode identifier
            outcome: Vote outcome (YES/NO/ABSTAIN)
            private_key: Masternode private key for signing
            
        Returns:
            Vote object or None if failed
        """
        proposal = self.proposals.get(proposal_hash)
        if not proposal:
            print("Proposal not found")
            return None
        
        if not proposal.is_active():
            print("Proposal not in active voting period")
            return None
        
        # Verify voter is valid masternode
        mn = self.mnlist.get(voter_vin)
        if not mn or not mn.is_enabled():
            print("Invalid or disabled masternode")
            return None
        
        vote = Vote(
            proposal_hash=proposal_hash,
            voter_vin=voter_vin,
            outcome=outcome,
            timestamp=int(time.time()),
        )
        
        vote.sign(private_key)
        
        if proposal.add_vote(vote):
            return vote
        
        return None
    
    def get_proposal(self, proposal_hash: str) -> Optional[Proposal]:
        """Get proposal by hash."""
        return self.proposals.get(proposal_hash)
    
    def get_proposals(
        self,
        active_only: bool = False,
        passing_only: bool = False,
    ) -> List[Proposal]:
        """
        Get list of proposals.
        
        Args:
            active_only: Only return active proposals
            passing_only: Only return passing proposals
            
        Returns:
            List of proposals
        """
        proposals = list(self.proposals.values())
        
        if active_only:
            proposals = [p for p in proposals if p.is_active()]
        
        if passing_only:
            total_mn = self.mnlist.get_enabled_count()
            proposals = [p for p in proposals if p.is_passing(total_mn)]
        
        return proposals
    
    def get_superblock_proposals(self, superblock_height: int) -> List[Proposal]:
        """
        Get proposals to be paid in a superblock.
        
        Args:
            superblock_height: Superblock height
            
        Returns:
            List of passing proposals sorted by net votes
        """
        total_mn = self.mnlist.get_enabled_count()
        passing = [
            p for p in self.proposals.values()
            if p.is_passing(total_mn) and not p.is_expired()
        ]
        
        # Sort by net votes (highest first)
        passing.sort(key=lambda p: p.get_net_votes(), reverse=True)
        
        return passing
    
    def get_budget_status(self) -> Dict[str, Any]:
        """Get current budget status."""
        # Calculate available budget
        blocks_per_cycle = config.SUPERBLOCK_INTERVAL
        reward_per_block = config.calculate_block_reward(self.blockchain.get_height())
        treasury_per_block = (reward_per_block * config.TREASURY_REWARD_PERCENT) // 100
        
        available_budget = blocks_per_cycle * treasury_per_block
        
        # Calculate allocated budget
        total_mn = self.mnlist.get_enabled_count()
        passing = self.get_proposals(passing_only=True)
        
        allocated = sum(p.payment_amount for p in passing)
        
        return {
            'available': available_budget,
            'allocated': allocated,
            'remaining': available_budget - allocated,
            'proposal_count': len(passing),
            'next_superblock': self._get_next_superblock_height(),
        }
    
    def _get_next_superblock_height(self) -> int:
        """Get height of next superblock."""
        current = self.blockchain.get_height()
        interval = config.SUPERBLOCK_INTERVAL
        return ((current // interval) + 1) * interval
    
    def is_superblock(self, height: int) -> bool:
        """Check if height is a superblock."""
        return height % config.SUPERBLOCK_INTERVAL == 0
    
    def cleanup_expired(self):
        """Remove expired proposals."""
        with self.lock:
            expired = [
                h for h, p in self.proposals.items()
                if p.is_expired()
            ]
            
            for h in expired:
                del self.proposals[h]
    
    def save(self, filepath: str):
        """Save governance state to file."""
        data = {
            'proposals': {h: p.to_dict() for h, p in self.proposals.items()},
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self, filepath: str) -> bool:
        """Load governance state from file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with self.lock:
                self.proposals.clear()
                for h, p_data in data.get('proposals', {}).items():
                    self.proposals[h] = Proposal.from_dict(p_data)
            
            return True
        except Exception as e:
            print(f"Error loading governance: {e}")
            return False
    
    def get_governance_info(self) -> Dict[str, Any]:
        """Get governance information."""
        return {
            'enabled': True,
            'proposal_fee': config.GOVERNANCE_PROPOSAL_FEE,
            'voting_period': config.GOVERNANCE_VOTING_PERIOD,
            'superblock_interval': config.SUPERBLOCK_INTERVAL,
            'min_votes_percent': config.GOVERNANCE_MIN_VOTES_PERCENT,
            'active_proposals': len(self.get_proposals(active_only=True)),
            'total_proposals': len(self.proposals),
        }
