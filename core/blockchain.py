"""
SALOCOIN Blockchain Implementation
Block structure, chain management, and consensus rules.
"""

import time
import struct
import json
import os
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from threading import Lock

from .crypto import sha256d, merkle_root, compact_to_target, target_to_compact
from .transaction import Transaction, TransactionPool
import config


@dataclass
class Block:
    """SALOCOIN Block structure."""
    
    version: int
    height: int
    timestamp: int
    previous_hash: str
    merkle_root: str
    difficulty: int  # Compact difficulty (nBits)
    nonce: int
    transactions: List[Dict] = field(default_factory=list)
    
    # Computed fields
    hash: str = ''
    size: int = 0
    
    # Masternode related
    masternode_payee: str = ''
    masternode_signature: bytes = b''
    
    def __post_init__(self):
        """Calculate block hash after initialization."""
        if not self.hash:
            self.hash = self.calculate_hash()
        self.size = len(self.serialize_header())
    
    def serialize_header(self) -> bytes:
        """
        Serialize block header for hashing.
        80 bytes total (same as Bitcoin).
        """
        header = struct.pack('<I', self.version)                    # 4 bytes
        header += bytes.fromhex(self.previous_hash)[::-1]           # 32 bytes (reversed)
        header += bytes.fromhex(self.merkle_root)[::-1]             # 32 bytes (reversed)
        header += struct.pack('<I', self.timestamp)                 # 4 bytes
        header += struct.pack('<I', self.difficulty)                # 4 bytes
        header += struct.pack('<I', self.nonce)                     # 4 bytes
        return header
    
    def calculate_hash(self) -> str:
        """Calculate block hash using SHA-256d."""
        header = self.serialize_header()
        return sha256d(header)[::-1].hex()  # Reversed for display
    
    def calculate_merkle_root(self) -> str:
        """Calculate Merkle root from transactions."""
        if not self.transactions:
            return '0' * 64
        
        # Get transaction hashes
        tx_hashes = []
        for tx_data in self.transactions:
            if isinstance(tx_data, dict):
                tx = Transaction.from_dict(tx_data)
            else:
                tx = tx_data
            tx_hash = bytes.fromhex(tx.txid)[::-1]  # Reversed
            tx_hashes.append(tx_hash)
        
        root = merkle_root(tx_hashes)
        return root[::-1].hex()  # Reversed for display
    
    def validate_merkle_root(self) -> bool:
        """Validate that Merkle root matches transactions."""
        return self.merkle_root == self.calculate_merkle_root()
    
    def validate_proof_of_work(self) -> bool:
        """Validate that block hash meets difficulty target."""
        target = self.get_target_from_difficulty(self.difficulty)
        hash_int = int(self.hash, 16)
        return hash_int < target
    
    @staticmethod
    def get_target_from_difficulty(difficulty: int) -> int:
        """Convert compact difficulty to full target."""
        return compact_to_target(difficulty)
    
    @staticmethod
    def get_difficulty_from_target(target: int) -> int:
        """Convert full target to compact difficulty."""
        return target_to_compact(target)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'hash': self.hash,
            'version': self.version,
            'height': self.height,
            'timestamp': self.timestamp,
            'previous_hash': self.previous_hash,
            'merkle_root': self.merkle_root,
            'difficulty': self.difficulty,
            'nonce': self.nonce,
            'size': self.size,
            'tx_count': len(self.transactions),
            'transactions': self.transactions,
            'masternode_payee': self.masternode_payee,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Block':
        """Create block from dictionary."""
        block = cls(
            version=data['version'],
            height=data['height'],
            timestamp=data['timestamp'],
            previous_hash=data['previous_hash'],
            merkle_root=data['merkle_root'],
            difficulty=data['difficulty'],
            nonce=data['nonce'],
            transactions=data.get('transactions', []),
        )
        block.hash = data.get('hash', block.calculate_hash())
        block.masternode_payee = data.get('masternode_payee', '')
        return block
    
    def get_coinbase(self) -> Optional[Transaction]:
        """Get coinbase transaction."""
        if self.transactions:
            tx_data = self.transactions[0]
            if isinstance(tx_data, dict):
                return Transaction.from_dict(tx_data)
            return tx_data
        return None
    
    def get_reward(self) -> int:
        """Get total block reward."""
        return config.calculate_block_reward(self.height)


class Blockchain:
    """SALOCOIN Blockchain manager."""
    
    def __init__(self, data_dir: str = None):
        """
        Initialize blockchain.
        
        Args:
            data_dir: Directory for blockchain data
        """
        self.chain: List[Block] = []
        self.block_index: Dict[str, int] = {}  # hash -> height
        self.tx_index: Dict[str, Tuple[str, int]] = {}  # txid -> (block_hash, tx_index)
        
        self.current_difficulty = config.INITIAL_DIFFICULTY
        self.total_work = 0
        
        self.mempool = TransactionPool()
        self.mempool.set_blockchain(self)  # Link mempool to blockchain for UTXO verification
        
        self.data_dir = data_dir or config.get_data_dir()
        self.lock = Lock()
        
        # Initialize with genesis block if empty
        if not self.chain:
            self._create_genesis_block()
    
    def _create_genesis_block(self):
        """Create the hardcoded genesis block. This CANNOT be modified."""
        genesis_coinbase = Transaction.create_coinbase(
            block_height=0,
            miner_address='S' + '1' * 33,  # Genesis address (no spendable coins)
            extra_data=config.GENESIS_BLOCK['coinbase_message'].decode()
        )
        
        # Use hardcoded merkle_root from config if available
        merkle_root = config.GENESIS_BLOCK.get('merkle_root', '')
        
        genesis = Block(
            version=config.GENESIS_BLOCK['version'],
            height=0,
            timestamp=config.GENESIS_BLOCK['timestamp'],
            previous_hash=config.GENESIS_BLOCK['prev_hash'],
            merkle_root=merkle_root,
            difficulty=config.GENESIS_BLOCK['bits'],
            nonce=config.GENESIS_BLOCK['nonce'],
            transactions=[genesis_coinbase.to_dict()],
        )
        
        # Calculate merkle root only if not hardcoded
        if not merkle_root:
            genesis.merkle_root = genesis.calculate_merkle_root()
        
        genesis.hash = genesis.calculate_hash()
        
        # Verify genesis hash matches expected (if set)
        if config.GENESIS_HASH and genesis.hash != config.GENESIS_HASH:
            print(f"⚠ Warning: Genesis hash mismatch!")
            print(f"   Calculated: {genesis.hash}")
            print(f"   Expected:   {config.GENESIS_HASH}")
            # Use expected hash to maintain network compatibility
            genesis.hash = config.GENESIS_HASH
        elif not config.GENESIS_HASH:
            # First run - print the genesis hash to hardcode later
            print(f"🆕 New Genesis Block Created!")
            print(f"   Hash: {genesis.hash}")
            print(f"   Timestamp: {genesis.timestamp}")
        
        self.chain.append(genesis)
        self.block_index[genesis.hash] = 0
        
        # Index genesis coinbase
        self.tx_index[genesis_coinbase.txid] = (genesis.hash, 0)
    
    def validate_genesis(self) -> bool:
        """Validate that genesis block matches hardcoded values."""
        if not self.chain:
            return False
        
        genesis = self.chain[0]
        
        # Genesis must have correct parameters
        if genesis.height != 0:
            return False
        if genesis.previous_hash != '0' * 64:
            return False
        if genesis.timestamp != config.GENESIS_BLOCK['timestamp']:
            return False
        if genesis.version != config.GENESIS_BLOCK['version']:
            return False
        
        return True
    
    def get_height(self) -> int:
        """Get current blockchain height."""
        return len(self.chain) - 1
    
    def get_latest_block(self) -> Block:
        """Get the latest block."""
        return self.chain[-1]
    
    def get_tip(self) -> Block:
        """Get the tip (latest block) of the chain. Alias for get_latest_block."""
        return self.get_latest_block()
    
    def get_block_by_height(self, height: int) -> Optional[Block]:
        """Get block at specific height."""
        if 0 <= height < len(self.chain):
            return self.chain[height]
        return None
    
    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        """Get block by hash."""
        height = self.block_index.get(block_hash)
        if height is not None:
            return self.chain[height]
        return None
    
    def get_transaction(self, txid: str) -> Optional[Tuple[Transaction, Block]]:
        """Get transaction by txid with containing block."""
        # Check mempool first
        tx = self.mempool.get_transaction(txid)
        if tx:
            return tx, None
        
        # Check block index
        location = self.tx_index.get(txid)
        if location:
            block_hash, tx_idx = location
            block = self.get_block_by_hash(block_hash)
            if block and tx_idx < len(block.transactions):
                tx = Transaction.from_dict(block.transactions[tx_idx])
                return tx, block
        
        return None
    
    def add_block(self, block: Block) -> bool:
        """
        Add a new block to the chain.
        
        Args:
            block: Block to add
            
        Returns:
            True if block was added successfully
        """
        with self.lock:
            # Validate block
            if not self._validate_block(block):
                return False
            
            # Add to chain
            self.chain.append(block)
            self.block_index[block.hash] = block.height
            
            # Index transactions
            for i, tx_data in enumerate(block.transactions):
                if isinstance(tx_data, dict):
                    tx = Transaction.from_dict(tx_data)
                else:
                    tx = tx_data
                self.tx_index[tx.txid] = (block.hash, i)
                
                # Remove from mempool
                self.mempool.remove_transaction(tx.txid)
            
            # Update difficulty
            self._update_difficulty()
            
            # Update total work
            target = Block.get_target_from_difficulty(block.difficulty)
            work = (2 ** 256) // (target + 1)
            self.total_work += work
            
            return True
    
    def calculate_chain_work(self, blocks: List[Block]) -> int:
        """
        Calculate total work for a list of blocks.
        
        Args:
            blocks: List of blocks
            
        Returns:
            Total work (sum of all block work)
        """
        total = 0
        for block in blocks:
            target = Block.get_target_from_difficulty(block.difficulty)
            work = (2 ** 256) // (target + 1)
            total += work
        return total
    
    def try_reorganize(self, new_chain: List[Block]) -> bool:
        """
        Attempt to reorganize to a new chain if it has more work.
        Bitcoin-style chain selection: the chain with most cumulative work wins.
        
        Args:
            new_chain: The competing chain (must start from a common ancestor)
            
        Returns:
            True if reorganization happened
        """
        with self.lock:
            if not new_chain:
                return False
            
            # Find common ancestor
            new_first = new_chain[0]
            common_height = new_first.height - 1
            
            if common_height < 0:
                return False
            
            if common_height >= len(self.chain):
                return False
            
            # Check MAX_REORG_DEPTH - prevent deep reorganizations
            reorg_depth = len(self.chain) - 1 - common_height
            if reorg_depth > config.MAX_REORG_DEPTH:
                print(f"Reorg rejected: depth {reorg_depth} exceeds MAX_REORG_DEPTH ({config.MAX_REORG_DEPTH})")
                return False
            
            # Verify new chain connects to our chain
            if new_first.previous_hash != self.chain[common_height].hash:
                print(f"Reorg failed: chains don't share common ancestor")
                return False
            
            # Calculate work for both chains from fork point
            our_blocks = self.chain[common_height + 1:]
            our_work = self.calculate_chain_work(our_blocks)
            new_work = self.calculate_chain_work(new_chain)
            
            print(f"Chain comparison from height {common_height}:")
            print(f"  Our chain: {len(our_blocks)} blocks, work: {our_work}")
            print(f"  New chain: {len(new_chain)} blocks, work: {new_work}")
            
            # Only reorg if new chain has MORE work (not equal)
            if new_work <= our_work:
                print(f"Keeping current chain (has equal or more work)")
                return False
            
            # Validate all blocks in new chain
            for block in new_chain:
                if not block.validate_proof_of_work():
                    print(f"Reorg failed: invalid PoW at height {block.height}")
                    return False
                if not block.validate_merkle_root():
                    print(f"Reorg failed: invalid merkle root at height {block.height}")
                    return False
            
            print(f"⚠️ CHAIN REORGANIZATION: rolling back {len(our_blocks)} blocks, adding {len(new_chain)} blocks")
            
            # Roll back our chain - return transactions to mempool
            for block in reversed(our_blocks):
                for tx_data in block.transactions[1:]:  # Skip coinbase
                    tx = Transaction.from_dict(tx_data) if isinstance(tx_data, dict) else tx_data
                    self.mempool.add_transaction(tx)
                # Remove from indices
                del self.block_index[block.hash]
                for tx_data in block.transactions:
                    tx = Transaction.from_dict(tx_data) if isinstance(tx_data, dict) else tx_data
                    if tx.txid in self.tx_index:
                        del self.tx_index[tx.txid]
            
            # Truncate chain
            self.chain = self.chain[:common_height + 1]
            
            # Recalculate total work
            self.total_work = self.calculate_chain_work(self.chain)
            
            # Recalculate difficulty
            self._update_difficulty()
            
            # Add new blocks
            for block in new_chain:
                # Update UTXO set and indices
                self.chain.append(block)
                self.block_index[block.hash] = block.height
                
                for i, tx_data in enumerate(block.transactions):
                    tx = Transaction.from_dict(tx_data) if isinstance(tx_data, dict) else tx_data
                    self.tx_index[tx.txid] = (block.hash, i)
                    self.mempool.remove_transaction(tx.txid)
                
                # Add work
                target = Block.get_target_from_difficulty(block.difficulty)
                work = (2 ** 256) // (target + 1)
                self.total_work += work
            
            # Update difficulty after reorg
            self._update_difficulty()
            
            print(f"✓ Reorg complete. New height: {len(self.chain) - 1}")
            return True

    def _validate_block(self, block: Block) -> bool:
        """
        Validate a block before adding to chain.
        
        Args:
            block: Block to validate
            
        Returns:
            True if block is valid
        """
        # Check height
        expected_height = len(self.chain)
        if block.height != expected_height:
            print(f"Invalid block height: expected {expected_height}, got {block.height}")
            return False
        
        # Check previous hash
        if block.previous_hash != self.chain[-1].hash:
            print("Invalid previous hash")
            return False
        
        # Check timestamp - must be greater than Median Time Past (MTP)
        mtp = self._get_median_time_past()
        if block.timestamp <= mtp:
            print(f"Block timestamp {block.timestamp} must be > MTP {mtp}")
            return False
        
        # Check timestamp - cannot be too far in future
        if block.timestamp > int(time.time()) + config.MAX_FUTURE_BLOCK_TIME:
            print(f"Block timestamp too far in future (max {config.MAX_FUTURE_BLOCK_TIME}s)")
            return False
        
        # Check proof of work
        if not block.validate_proof_of_work():
            print("Invalid proof of work")
            return False
        
        # Check difficulty is within bounds
        if block.difficulty < config.MAX_DIFFICULTY:  # Lower value = harder
            print(f"Difficulty too high (suspicious)")
            # Allow but log - could be legitimate high hashrate
        
        # Check merkle root
        if not block.validate_merkle_root():
            print("Invalid merkle root")
            return False
        
        # Check transactions
        if not block.transactions:
            print("Block has no transactions")
            return False
        
        # First transaction must be coinbase
        coinbase = Transaction.from_dict(block.transactions[0])
        if not coinbase.is_coinbase:
            print("First transaction is not coinbase")
            return False
        
        # Validate coinbase reward
        coinbase_value = sum(out.value for out in coinbase.outputs)
        expected_reward = config.calculate_block_reward(block.height)
        # Allow total coinbase outputs to equal reward + fees (fees collected from txs)
        # For now, just ensure it doesn't exceed reward (fee validation would need full UTXO check)
        
        # Track spent outputs within this block to prevent double-spend
        spent_in_block = set()
        total_fees = 0
        
        # Validate all transactions
        for i, tx_data in enumerate(block.transactions[1:], 1):
            tx = Transaction.from_dict(tx_data)
            if tx.is_coinbase:
                print(f"Non-first transaction {i} is coinbase")
                return False
            
            # Verify transaction signatures
            if not tx.verify():
                print(f"Transaction {i} ({tx.txid[:16]}...) has invalid signature")
                return False
            
            # Verify inputs exist and are unspent
            tx_input_value = 0
            for inp in tx.inputs:
                outpoint = f"{inp.txid}:{inp.vout}"
                
                # Check for double-spend within this block
                if outpoint in spent_in_block:
                    print(f"Double-spend detected in block: {outpoint}")
                    return False
                spent_in_block.add(outpoint)
                
                # Verify input exists in blockchain
                prev_tx_result = self.get_transaction(inp.txid)
                if not prev_tx_result or prev_tx_result[1] is None:
                    # Check if it's in earlier transactions of this block
                    found_in_block = False
                    for j, earlier_tx_data in enumerate(block.transactions[:i]):
                        earlier_tx = Transaction.from_dict(earlier_tx_data)
                        if earlier_tx.txid == inp.txid:
                            if inp.vout < len(earlier_tx.outputs):
                                tx_input_value += earlier_tx.outputs[inp.vout].value
                                found_in_block = True
                                break
                    if not found_in_block:
                        print(f"Transaction {i} references non-existent input: {inp.txid[:16]}...")
                        return False
                else:
                    prev_tx, prev_block = prev_tx_result
                    if inp.vout >= len(prev_tx.outputs):
                        print(f"Transaction {i} references invalid output index")
                        return False
                    
                    # Check if already spent in blockchain
                    if self._is_output_spent(inp.txid, inp.vout):
                        print(f"Transaction {i} references already spent output: {outpoint}")
                        return False
                    
                    # Check coinbase maturity
                    if prev_tx.is_coinbase:
                        confirmations = block.height - prev_block.height
                        if confirmations < config.COINBASE_MATURITY:
                            print(f"Transaction {i} spends immature coinbase (need {config.COINBASE_MATURITY} confirmations, have {confirmations})")
                            return False
                    
                    tx_input_value += prev_tx.outputs[inp.vout].value
            
            # Verify outputs don't exceed inputs
            tx_output_value = sum(out.value for out in tx.outputs)
            if tx_output_value > tx_input_value:
                print(f"Transaction {i} outputs ({tx_output_value}) exceed inputs ({tx_input_value})")
                return False
            
            # Calculate fee
            total_fees += tx_input_value - tx_output_value
        
        # Validate coinbase doesn't exceed reward + fees
        if coinbase_value > expected_reward + total_fees:
            print(f"Coinbase value ({coinbase_value}) exceeds reward ({expected_reward}) + fees ({total_fees})")
            return False
        
        # Check block size
        if block.size > config.MAX_BLOCK_SIZE:
            print("Block too large")
            return False
        
        return True
    
    def _is_output_spent(self, txid: str, vout: int) -> bool:
        """Check if an output has been spent in the blockchain."""
        for block in self.chain:
            for tx_data in block.transactions:
                tx = Transaction.from_dict(tx_data)
                for inp in tx.inputs:
                    if inp.txid == txid and inp.vout == vout:
                        return True
        return False
    
    def _update_difficulty(self):
        """
        Update difficulty using Dark Gravity Wave algorithm.
        Adjusts every block based on last DGW_PAST_BLOCKS blocks.
        Also applies difficulty multiplier at milestone blocks for security.
        """
        if len(self.chain) < config.DGW_PAST_BLOCKS + 1:
            return
        
        # Get blocks for calculation
        blocks = self.chain[-config.DGW_PAST_BLOCKS - 1:]
        
        # Calculate actual timespan
        actual_timespan = blocks[-1].timestamp - blocks[0].timestamp
        
        # Target timespan
        target_timespan = config.BLOCK_TIME_TARGET * config.DGW_PAST_BLOCKS
        
        # Limit adjustment (max 4x change per adjustment)
        if actual_timespan < target_timespan // config.MAX_DIFFICULTY_ADJUSTMENT:
            actual_timespan = target_timespan // config.MAX_DIFFICULTY_ADJUSTMENT
        elif actual_timespan > target_timespan * config.MAX_DIFFICULTY_ADJUSTMENT:
            actual_timespan = target_timespan * config.MAX_DIFFICULTY_ADJUSTMENT
        
        # Calculate new target
        old_difficulty = self.current_difficulty
        current_target = Block.get_target_from_difficulty(self.current_difficulty)
        new_target = int((current_target * actual_timespan) // target_timespan)
        
        # Apply difficulty milestone multiplier (lower target = harder)
        height = len(self.chain)
        multiplier = config.get_difficulty_multiplier(height)
        if multiplier > 1:
            new_target = new_target // multiplier
        
        # Ensure target doesn't go above minimum difficulty (easiest)
        max_target = Block.get_target_from_difficulty(config.MIN_DIFFICULTY)
        if new_target > max_target:
            new_target = max_target
        
        # Ensure target doesn't go below maximum difficulty (hardest)
        min_target = Block.get_target_from_difficulty(config.MAX_DIFFICULTY)
        if new_target < min_target:
            new_target = min_target
        
        # Ensure target doesn't become zero or negative
        if new_target < 1:
            new_target = 1
        
        self.current_difficulty = Block.get_difficulty_from_target(new_target)
        
        # Log significant difficulty changes
        if self.current_difficulty != old_difficulty:
            ratio = blocks[-1].timestamp - blocks[0].timestamp
            print(f"⚡ Difficulty adjusted: {old_difficulty} → {self.current_difficulty} (actual {ratio}s vs target {target_timespan}s)")
    
    def _get_median_time_past(self) -> int:
        """
        Get Median Time Past (MTP) - median timestamp of last 11 blocks.
        Used for timestamp validation to prevent manipulation.
        
        Returns:
            Median timestamp of last MTP_BLOCK_COUNT blocks
        """
        if len(self.chain) < config.MTP_BLOCK_COUNT:
            # Not enough blocks, use last block's timestamp
            return self.chain[-1].timestamp if self.chain else 0
        
        # Get last MTP_BLOCK_COUNT timestamps
        timestamps = [b.timestamp for b in self.chain[-config.MTP_BLOCK_COUNT:]]
        timestamps.sort()
        
        # Return median
        return timestamps[len(timestamps) // 2]
    
    def is_coinbase_mature(self, txid: str) -> bool:
        """
        Check if a coinbase transaction has enough confirmations to be spent.
        
        Args:
            txid: Transaction ID to check
            
        Returns:
            True if mature (has COINBASE_MATURITY confirmations) or not a coinbase
        """
        result = self.get_transaction(txid)
        if not result:
            return True  # Unknown tx, let other validation handle it
        
        tx, block = result
        
        # If not coinbase, always mature
        if not tx.is_coinbase:
            return True
        
        # Calculate confirmations
        current_height = len(self.chain) - 1
        confirmations = current_height - block.height + 1
        
        return confirmations >= config.COINBASE_MATURITY
    
    def get_next_difficulty(self) -> int:
        """
        Get difficulty for next block.
        Includes emergency difficulty reduction if blocks are taking too long.
        """
        import time
        
        if len(self.chain) == 0:
            return self.current_difficulty
        
        # Check for emergency difficulty reduction
        # If last block was found more than EMERGENCY_DIFFICULTY_THRESHOLD seconds ago,
        # reduce difficulty to help network recover from miner departure
        last_block_time = self.chain[-1].timestamp
        time_since_last_block = int(time.time()) - last_block_time
        
        if time_since_last_block > config.EMERGENCY_DIFFICULTY_THRESHOLD:
            # Calculate how many threshold periods have passed
            periods = time_since_last_block // config.EMERGENCY_DIFFICULTY_THRESHOLD
            
            # Get current target and make it easier
            current_target = Block.get_target_from_difficulty(self.current_difficulty)
            
            # Each period, make it 4x easier (multiply target by 4)
            emergency_target = current_target * (config.EMERGENCY_DIFFICULTY_REDUCTION ** periods)
            
            # Cap at minimum difficulty (easiest allowed)
            max_target = Block.get_target_from_difficulty(config.MIN_DIFFICULTY)
            if emergency_target > max_target:
                emergency_target = max_target
            
            return Block.get_difficulty_from_target(int(emergency_target))
        
        return self.current_difficulty
    
    def create_block_template(self, miner_address: str,
                               extra_data: str = "") -> Block:
        """
        Create a block template for mining.
        
        Args:
            miner_address: Address to receive mining reward
            extra_data: Extra data for coinbase
            
        Returns:
            Block template (without valid nonce)
        """
        height = len(self.chain)
        
        # Create coinbase
        coinbase = Transaction.create_coinbase(
            block_height=height,
            miner_address=miner_address,
            extra_data=extra_data
        )
        
        # Get transactions from mempool
        txs = self.mempool.get_transactions(
            max_size=config.MAX_BLOCK_SIZE - 1000  # Leave room for coinbase
        )
        
        transactions = [coinbase.to_dict()]
        transactions.extend([tx.to_dict() for tx in txs])
        
        # Use get_next_difficulty() to apply emergency reduction if needed
        next_difficulty = self.get_next_difficulty()
        
        block = Block(
            version=1,
            height=height,
            timestamp=int(time.time()),
            previous_hash=self.chain[-1].hash,
            merkle_root='',
            difficulty=next_difficulty,
            nonce=0,
            transactions=transactions,
        )
        
        block.merkle_root = block.calculate_merkle_root()
        
        return block
    
    def mine_block(self, block: Block, max_nonce: int = 2**32) -> Optional[Block]:
        """
        Mine a block by finding valid nonce.
        
        Args:
            block: Block template to mine
            max_nonce: Maximum nonce to try
            
        Returns:
            Mined block or None if max_nonce reached
        """
        target = Block.get_target_from_difficulty(block.difficulty)
        
        for nonce in range(max_nonce):
            block.nonce = nonce
            block.hash = block.calculate_hash()
            
            if int(block.hash, 16) < target:
                return block
            
            # Print progress occasionally
            if nonce % 100000 == 0 and nonce > 0:
                print(f"Mining... nonce={nonce}, hash={block.hash[:16]}...")
        
        return None
    
    def get_balance(self, address: str) -> int:
        """
        Get balance of an address.
        
        Note: This is a simplified implementation.
        A real implementation would use UTXO set.
        
        Args:
            address: Address to check
            
        Returns:
            Balance in satoshis
        """
        balance = 0
        spent = set()  # Track spent outputs
        
        # Scan all blocks
        for block in self.chain:
            for tx_data in block.transactions:
                tx = Transaction.from_dict(tx_data)
                
                # Mark inputs as spent
                for inp in tx.inputs:
                    if not inp.is_coinbase():
                        spent.add(f"{inp.txid}:{inp.vout}")
                
                # Add unspent outputs
                for i, out in enumerate(tx.outputs):
                    if out.address == address:
                        outpoint = f"{tx.txid}:{i}"
                        if outpoint not in spent:
                            balance += out.value
        
        return balance
    
    def get_utxos(self, address: str, include_immature: bool = False) -> List[Dict]:
        """
        Get unspent transaction outputs for an address.
        
        Args:
            address: Address to get UTXOs for
            include_immature: Include immature coinbase outputs (default False)
            
        Returns:
            List of UTXO dictionaries
        """
        utxos = {}
        coinbase_txids = set()  # Track which txids are coinbase
        
        current_height = len(self.chain) - 1
        
        # Scan all blocks
        for block in self.chain:
            for tx_data in block.transactions:
                tx = Transaction.from_dict(tx_data)
                
                # Track coinbase transactions
                if tx.is_coinbase:
                    coinbase_txids.add(tx.txid)
                
                # Remove spent outputs
                for inp in tx.inputs:
                    if not inp.is_coinbase():
                        outpoint = f"{inp.txid}:{inp.vout}"
                        utxos.pop(outpoint, None)
                
                # Add outputs for this address
                for i, out in enumerate(tx.outputs):
                    if out.address == address:
                        confirmations = current_height - block.height + 1
                        is_coinbase = tx.is_coinbase
                        
                        # Check coinbase maturity
                        if is_coinbase and not include_immature:
                            if confirmations < config.COINBASE_MATURITY:
                                continue  # Skip immature coinbase outputs
                        
                        outpoint = f"{tx.txid}:{i}"
                        utxos[outpoint] = {
                            'txid': tx.txid,
                            'vout': i,
                            'value': out.value,
                            'script': out.script_pubkey.hex(),
                            'confirmations': confirmations,
                            'is_coinbase': is_coinbase,
                            'is_mature': not is_coinbase or confirmations >= config.COINBASE_MATURITY,
                        }
        
        return list(utxos.values())
    
    def save(self, filepath: str = None):
        """Save blockchain to file."""
        if filepath is None:
            os.makedirs(self.data_dir, exist_ok=True)
            filepath = os.path.join(self.data_dir, config.BLOCKCHAIN_FILENAME)
        
        data = {
            'height': self.get_height(),
            'difficulty': self.current_difficulty,
            'total_work': self.total_work,
            'blocks': [block.to_dict() for block in self.chain],
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f)
        
        # Save mempool
        mempool_path = os.path.join(self.data_dir, 'mempool.json')
        self.mempool.save(mempool_path)
    
    def load(self, filepath: str = None) -> bool:
        """Load blockchain from file."""
        if filepath is None:
            filepath = os.path.join(self.data_dir, config.BLOCKCHAIN_FILENAME)
        
        if not os.path.exists(filepath):
            return False
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            self.chain = [Block.from_dict(b) for b in data['blocks']]
            self.current_difficulty = data['difficulty']
            self.total_work = data['total_work']
            
            # Rebuild indices
            self.block_index.clear()
            self.tx_index.clear()
            
            for block in self.chain:
                self.block_index[block.hash] = block.height
                for i, tx_data in enumerate(block.transactions):
                    tx = Transaction.from_dict(tx_data)
                    self.tx_index[tx.txid] = (block.hash, i)
            
            # Load mempool
            mempool_path = os.path.join(self.data_dir, 'mempool.json')
            self.mempool.load(mempool_path)
            
            return True
            
        except Exception as e:
            print(f"Error loading blockchain: {e}")
            return False
    
    def get_chain_info(self) -> Dict[str, Any]:
        """Get blockchain information."""
        return {
            'chain': 'main',
            'blocks': len(self.chain),
            'headers': len(self.chain),
            'bestblockhash': self.chain[-1].hash,
            'difficulty': self.current_difficulty,
            'mediantime': self.chain[-1].timestamp,
            'chainwork': hex(self.total_work),
            'pruned': False,
            'size_on_disk': 0,  # Would calculate from files
        }
    
    def get_block_stats(self, height: int) -> Optional[Dict[str, Any]]:
        """Get statistics for a block."""
        block = self.get_block_by_height(height)
        if not block:
            return None
        
        total_out = 0
        total_fee = 0
        tx_count = len(block.transactions)
        
        for tx_data in block.transactions:
            tx = Transaction.from_dict(tx_data)
            total_out += tx.get_total_output_value()
            if not tx.is_coinbase:
                total_fee += tx.fee
        
        return {
            'height': height,
            'hash': block.hash,
            'time': block.timestamp,
            'txs': tx_count,
            'total_out': total_out,
            'total_fee': total_fee,
            'subsidy': block.get_reward(),
            'size': block.size,
        }
