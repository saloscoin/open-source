"""
SALOCOIN Transaction Implementation
Handles transaction creation, signing, and validation.
"""

import time
import struct
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
import json

from .crypto import (
    sha256d,
    sign_message,
    verify_signature,
    base58check_decode,
    public_key_to_address,
)
import config


@dataclass
class TxInput:
    """Transaction Input - references a previous output."""
    
    txid: str               # Previous transaction hash
    vout: int               # Output index in previous transaction
    script_sig: bytes = b'' # Unlocking script (signature)
    sequence: int = 0xffffffff
    
    # For signing (not serialized)
    prev_output: Optional['TxOutput'] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'txid': self.txid,
            'vout': self.vout,
            'scriptSig': self.script_sig.hex(),
            'sequence': self.sequence,
        }
        # Include address/value if prev_output is set (wallet-style)
        if self.prev_output:
            result['address'] = self.prev_output.address
            result['value'] = self.prev_output.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TxInput':
        """Create from dictionary."""
        inp = cls(
            txid=data.get('txid', '0' * 64),
            vout=data.get('vout', 0),
            script_sig=bytes.fromhex(data.get('scriptSig', data.get('script_sig', ''))),
            sequence=data.get('sequence', 0xffffffff),
        )
        # Store address/value for wallet-style transactions
        if 'address' in data:
            inp.prev_output = TxOutput(
                value=data.get('value', 0),
                script_pubkey=b'',
                address=data.get('address', '')
            )
        return inp
    
    def serialize(self) -> bytes:
        """Serialize input for hashing."""
        data = bytes.fromhex(self.txid)[::-1]  # Reverse txid
        data += struct.pack('<I', self.vout)
        data += self._serialize_script(self.script_sig)
        data += struct.pack('<I', self.sequence)
        return data
    
    @staticmethod
    def _serialize_script(script: bytes) -> bytes:
        """Serialize script with varint length prefix."""
        length = len(script)
        if length < 0xfd:
            return bytes([length]) + script
        elif length <= 0xffff:
            return b'\xfd' + struct.pack('<H', length) + script
        elif length <= 0xffffffff:
            return b'\xfe' + struct.pack('<I', length) + script
        else:
            return b'\xff' + struct.pack('<Q', length) + script
    
    def is_coinbase(self) -> bool:
        """Check if this is a coinbase input."""
        return self.txid == '0' * 64 and self.vout == 0xffffffff


@dataclass
class TxOutput:
    """Transaction Output - defines how coins can be spent."""
    
    value: int              # Amount in satoshis
    script_pubkey: bytes    # Locking script
    
    # Convenience fields (not serialized)
    address: str = ''
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'value': self.value,
            'scriptPubKey': self.script_pubkey.hex(),
            'address': self.address,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TxOutput':
        """Create from dictionary."""
        return cls(
            value=data.get('value', 0),
            script_pubkey=bytes.fromhex(data.get('scriptPubKey', data.get('script_pubkey', ''))),
            address=data.get('address', ''),
        )
    
    def serialize(self) -> bytes:
        """Serialize output for hashing."""
        data = struct.pack('<Q', self.value)
        data += TxInput._serialize_script(self.script_pubkey)
        return data


@dataclass
class Transaction:
    """SALOCOIN Transaction."""
    
    version: int = 1
    inputs: List[TxInput] = field(default_factory=list)
    outputs: List[TxOutput] = field(default_factory=list)
    locktime: int = 0
    
    # Computed fields
    txid: str = ''
    size: int = 0
    fee: int = 0
    
    # Transaction type flags
    is_coinbase: bool = False
    is_instantsend: bool = False
    is_privatesend: bool = False
    
    # Timestamps
    timestamp: int = 0
    
    def __post_init__(self):
        """Calculate txid after initialization."""
        if not self.txid:
            self.txid = self.calculate_hash()
        if not self.timestamp:
            self.timestamp = int(time.time())
    
    def calculate_hash(self) -> str:
        """Calculate transaction hash (txid)."""
        return sha256d(self.serialize()).hex()
    
    def serialize(self) -> bytes:
        """
        Serialize transaction for hashing.
        Uses Bitcoin-style serialization.
        """
        data = struct.pack('<I', self.version)
        
        # Input count (varint)
        data += self._varint(len(self.inputs))
        
        # Inputs
        for inp in self.inputs:
            data += inp.serialize()
        
        # Output count (varint)
        data += self._varint(len(self.outputs))
        
        # Outputs
        for out in self.outputs:
            data += out.serialize()
        
        # Locktime
        data += struct.pack('<I', self.locktime)
        
        return data
    
    @staticmethod
    def _varint(n: int) -> bytes:
        """Encode integer as Bitcoin varint."""
        if n < 0xfd:
            return bytes([n])
        elif n <= 0xffff:
            return b'\xfd' + struct.pack('<H', n)
        elif n <= 0xffffffff:
            return b'\xfe' + struct.pack('<I', n)
        else:
            return b'\xff' + struct.pack('<Q', n)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'txid': self.txid,
            'version': self.version,
            'inputs': [inp.to_dict() for inp in self.inputs],
            'outputs': [out.to_dict() for out in self.outputs],
            'locktime': self.locktime,
            'timestamp': self.timestamp,
            'size': len(self.serialize()),
            'fee': self.fee,
            'is_coinbase': self.is_coinbase,
            'is_instantsend': self.is_instantsend,
            'is_privatesend': self.is_privatesend,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Transaction':
        """Create from dictionary."""
        tx = cls(
            version=data.get('version', 1),
            inputs=[TxInput.from_dict(inp) for inp in data.get('inputs', [])],
            outputs=[TxOutput.from_dict(out) for out in data.get('outputs', [])],
            locktime=data.get('locktime', 0),
        )
        tx.txid = data.get('txid', tx.calculate_hash())
        tx.timestamp = data.get('timestamp', int(time.time()))
        tx.is_coinbase = data.get('is_coinbase', False)
        tx.is_instantsend = data.get('is_instantsend', False)
        tx.is_privatesend = data.get('is_privatesend', False)
        tx.fee = data.get('fee', 0)
        return tx
    
    def get_total_input_value(self) -> int:
        """Get total value of inputs (requires prev_output to be set)."""
        total = 0
        for inp in self.inputs:
            if inp.prev_output:
                total += inp.prev_output.value
        return total
    
    def get_total_output_value(self) -> int:
        """Get total value of outputs."""
        return sum(out.value for out in self.outputs)
    
    def calculate_fee(self) -> int:
        """Calculate transaction fee."""
        if self.is_coinbase:
            return 0
        return self.get_total_input_value() - self.get_total_output_value()
    
    def sign_input(self, input_index: int, private_key: bytes, public_key: bytes,
                   sighash_type: int = 1) -> bool:
        """
        Sign a transaction input.
        
        Args:
            input_index: Index of input to sign
            private_key: Private key for signing
            public_key: Corresponding public key
            sighash_type: Signature hash type (default SIGHASH_ALL)
            
        Returns:
            True if signing succeeded
        """
        if input_index >= len(self.inputs):
            return False
        
        # Create signing data
        signing_tx = self._create_signing_tx(input_index, sighash_type)
        signing_data = signing_tx + struct.pack('<I', sighash_type)
        
        # Sign
        signature = sign_message(private_key, signing_data)
        
        # Append sighash type to signature
        signature = signature + bytes([sighash_type])
        
        # Create scriptSig: <sig> <pubkey>
        script_sig = bytes([len(signature)]) + signature
        script_sig += bytes([len(public_key)]) + public_key
        
        self.inputs[input_index].script_sig = script_sig
        
        # Recalculate txid
        self.txid = self.calculate_hash()
        
        return True
    
    def _create_signing_tx(self, input_index: int, sighash_type: int) -> bytes:
        """Create transaction data for signing."""
        # Simplified signing (SIGHASH_ALL)
        data = struct.pack('<I', self.version)
        data += self._varint(len(self.inputs))
        
        for i, inp in enumerate(self.inputs):
            data += bytes.fromhex(inp.txid)[::-1]
            data += struct.pack('<I', inp.vout)
            
            if i == input_index:
                # Include the scriptPubKey of the output being spent
                if inp.prev_output:
                    script = inp.prev_output.script_pubkey
                else:
                    script = b''
                data += self._varint(len(script)) + script
            else:
                data += b'\x00'  # Empty script for other inputs
            
            data += struct.pack('<I', inp.sequence)
        
        data += self._varint(len(self.outputs))
        for out in self.outputs:
            data += out.serialize()
        
        data += struct.pack('<I', self.locktime)
        
        return data
    
    def verify_input(self, input_index: int) -> bool:
        """
        Verify signature of an input.
        
        Args:
            input_index: Index of input to verify
            
        Returns:
            True if signature is valid
        """
        if input_index >= len(self.inputs):
            return False
        
        inp = self.inputs[input_index]
        script_sig = inp.script_sig
        
        if len(script_sig) < 2:
            return False
        
        # Parse scriptSig: <sig_len> <sig> <pubkey_len> <pubkey>
        try:
            sig_len = script_sig[0]
            signature = script_sig[1:1 + sig_len]
            
            if 1 + sig_len >= len(script_sig):
                return False
            
            pubkey_len = script_sig[1 + sig_len]
            public_key = script_sig[2 + sig_len:2 + sig_len + pubkey_len]
            
            # Remove sighash type from signature
            sighash_type = signature[-1]
            signature = signature[:-1]
            
            # Create signing data
            signing_tx = self._create_signing_tx(input_index, sighash_type)
            signing_data = signing_tx + struct.pack('<I', sighash_type)
            
            return verify_signature(public_key, signing_data, signature)
            
        except Exception:
            return False
    
    def verify(self) -> bool:
        """Verify all input signatures."""
        if self.is_coinbase:
            return True
        
        for i in range(len(self.inputs)):
            if not self.verify_input(i):
                return False
        
        return True
    
    @classmethod
    def create_coinbase(cls, block_height: int, miner_address: str,
                        extra_data: str = "") -> 'Transaction':
        """
        Create a coinbase transaction.
        
        Args:
            block_height: Block height for this coinbase
            miner_address: Address to receive mining reward
            extra_data: Extra data to include in coinbase
            
        Returns:
            Coinbase transaction
        """
        # Get reward distribution
        rewards = config.calculate_reward_distribution(block_height)
        
        # Coinbase input
        coinbase_script = struct.pack('<I', block_height)
        coinbase_script += extra_data.encode()[:100]  # Limit extra data
        
        coinbase_input = TxInput(
            txid='0' * 64,
            vout=0xffffffff,
            script_sig=coinbase_script,
            sequence=0xffffffff,
        )
        
        outputs = []
        
        # Miner reward output
        miner_output = cls._create_p2pkh_output(miner_address, rewards['miner'])
        outputs.append(miner_output)
        
        # Note: Masternode and treasury outputs would be added by the masternode
        # payment system in a real implementation
        
        tx = cls(
            version=1,
            inputs=[coinbase_input],
            outputs=outputs,
            locktime=0,
        )
        tx.is_coinbase = True
        tx.txid = tx.calculate_hash()
        
        return tx
    
    @classmethod
    def _create_p2pkh_output(cls, address: str, value: int) -> TxOutput:
        """
        Create P2PKH (Pay-to-Public-Key-Hash) output.
        
        Args:
            address: Recipient address
            value: Amount in satoshis
            
        Returns:
            TxOutput with P2PKH script
        """
        try:
            version, pubkey_hash = base58check_decode(address)
        except Exception:
            pubkey_hash = b'\x00' * 20
        
        # P2PKH script: OP_DUP OP_HASH160 <pubkey_hash> OP_EQUALVERIFY OP_CHECKSIG
        script_pubkey = bytes([
            0x76,  # OP_DUP
            0xa9,  # OP_HASH160
            0x14,  # Push 20 bytes
        ]) + pubkey_hash + bytes([
            0x88,  # OP_EQUALVERIFY
            0xac,  # OP_CHECKSIG
        ])
        
        return TxOutput(
            value=value,
            script_pubkey=script_pubkey,
            address=address,
        )
    
    @classmethod
    def create_transaction(cls, inputs: List[Dict], outputs: List[Dict],
                          change_address: str = None) -> 'Transaction':
        """
        Create a regular transaction.
        
        Args:
            inputs: List of input dicts with txid, vout, value, prev_script
            outputs: List of output dicts with address, value
            change_address: Address for change output (optional)
            
        Returns:
            Unsigned transaction
        """
        tx_inputs = []
        total_in = 0
        
        for inp in inputs:
            tx_input = TxInput(
                txid=inp['txid'],
                vout=inp['vout'],
            )
            tx_input.prev_output = TxOutput(
                value=inp.get('value', 0),
                script_pubkey=bytes.fromhex(inp.get('prev_script', '')),
                address=inp.get('address', ''),
            )
            tx_inputs.append(tx_input)
            total_in += inp.get('value', 0)
        
        tx_outputs = []
        total_out = 0
        
        for out in outputs:
            tx_output = cls._create_p2pkh_output(out['address'], out['value'])
            tx_outputs.append(tx_output)
            total_out += out['value']
        
        # Calculate fee and change
        fee = total_in - total_out
        
        if fee < 0:
            raise ValueError("Insufficient input value")
        
        # Add change output if needed
        min_change = config.DEFAULT_TX_FEE
        if change_address and fee > min_change * 2:
            change_value = fee - min_change
            change_output = cls._create_p2pkh_output(change_address, change_value)
            tx_outputs.append(change_output)
            fee = min_change
        
        tx = cls(
            version=1,
            inputs=tx_inputs,
            outputs=tx_outputs,
        )
        tx.fee = fee
        tx.txid = tx.calculate_hash()
        
        return tx


class TransactionPool:
    """Memory pool for unconfirmed transactions."""
    
    # Default: No expiry (0 = forever)
    DEFAULT_TX_TTL = 0  # 0 means never expire
    
    def __init__(self, max_size: int = 300_000_000, tx_ttl: int = None, blockchain=None):  # 300 MB default
        self.transactions: Dict[str, Transaction] = {}
        self.tx_timestamps: Dict[str, float] = {}  # txid -> timestamp when added
        self.spent_outputs: set = set()  # Track outputs spent by mempool txs
        self.max_size = max_size
        self.current_size = 0
        self.tx_ttl = tx_ttl if tx_ttl is not None else self.DEFAULT_TX_TTL
        self.blockchain = blockchain  # Reference to blockchain for UTXO verification
    
    def set_blockchain(self, blockchain):
        """Set blockchain reference for UTXO validation."""
        self.blockchain = blockchain
    
    def add_transaction(self, tx: Transaction, timestamp: float = None, 
                       skip_verification: bool = False) -> bool:
        """
        Add transaction to mempool.
        
        Args:
            tx: Transaction to add
            timestamp: Optional timestamp (defaults to now)
            skip_verification: Skip signature verification (for loading from disk)
            
        Returns:
            True if added successfully
        """
        import time
        
        if tx.txid in self.transactions:
            return False
        
        if tx.is_coinbase:
            return False
        
        tx_size = len(tx.serialize())
        
        # Check size limits
        if self.current_size + tx_size > self.max_size:
            # Could implement eviction here
            return False
        
        # Verify transaction signature
        if not skip_verification and not tx.verify():
            print(f"Mempool: rejected tx {tx.txid[:16]}... - invalid signature")
            return False
        
        # Check for double-spend within mempool
        for inp in tx.inputs:
            outpoint = f"{inp.txid}:{inp.vout}"
            if outpoint in self.spent_outputs:
                print(f"Mempool: rejected tx {tx.txid[:16]}... - double-spend in mempool")
                return False
        
        # Verify inputs exist and are unspent (if blockchain is available)
        if self.blockchain and not skip_verification:
            for inp in tx.inputs:
                prev_tx_result = self.blockchain.get_transaction(inp.txid)
                if not prev_tx_result:
                    print(f"Mempool: rejected tx {tx.txid[:16]}... - input not found")
                    return False
                
                prev_tx, prev_block = prev_tx_result
                if prev_block is None:
                    # Input from another mempool tx - that's ok
                    continue
                
                if inp.vout >= len(prev_tx.outputs):
                    print(f"Mempool: rejected tx {tx.txid[:16]}... - invalid output index")
                    return False
                
                # Check coinbase maturity
                if prev_tx.is_coinbase:
                    current_height = len(self.blockchain.chain) - 1
                    confirmations = current_height - prev_block.height + 1
                    import sys
                    debug_msg = f"Mempool: coinbase check - chain_height={current_height}, prev_block_height={prev_block.height}, confirmations={confirmations}, txid={inp.txid[:16]}..."
                    print(debug_msg)
                    print(debug_msg, file=sys.stderr)
                    if confirmations < 100:  # COINBASE_MATURITY
                        reject_msg = f"Mempool: rejected tx {tx.txid[:16]}... - spending immature coinbase (need 100, have {confirmations})"
                        print(reject_msg)
                        print(reject_msg, file=sys.stderr)
                        return False
        
        # Track spent outputs
        for inp in tx.inputs:
            outpoint = f"{inp.txid}:{inp.vout}"
            self.spent_outputs.add(outpoint)
        
        self.transactions[tx.txid] = tx
        self.tx_timestamps[tx.txid] = timestamp if timestamp else time.time()
        self.current_size += tx_size
        
        return True
    
    def remove_transaction(self, txid: str) -> Optional[Transaction]:
        """Remove transaction from mempool and clean up spent outputs tracking."""
        tx = self.transactions.pop(txid, None)
        self.tx_timestamps.pop(txid, None)
        if tx:
            self.current_size -= len(tx.serialize())
            # Remove from spent_outputs tracking
            for inp in tx.inputs:
                outpoint = f"{inp.txid}:{inp.vout}"
                self.spent_outputs.discard(outpoint)
        return tx
    
    def prune_expired(self) -> int:
        """Remove expired transactions. Returns number of transactions removed."""
        # If TTL is 0, never expire transactions
        if self.tx_ttl == 0:
            return 0
        
        import time
        now = time.time()
        expired = []
        
        for txid, timestamp in self.tx_timestamps.items():
            if now - timestamp > self.tx_ttl:
                expired.append(txid)
        
        for txid in expired:
            self.remove_transaction(txid)
        
        return len(expired)
    
    def get_transaction(self, txid: str) -> Optional[Transaction]:
        """Get transaction by txid."""
        return self.transactions.get(txid)
    
    def get_transactions(self, max_count: int = None, 
                        max_size: int = None) -> List[Transaction]:
        """
        Get transactions for block inclusion.
        
        Args:
            max_count: Maximum number of transactions
            max_size: Maximum total size
            
        Returns:
            List of transactions sorted by fee rate
        """
        # Sort by fee rate (fee per byte)
        sorted_txs = sorted(
            self.transactions.values(),
            key=lambda tx: tx.fee / max(len(tx.serialize()), 1),
            reverse=True
        )
        
        result = []
        total_size = 0
        
        for tx in sorted_txs:
            tx_size = len(tx.serialize())
            
            if max_count and len(result) >= max_count:
                break
            
            if max_size and total_size + tx_size > max_size:
                continue
            
            result.append(tx)
            total_size += tx_size
        
        return result
    
    def remove_confirmed(self, txids: List[str]):
        """Remove confirmed transactions."""
        for txid in txids:
            self.remove_transaction(txid)
    
    def size(self) -> int:
        """Get number of transactions in mempool."""
        return len(self.transactions)
    
    def memory_usage(self) -> int:
        """Get current memory usage in bytes."""
        return self.current_size
    
    def clear(self):
        """Clear all transactions."""
        self.transactions.clear()
        self.tx_timestamps.clear()
        self.spent_outputs.clear()
        self.current_size = 0
    
    def save(self, filepath: str):
        """Save mempool to disk with timestamps."""
        import os
        import time
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = {
            'transactions': [
                {
                    **tx.to_dict(),
                    '_mempool_timestamp': self.tx_timestamps.get(tx.txid, time.time())
                }
                for tx in self.transactions.values()
            ],
            'tx_ttl': self.tx_ttl
        }
        with open(filepath, 'w') as f:
            json.dump(data, f)
    
    def load(self, filepath: str):
        """Load mempool from disk (transactions never expire when TTL=0)."""
        import os
        import time
        if not os.path.exists(filepath):
            return
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            now = time.time()
            loaded = 0
            expired = 0
            
            for tx_data in data.get('transactions', []):
                # Get timestamp from saved data
                timestamp = tx_data.pop('_mempool_timestamp', now)
                
                # Skip if expired (only if TTL > 0)
                if self.tx_ttl > 0 and now - timestamp > self.tx_ttl:
                    expired += 1
                    continue
                
                tx = Transaction.from_dict(tx_data)
                # Use skip_verification=True since we're loading previously validated txs
                # and blockchain may not be fully loaded yet
                if self.add_transaction(tx, timestamp=timestamp, skip_verification=True):
                    loaded += 1
            
            if expired > 0:
                print(f"Mempool: loaded {loaded} transactions, pruned {expired} expired")
            elif loaded > 0:
                print(f"Mempool: loaded {loaded} transactions")
                
        except Exception as e:
            print(f"Warning: Could not load mempool: {e}")
    
    def estimate_fee(self, blockchain=None, priority: str = 'normal') -> dict:
        """
        Bitcoin-style dynamic fee estimation.
        
        Calculates fees based on:
        1. Current mempool size and bytes
        2. Recent block fill rate
        3. Median fee rate from recent blocks
        
        Args:
            blockchain: Blockchain instance for historical analysis
            priority: 'fast', 'normal', or 'economy'
            
        Returns:
            dict with fee recommendations
        """
        try:
            from config import MIN_FEE_RATE, MAX_FEE_RATE, FEE_ESTIMATION_BLOCKS, MAX_BLOCK_SIZE
        except ImportError:
            MIN_FEE_RATE, MAX_FEE_RATE, FEE_ESTIMATION_BLOCKS, MAX_BLOCK_SIZE = 1, 1000, 10, 2000000
        
        mempool_size = self.size()
        mempool_bytes = self.current_size
        
        # Collect fee rates from mempool transactions
        mempool_fee_rates = []
        for tx in self.transactions.values():
            tx_size = max(len(tx.serialize()), 1)
            fee_rate = tx.fee / tx_size if tx.fee > 0 else MIN_FEE_RATE
            mempool_fee_rates.append(fee_rate)
        
        # Sort fee rates (highest first)
        mempool_fee_rates.sort(reverse=True)
        
        # Analyze recent blocks if blockchain provided
        recent_block_fill = 0.5  # Default 50% fill
        median_accepted_fee = MIN_FEE_RATE
        
        if blockchain:
            try:
                height = blockchain.get_height()
                blocks_to_analyze = min(FEE_ESTIMATION_BLOCKS, height)
                
                total_block_size = 0
                accepted_fees = []
                
                for i in range(height, max(0, height - blocks_to_analyze), -1):
                    block = blockchain.chain[i]
                    block_size = getattr(block, 'size', 0) or len(str(block.to_dict()))
                    total_block_size += block_size
                    
                    # Get fees from non-coinbase transactions
                    for tx_data in block.transactions:
                        tx = Transaction.from_dict(tx_data) if isinstance(tx_data, dict) else tx_data
                        if not tx.is_coinbase() and tx.fee > 0:
                            tx_size = max(len(tx.serialize()), 1)
                            accepted_fees.append(tx.fee / tx_size)
                
                if blocks_to_analyze > 0:
                    recent_block_fill = total_block_size / (blocks_to_analyze * MAX_BLOCK_SIZE)
                
                if accepted_fees:
                    accepted_fees.sort()
                    median_accepted_fee = accepted_fees[len(accepted_fees) // 2]
            except Exception as e:
                pass  # Use defaults if analysis fails
        
        # Calculate base fee rate from network conditions
        # Higher mempool = higher fees, higher block fill = higher fees
        congestion_factor = 1.0
        
        if mempool_size > 100:
            congestion_factor += (mempool_size - 100) / 100  # +1 for every 100 txs over 100
        
        if recent_block_fill > 0.8:
            congestion_factor += (recent_block_fill - 0.8) * 5  # Boost if blocks >80% full
        
        # Use the higher of: median accepted fee or congestion-based calculation
        base_fee_rate = max(median_accepted_fee, MIN_FEE_RATE * congestion_factor)
        
        # Priority multipliers (blocks to confirm)
        # fast: next 1-2 blocks, normal: 3-6 blocks, economy: 7+ blocks
        priority_config = {
            'fast': {'multiplier': 2.0, 'target_blocks': 1, 'percentile': 90},
            'normal': {'multiplier': 1.0, 'target_blocks': 3, 'percentile': 50},
            'economy': {'multiplier': 0.5, 'target_blocks': 10, 'percentile': 20}
        }
        
        config = priority_config.get(priority, priority_config['normal'])
        
        # If we have mempool fee data, use percentile-based estimation
        if mempool_fee_rates:
            percentile_idx = int(len(mempool_fee_rates) * (100 - config['percentile']) / 100)
            percentile_idx = min(percentile_idx, len(mempool_fee_rates) - 1)
            fee_rate = max(mempool_fee_rates[percentile_idx], base_fee_rate * config['multiplier'])
        else:
            fee_rate = base_fee_rate * config['multiplier']
        
        # Apply bounds
        fee_rate = max(MIN_FEE_RATE, min(MAX_FEE_RATE, int(fee_rate)))
        
        # Calculate for typical transaction sizes
        typical_tx_size = 250  # bytes
        
        return {
            'fee_rate': fee_rate,                           # sat/byte
            'fee_per_kb': fee_rate * 1000,                  # sat/KB
            'estimated_fee': fee_rate * typical_tx_size,    # for 250-byte tx
            'estimated_fee_salo': (fee_rate * typical_tx_size) / 100000000,
            'priority': priority,
            'target_blocks': config['target_blocks'],
            'mempool_size': mempool_size,
            'mempool_bytes': mempool_bytes,
            'recent_block_fill': round(recent_block_fill * 100, 1),
            'median_accepted_fee': round(median_accepted_fee, 2)
        }
    
    def get_fee_estimates(self, blockchain=None) -> dict:
        """
        Get fee estimates for wallet display.
        
        Returns fees for: fast, normal, economy
        """
        return {
            'fast': self.estimate_fee(blockchain, 'fast'),
            'normal': self.estimate_fee(blockchain, 'normal'),
            'economy': self.estimate_fee(blockchain, 'economy'),
            'mempool_size': self.size(),
            'mempool_bytes': self.current_size,
            'timestamp': int(__import__('time').time())
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'size': self.size(),
            'bytes': self.current_size,
            'tx_ttl': self.tx_ttl,
            'transactions': [tx.to_dict() for tx in self.transactions.values()],
        }
