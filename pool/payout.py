"""
Payout Management for SALOCOIN Pool
Handles reward distribution and transaction creation.
"""

import time
import struct
import hashlib
import threading
import requests
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Import from parent
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import config
    COIN_UNIT = config.COIN_UNIT
except ImportError:
    COIN_UNIT = 100000000


@dataclass
class PendingPayout:
    """A pending payout to a miner."""
    address: str
    amount: int  # In satoshis
    shares: int
    created_at: float = field(default_factory=time.time)
    
    @property
    def amount_formatted(self) -> str:
        return f"{self.amount / COIN_UNIT:.8f} SALO"


class PayoutManager:
    """Manages pool payouts to miners."""
    
    STATS_FILE = 'data/pool_stats.json'
    
    def __init__(self, pool_address: str, pool_privkey: str, 
                 seed_url: str = "https://api.salocoin.org",
                 fee_percent: float = 1.0,
                 min_payout: int = COIN_UNIT):  # Min 1 SALO
        self.pool_address = pool_address
        self.pool_privkey = pool_privkey
        self.seed_url = seed_url
        self.fee_percent = fee_percent
        self.min_payout = min_payout
        
        self.pending_payouts: Dict[str, PendingPayout] = {}  # address -> payout
        self.completed_payouts: List[dict] = []
        self.lock = threading.RLock()
        
        # Stats (will be loaded from file)
        self.total_paid = 0
        self.total_fees = 0
        self.blocks_paid = 0
        
        # Load saved stats
        self._load_stats()
    
    def _load_stats(self):
        """Load saved stats from file."""
        try:
            if os.path.exists(self.STATS_FILE):
                with open(self.STATS_FILE, 'r') as f:
                    data = json.load(f)
                    self.total_paid = data.get('total_paid', 0)
                    self.total_fees = data.get('total_fees', 0)
                    self.blocks_paid = data.get('blocks_paid', 0)
                    self.completed_payouts = data.get('completed_payouts', [])[-100:]  # Keep last 100
                    
                    # Restore pending payouts
                    for p in data.get('pending_payouts', []):
                        self.pending_payouts[p['address']] = PendingPayout(
                            address=p['address'],
                            amount=p['amount'],
                            shares=p.get('shares', 0),
                            created_at=p.get('created_at', time.time())
                        )
                    
                    pending_total = sum(p.amount for p in self.pending_payouts.values())
                    logger.info(f"📊 Loaded pool stats: {self.total_paid / COIN_UNIT:.8f} SALO paid, {self.blocks_paid} blocks, {len(self.pending_payouts)} pending ({pending_total / COIN_UNIT:.8f} SALO)")
        except Exception as e:
            logger.warning(f"Could not load pool stats: {e}")
    
    def _save_stats(self):
        """Save stats to file for persistence."""
        try:
            os.makedirs(os.path.dirname(self.STATS_FILE), exist_ok=True)
            
            # Serialize pending payouts
            pending_list = [
                {
                    'address': p.address,
                    'amount': p.amount,
                    'shares': p.shares,
                    'created_at': p.created_at
                }
                for p in self.pending_payouts.values()
            ]
            
            with open(self.STATS_FILE, 'w') as f:
                json.dump({
                    'total_paid': self.total_paid,
                    'total_fees': self.total_fees,
                    'blocks_paid': self.blocks_paid,
                    'completed_payouts': self.completed_payouts[-100:],  # Keep last 100
                    'pending_payouts': pending_list,
                    'last_updated': time.time()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save pool stats: {e}")
    
    @property
    def fee_rate(self) -> float:
        """Fee as decimal (0.01 for 1%)."""
        return self.fee_percent / 100.0
    
    def calculate_payouts(self, block_reward: int, shares_by_address: Dict[str, int]) -> Dict[str, int]:
        """
        Calculate payouts for a block based on shares.
        
        Args:
            block_reward: Total block reward in satoshis
            shares_by_address: Dict of address -> share count
            
        Returns:
            Dict of address -> payout amount
        """
        if not shares_by_address:
            return {}
        
        # Calculate pool fee
        pool_fee = int(block_reward * self.fee_rate)
        miner_reward = block_reward - pool_fee
        
        # Calculate total shares
        total_shares = sum(shares_by_address.values())
        if total_shares == 0:
            return {}
        
        # Calculate individual payouts
        payouts = {}
        for address, shares in shares_by_address.items():
            share_pct = shares / total_shares
            payout = int(miner_reward * share_pct)
            if payout > 0:
                payouts[address] = payout
        
        logger.info(f"Calculated payouts: {len(payouts)} miners, "
                   f"total {miner_reward / COIN_UNIT:.8f} SALO, "
                   f"fee {pool_fee / COIN_UNIT:.8f} SALO")
        
        return payouts
    
    def add_pending_payout(self, address: str, amount: int, shares: int):
        """Add or update pending payout for an address."""
        with self.lock:
            if address in self.pending_payouts:
                self.pending_payouts[address].amount += amount
                self.pending_payouts[address].shares += shares
            else:
                self.pending_payouts[address] = PendingPayout(
                    address=address,
                    amount=amount,
                    shares=shares
                )
    
    def process_block_reward(self, block_reward: int, shares_by_address: Dict[str, int]):
        """Process a block reward and add to pending payouts."""
        payouts = self.calculate_payouts(block_reward, shares_by_address)
        
        with self.lock:
            for address, amount in payouts.items():
                shares = shares_by_address.get(address, 0)
                self.add_pending_payout(address, amount, shares)
                logger.info(f"Added pending: {address[:20]}... = {amount / COIN_UNIT:.8f} SALO")
            
            self.blocks_paid += 1
            self.total_fees += int(block_reward * self.fee_rate)
            self._save_stats()  # Persist after each block
    
    def send_payouts(self) -> List[Tuple[str, int, bool, str]]:
        """
        Send all pending payouts that meet minimum threshold.
        Processes oldest payouts first (FIFO) to be fair.
        Supports partial payouts when mature balance is limited.
        
        Returns:
            List of (address, amount, success, txid_or_error)
        """
        results = []
        
        # Get current mature balance first
        try:
            resp = requests.get(f"{self.seed_url}/utxos/{self.pool_address}", timeout=10)
            if resp.status_code != 200:
                logger.error("Failed to get UTXOs for payout check")
                return results
            
            utxos = resp.json().get('utxos', [])
            mature_utxos = [u for u in utxos if u.get('mature', False) or not u.get('is_coinbase', False)]
            available_balance = sum(u['value'] for u in mature_utxos)
            
            if available_balance < self.min_payout:
                logger.info(f"⏳ Waiting for mature balance: have {available_balance / COIN_UNIT:.2f} SALO, need at least {self.min_payout / COIN_UNIT:.2f} SALO")
                return results
        except Exception as e:
            logger.error(f"Failed to check mature balance: {e}")
            return results
        
        with self.lock:
            payouts_to_send = [
                (addr, p) for addr, p in self.pending_payouts.items()
                if p.amount >= self.min_payout
            ]
            # Sort by creation time (oldest first) - FIFO ordering
            payouts_to_send.sort(key=lambda x: x[1].created_at)
        
        for address, payout in payouts_to_send:
            # Check if we have enough for full payout
            if available_balance >= payout.amount:
                # Full payout
                payout_amount = payout.amount
            elif available_balance >= self.min_payout:
                # Partial payout - pay what we can
                payout_amount = available_balance
                logger.info(f"📦 Partial payout: {payout_amount / COIN_UNIT:.2f} of {payout.amount / COIN_UNIT:.2f} SALO to {address[:20]}...")
            else:
                # Not enough for even minimum payout
                logger.info(f"⏳ Insufficient balance for {address[:20]}...: have {available_balance / COIN_UNIT:.2f}, need {self.min_payout / COIN_UNIT:.2f} SALO")
                break
            
            success, result = self._send_single_payout(address, payout_amount)
            
            if success:
                with self.lock:
                    self.total_paid += payout_amount
                    
                    if payout_amount >= payout.amount:
                        # Full payout - remove from pending
                        del self.pending_payouts[address]
                    else:
                        # Partial payout - reduce pending amount
                        self.pending_payouts[address].amount -= payout_amount
                        logger.info(f"📝 Remaining pending for {address[:20]}...: {self.pending_payouts[address].amount / COIN_UNIT:.2f} SALO")
                    
                    self.completed_payouts.append({
                        'address': address,
                        'amount': payout_amount,
                        'txid': result,
                        'timestamp': time.time(),
                        'partial': payout_amount < payout.amount
                    })
                    self._save_stats()  # Persist after each successful payout
                    
                # Update available balance
                available_balance -= payout_amount
                logger.info(f"✅ Sent {payout_amount / COIN_UNIT:.8f} SALO to {address[:20]}...")
            else:
                logger.error(f"❌ Failed payout to {address[:20]}...: {result}")
            
            results.append((address, payout_amount, success, result))
            
            # Stop if we're out of balance
            if available_balance < self.min_payout:
                break
        
        return results
    
    def _send_single_payout(self, address: str, amount: int) -> Tuple[bool, str]:
        """Send a single payout transaction."""
        try:
            # Get UTXOs (fresh fetch to avoid stale data)
            resp = requests.get(f"{self.seed_url}/utxos/{self.pool_address}", timeout=10)
            if resp.status_code != 200:
                return False, "Failed to get UTXOs"
            
            utxos = resp.json().get('utxos', [])
            if not utxos:
                return False, "No UTXOs available"
            
            # Create and sign transaction (only uses mature UTXOs)
            tx = self._create_transaction(address, amount, utxos)
            if not tx:
                return False, "Failed to create transaction"
            
            # Debug: log transaction details
            logger.debug(f"Transaction created: {tx.get('txid', 'unknown')[:16]}... with {len(tx.get('inputs', []))} inputs")
            
            # Submit transaction
            resp = requests.post(
                f"{self.seed_url}/submit_tx",
                json={'transaction': tx},
                timeout=10
            )
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get('success') or result.get('txid'):
                    return True, result.get('txid', 'submitted')
                return False, result.get('error', 'Unknown error')
            
            # Log detailed error for debugging
            try:
                error_json = resp.json()
                error_detail = error_json.get('error', resp.text[:500])
                # Try to get more specific error info
                logger.error(f"Full rejection response: {error_json}")
            except:
                error_detail = resp.text[:500]
            logger.error(f"Transaction rejected: HTTP {resp.status_code} - {error_detail}")
            return False, f"HTTP {resp.status_code}: {error_detail}"
            
        except Exception as e:
            return False, str(e)
    
    def _get_network_fee(self, priority: str = 'normal') -> int:
        """
        Get dynamic network fee from seed server.
        
        Args:
            priority: 'fast', 'normal', or 'economy'
            
        Returns:
            Fee in satoshis for a typical transaction (~200 bytes)
        """
        try:
            resp = requests.get(
                f"{self.seed_url}/fee_estimate/{priority}",
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                # estimated_fee is already in satoshis, use it directly
                fee_satoshis = int(data.get('estimated_fee', 250))
                # Ensure minimum fee
                fee_satoshis = max(fee_satoshis, 10000)  # Min 0.0001 SALO
                logger.debug(f"Dynamic fee ({priority}): {fee_satoshis} satoshis")
                return fee_satoshis
        except Exception as e:
            logger.warning(f"Failed to get network fee: {e}, using default")
        
        # Fallback to default fee
        return 10000  # 0.0001 SALO
    
    def _create_transaction(self, to_address: str, amount: int, utxos: list) -> Optional[dict]:
        """Create a signed transaction. Network fee is deducted from payout (Bitcoin-style)."""
        try:
            from core.transaction import Transaction
            from core.crypto import private_key_to_public_key, wif_to_private_key
            
            # Auto-detect hex vs WIF private key
            if len(self.pool_privkey) == 64 and all(c in '0123456789abcdefABCDEF' for c in self.pool_privkey):
                # Hex format - convert directly to bytes
                privkey_bytes = bytes.fromhex(self.pool_privkey)
                compressed = True
            else:
                # WIF format - decode
                privkey_bytes, compressed = wif_to_private_key(self.pool_privkey)
            
            pubkey = private_key_to_public_key(privkey_bytes, compressed)
            
            # Get dynamic fee from network (use normal priority for pool payouts)
            fee = self._get_network_fee()
            
            # Bitcoin-style: deduct fee from miner's payout
            payout_after_fee = amount - fee
            if payout_after_fee <= 0:
                logger.error(f"Payout {amount} too small after fee {fee}")
                return None
            
            needed = amount  # We need the original amount from UTXOs
            selected = []
            total = 0
            
            # Only use mature UTXOs (100+ confirmations for coinbase)
            for utxo in utxos:
                # Skip immature coinbase outputs
                if utxo.get('is_coinbase', False) and not utxo.get('mature', False):
                    continue
                selected.append(utxo)
                total += utxo['value']
                if total >= needed:
                    break
            
            if total < needed:
                logger.error(f"Insufficient funds: have {total}, need {needed}")
                return None
            
            # Calculate change - fee goes back to pool as change
            change = total - payout_after_fee - fee
            
            # Build inputs in correct format for create_transaction
            inputs = [{
                'txid': u['txid'],
                'vout': u['vout'],
                'value': u['value'],
                'prev_script': u.get('script', ''),
            } for u in selected]
            
            # Build outputs - miner gets payout minus fee
            outputs = [{'address': to_address, 'value': payout_after_fee}]
            
            logger.info(f"Payout: {amount / COIN_UNIT:.8f} - {fee / COIN_UNIT:.8f} fee = {payout_after_fee / COIN_UNIT:.8f} SALO to {to_address[:20]}...")
            
            # Create transaction using proper factory method
            change_addr = self.pool_address if change > 0 else None
            tx = Transaction.create_transaction(inputs, outputs, change_addr)
            
            # Sign all inputs
            for i in range(len(tx.inputs)):
                tx.sign_input(i, privkey_bytes, pubkey)
            
            # Recalculate txid after signing
            tx.txid = tx.calculate_hash()
            
            return tx.to_dict()
            
        except Exception as e:
            logger.error(f"Error creating transaction: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_pending_payouts(self) -> list:
        """Get list of pending payouts."""
        with self.lock:
            return [
                {
                    'address': addr,
                    'amount': p.amount,
                    'amount_formatted': p.amount_formatted,
                    'shares': p.shares,
                    'pending_since': p.created_at
                }
                for addr, p in self.pending_payouts.items()
            ]
    
    def get_stats(self) -> dict:
        """Get payout statistics."""
        with self.lock:
            return {
                'total_paid': self.total_paid,
                'total_paid_formatted': f"{self.total_paid / COIN_UNIT:.8f} SALO",
                'total_fees': self.total_fees,
                'total_fees_formatted': f"{self.total_fees / COIN_UNIT:.8f} SALO",
                'blocks_paid': self.blocks_paid,
                'pending_count': len(self.pending_payouts),
                'pending_amount': sum(p.amount for p in self.pending_payouts.values()),
                'recent_payouts': self.completed_payouts[-10:]  # Last 10
            }
