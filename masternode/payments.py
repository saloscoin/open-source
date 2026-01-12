"""
SALOCOIN Masternode Payments
Handles masternode payment selection and verification.
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .masternode import MasternodeList, Masternode, MasternodeState
from core.blockchain import Blockchain, Block
from core.transaction import Transaction, TxOutput
from core.crypto import sha256d
import config


@dataclass
class PaymentVote:
    """Masternode payment vote."""
    
    voter_vin: str          # Voting masternode identifier
    payee: str              # Proposed payee address
    block_height: int       # Block height this vote is for
    signature: bytes        # Vote signature
    timestamp: int = 0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = int(time.time())
    
    def get_hash(self) -> bytes:
        """Get vote hash."""
        data = (
            self.voter_vin.encode() +
            self.payee.encode() +
            str(self.block_height).to_bytes(4, 'little')
        )
        return sha256d(data)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'voter_vin': self.voter_vin,
            'payee': self.payee,
            'block_height': self.block_height,
            'timestamp': self.timestamp,
            'signature': self.signature.hex(),
        }


class MasternodePayments:
    """
    Manages masternode payment selection and verification.
    
    Implements deterministic masternode payment selection based on:
    1. Last payment height
    2. Registration order
    3. Block hash for additional randomness
    """
    
    def __init__(self, blockchain: Blockchain, masternode_list: MasternodeList):
        """
        Initialize masternode payments.
        
        Args:
            blockchain: Blockchain instance
            masternode_list: Masternode list
        """
        self.blockchain = blockchain
        self.mnlist = masternode_list
        
        # Payment votes
        self.votes: Dict[int, List[PaymentVote]] = {}  # height -> votes
        
        # Payment history
        self.payment_history: Dict[int, str] = {}  # height -> payee address
    
    def get_next_payee(self, block_height: int) -> Optional[str]:
        """
        Get the next masternode to be paid.
        
        Uses deterministic selection based on:
        1. Enabled masternodes only
        2. Sorted by last payment height (ascending)
        3. Then by collateral txid for determinism
        
        Args:
            block_height: Block height
            
        Returns:
            Payout address or None
        """
        enabled = self.mnlist.get_enabled()
        if not enabled:
            return None
        
        # Filter out recently paid
        min_blocks_between_payments = max(1, len(enabled) // 10)
        
        eligible = [
            mn for mn in enabled
            if block_height - mn.last_paid_height > min_blocks_between_payments
        ]
        
        if not eligible:
            eligible = enabled  # Fallback to all enabled
        
        # Sort by last payment height, then by vin for determinism
        sorted_mns = sorted(
            eligible,
            key=lambda mn: (mn.last_paid_height, mn.vin)
        )
        
        if sorted_mns:
            return sorted_mns[0].payout_address
        
        return None
    
    def get_next_payment(self, block_height: int) -> Dict[str, Any]:
        """
        Get the next masternode payment info for a block.
        
        Args:
            block_height: Block height
            
        Returns:
            Payment info dict with payee address and amount
        """
        payee = self.get_next_payee(block_height)
        amounts = self.calculate_payment_amounts(block_height)
        
        if payee:
            return {
                'payee': payee,
                'amount': amounts.get('masternode', 0),
                'height': block_height,
            }
        return {}
    
    def get_next_payee_with_quorum(self, block_height: int) -> Optional[str]:
        """
        Get next payee using quorum-based selection.
        
        Args:
            block_height: Block height
            
        Returns:
            Payee address based on quorum votes
        """
        # Check if we have votes for this height
        if block_height in self.votes:
            votes = self.votes[block_height]
            
            # Count votes per payee
            vote_counts: Dict[str, int] = {}
            for vote in votes:
                vote_counts[vote.payee] = vote_counts.get(vote.payee, 0) + 1
            
            # Get winner (most votes)
            if vote_counts:
                winner = max(vote_counts.keys(), key=lambda p: vote_counts[p])
                required_votes = self.mnlist.get_enabled_count() // 10 + 1
                
                if vote_counts[winner] >= required_votes:
                    return winner
        
        # Fallback to deterministic selection
        return self.get_next_payee(block_height)
    
    def calculate_payment_amounts(self, block_height: int) -> Dict[str, int]:
        """
        Calculate reward distribution for a block.
        
        Args:
            block_height: Block height
            
        Returns:
            Dictionary with miner, masternode, and treasury amounts
        """
        return config.calculate_reward_distribution(block_height)
    
    def verify_block_payment(self, block: Block) -> bool:
        """
        Verify that block contains correct masternode payment.
        
        Args:
            block: Block to verify
            
        Returns:
            True if payment is valid
        """
        if not block.transactions:
            return False
        
        # Get coinbase transaction
        coinbase = Transaction.from_dict(block.transactions[0])
        if not coinbase.is_coinbase:
            return False
        
        # Get expected payments
        expected = self.calculate_payment_amounts(block.height)
        expected_payee = self.get_next_payee(block.height)
        
        if not expected_payee:
            # No masternodes, miner gets full reward
            return True
        
        # Find masternode payment output
        mn_payment_found = False
        for output in coinbase.outputs:
            if output.address == expected_payee:
                if output.value >= expected['masternode']:
                    mn_payment_found = True
                    break
        
        return mn_payment_found
    
    def create_coinbase_payments(
        self,
        block_height: int,
        miner_address: str,
        treasury_address: str = None,
    ) -> List[TxOutput]:
        """
        Create coinbase outputs with proper payment distribution.
        
        Args:
            block_height: Block height
            miner_address: Miner's payout address
            treasury_address: Treasury address (optional)
            
        Returns:
            List of transaction outputs
        """
        from core.transaction import Transaction
        
        amounts = self.calculate_payment_amounts(block_height)
        outputs = []
        
        # Miner output
        miner_output = Transaction._create_p2pkh_output(
            miner_address,
            amounts['miner']
        )
        outputs.append(miner_output)
        
        # Masternode output
        mn_payee = self.get_next_payee(block_height)
        if mn_payee:
            mn_output = Transaction._create_p2pkh_output(
                mn_payee,
                amounts['masternode']
            )
            outputs.append(mn_output)
            
            # Update last paid height
            mn = self.mnlist.get_by_address(mn_payee)
            if mn:
                mn.last_paid_height = block_height
        
        # Treasury output
        if treasury_address:
            treasury_output = Transaction._create_p2pkh_output(
                treasury_address,
                amounts['treasury']
            )
            outputs.append(treasury_output)
        
        return outputs
    
    def add_vote(self, vote: PaymentVote) -> bool:
        """
        Add a payment vote.
        
        Args:
            vote: Payment vote
            
        Returns:
            True if vote was accepted
        """
        # Verify voter is valid masternode
        mn = self.mnlist.get(vote.voter_vin)
        if not mn or not mn.is_enabled():
            return False
        
        # Verify vote is for future block
        current_height = self.blockchain.get_height()
        if vote.block_height <= current_height:
            return False
        
        # Store vote
        if vote.block_height not in self.votes:
            self.votes[vote.block_height] = []
        
        # Check for duplicate
        for existing in self.votes[vote.block_height]:
            if existing.voter_vin == vote.voter_vin:
                return False
        
        self.votes[vote.block_height].append(vote)
        return True
    
    def cleanup_old_votes(self):
        """Remove votes for blocks that have already passed."""
        current_height = self.blockchain.get_height()
        
        old_heights = [h for h in self.votes.keys() if h <= current_height - 10]
        for height in old_heights:
            del self.votes[height]
    
    def record_payment(self, block_height: int, payee: str):
        """Record a payment in history."""
        self.payment_history[block_height] = payee
    
    def get_payment_history(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get recent payment history."""
        heights = sorted(self.payment_history.keys(), reverse=True)[:count]
        
        history = []
        for height in heights:
            payee = self.payment_history[height]
            mn = self.mnlist.get_by_address(payee)
            
            history.append({
                'height': height,
                'payee': payee,
                'masternode': mn.vin if mn else None,
            })
        
        return history
    
    def get_masternode_earnings(self, mn_vin: str) -> Dict[str, Any]:
        """Get earnings statistics for a masternode."""
        mn = self.mnlist.get(mn_vin)
        if not mn:
            return {}
        
        # Count payments in history
        payment_count = sum(
            1 for payee in self.payment_history.values()
            if payee == mn.payout_address
        )
        
        # Estimate earnings
        avg_reward = config.calculate_block_reward(self.blockchain.get_height())
        mn_share = (avg_reward * config.MASTERNODE_REWARD_PERCENT) // 100
        
        return {
            'total_payments': payment_count,
            'estimated_earnings': payment_count * mn_share,
            'last_paid_height': mn.last_paid_height,
            'next_payment_estimate': self._estimate_next_payment(mn),
        }
    
    def _estimate_next_payment(self, mn: Masternode) -> int:
        """Estimate blocks until next payment."""
        enabled_count = self.mnlist.get_enabled_count()
        if enabled_count == 0:
            return 0
        
        current_height = self.blockchain.get_height()
        blocks_since_payment = current_height - mn.last_paid_height
        
        return max(0, enabled_count - blocks_since_payment)
