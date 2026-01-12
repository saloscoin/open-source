"""
Job Management for SALOCOIN Pool
Creates and manages mining jobs for workers.
"""

import time
import struct
import hashlib
import threading
import requests
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
import logging

logger = logging.getLogger(__name__)

# Import from parent
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import config
    COIN_UNIT = config.COIN_UNIT
    INITIAL_BLOCK_REWARD = config.INITIAL_BLOCK_REWARD
    MIN_BLOCK_REWARD = config.MIN_BLOCK_REWARD
    HALVING_INTERVAL = config.HALVING_INTERVAL
    INITIAL_DIFFICULTY = config.INITIAL_DIFFICULTY
    GENESIS_HASH = config.GENESIS_HASH
except ImportError:
    COIN_UNIT = 100000000
    INITIAL_BLOCK_REWARD = 100 * COIN_UNIT
    MIN_BLOCK_REWARD = 1 * COIN_UNIT
    HALVING_INTERVAL = 210000
    INITIAL_DIFFICULTY = 0x1d00ffff
    GENESIS_HASH = "0" * 64


def double_sha256(data: bytes) -> bytes:
    """Double SHA256 hash."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def compact_to_target(compact: int) -> int:
    """Convert compact difficulty to target."""
    exp = (compact >> 24) & 0xFF
    coef = compact & 0x007fffff  # 23-bit mantissa (Bitcoin format)
    if exp <= 3:
        return coef >> (8 * (3 - exp))
    return coef << (8 * (exp - 3))


def merkle_hash(a: bytes, b: bytes) -> bytes:
    """Compute merkle hash of two nodes."""
    return double_sha256(a + b)


def calculate_merkle_root(txids: list) -> str:
    """Calculate merkle root from list of txids (hex strings)."""
    if not txids:
        return "0" * 64
    
    # Convert to bytes (little-endian for internal merkle calculation)
    hashes = [bytes.fromhex(txid)[::-1] for txid in txids]
    
    while len(hashes) > 1:
        # If odd number, duplicate last
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])
        
        # Pair and hash
        new_hashes = []
        for i in range(0, len(hashes), 2):
            new_hashes.append(merkle_hash(hashes[i], hashes[i + 1]))
        hashes = new_hashes
    
    # Return as hex string (big-endian for display)
    return hashes[0][::-1].hex()


@dataclass
class MiningJob:
    """Represents a mining job for workers."""
    id: str
    height: int
    prev_hash: str
    merkle_root: str
    timestamp: int
    difficulty: int
    target: int
    reward: int
    coinbase_tx: dict
    header76: bytes  # 76-byte header without nonce
    mempool_txs: list = field(default_factory=list)  # Mempool transactions to include
    created_at: float = field(default_factory=time.time)
    
    @property
    def target_hex(self) -> str:
        """Target as 64-char hex string."""
        return format(self.target, '064x')
    
    def to_stratum_params(self, share_target: int) -> list:
        """Convert to Stratum mining.notify params."""
        return [
            self.id,
            self.prev_hash,
            self.merkle_root[:32],  # merkle1
            self.merkle_root[32:],  # merkle2
            [],  # merkle branches (empty for single tx)
            format(1, '08x'),  # version
            format(self.difficulty, '08x'),  # nbits
            format(self.timestamp, '08x'),  # ntime
            True  # clean_jobs
        ]


class JobManager:
    """Manages mining jobs for the pool."""
    
    def __init__(self, pool_address: str, seed_url: str = "https://api.salocoin.org"):
        self.pool_address = pool_address
        self.seed_url = seed_url
        
        self.current_job: Optional[MiningJob] = None
        self.jobs: Dict[str, MiningJob] = {}  # job_id -> job
        self.lock = threading.RLock()
        
        self._job_counter = 0
        self.height = 0
        self.difficulty = INITIAL_DIFFICULTY
        self.prev_hash = GENESIS_HASH
        
        # Share difficulty (256x easier than block)
        self.share_multiplier = 256
    
    @property
    def target(self) -> int:
        """Current network target."""
        return compact_to_target(self.difficulty)
    
    @property
    def share_target(self) -> int:
        """Share target (easier than block)."""
        return self.target * self.share_multiplier
    
    def sync_blockchain(self) -> bool:
        """Sync blockchain state from seed node."""
        try:
            resp = requests.get(f"{self.seed_url}/status", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.height = data.get('height', 0)
                self.prev_hash = data.get('best_block', GENESIS_HASH)
                self.difficulty = data.get('difficulty', INITIAL_DIFFICULTY)
                logger.debug(f"Synced: height={self.height}, difficulty={self.difficulty}")
                return True
        except Exception as e:
            logger.error(f"Sync error: {e}")
        return False
    
    def fetch_mempool(self) -> list:
        """Fetch pending transactions from mempool."""
        try:
            resp = requests.get(f"{self.seed_url}/mempool", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                txs = data.get('transactions', [])
                logger.info(f"Fetched {len(txs)} mempool transactions")
                return txs
        except Exception as e:
            logger.warning(f"Mempool fetch error: {e}")
        return []
    
    def calc_reward(self, height: int) -> int:
        """Calculate block reward for height."""
        halvings = height // HALVING_INTERVAL
        reward = INITIAL_BLOCK_REWARD
        for _ in range(halvings):
            reward //= 2
        return max(reward, MIN_BLOCK_REWARD)
    
    def create_coinbase(self, height: int, reward: int) -> dict:
        """Create coinbase transaction."""
        try:
            import base58
            decoded = base58.b58decode_check(self.pool_address)
            pubkey_hash = decoded[1:].hex()
        except:
            pubkey_hash = "0" * 40
        
        script_pubkey = f"76a914{pubkey_hash}88ac"
        height_bytes = struct.pack('<I', height)
        script_sig = height_bytes.hex()
        
        # Build raw tx for txid
        tx_raw = struct.pack('<I', 1)  # version
        tx_raw += bytes([1])  # input count
        tx_raw += bytes.fromhex("0" * 64)  # null txid
        tx_raw += struct.pack('<I', 0xFFFFFFFF)  # vout
        tx_raw += bytes([len(height_bytes)]) + height_bytes
        tx_raw += struct.pack('<I', 0xFFFFFFFF)  # sequence
        tx_raw += bytes([1])  # output count
        tx_raw += struct.pack('<Q', reward)
        script_bytes = bytes.fromhex(script_pubkey)
        tx_raw += bytes([len(script_bytes)]) + script_bytes
        tx_raw += struct.pack('<I', 0)  # locktime
        
        txid = double_sha256(tx_raw)[::-1].hex()
        
        return {
            'txid': txid,
            'version': 1,
            'inputs': [{
                'txid': "0" * 64,
                'vout': 0xFFFFFFFF,
                'scriptSig': script_sig,
                'sequence': 0xFFFFFFFF
            }],
            'outputs': [{
                'value': reward,
                'scriptPubKey': script_pubkey,
                'address': self.pool_address
            }],
            'locktime': 0,
            'is_coinbase': True
        }
    
    def create_job(self, force: bool = False) -> Optional[MiningJob]:
        """Create a new mining job."""
        old_height = self.height
        
        if not self.sync_blockchain():
            return None
        
        # Only create new job if height changed or forced
        if not force and old_height == self.height and self.current_job:
            return self.current_job
        
        with self.lock:
            self._job_counter += 1
            job_id = f"{self._job_counter:08x}"
            
            new_height = self.height + 1
            reward = self.calc_reward(new_height)
            timestamp = int(time.time())
            
            coinbase_tx = self.create_coinbase(new_height, reward)
            
            # Fetch mempool transactions
            mempool_txs = self.fetch_mempool()
            
            # Calculate merkle root from all transactions
            all_txids = [coinbase_tx['txid']] + [tx['txid'] for tx in mempool_txs]
            merkle_root = calculate_merkle_root(all_txids)
            
            target = compact_to_target(self.difficulty)
            
            # Build 76-byte header
            header76 = struct.pack('<I', 1)  # version
            header76 += bytes.fromhex(self.prev_hash)[::-1]
            header76 += bytes.fromhex(merkle_root)[::-1]
            header76 += struct.pack('<I', timestamp)
            header76 += struct.pack('<I', self.difficulty)
            
            job = MiningJob(
                id=job_id,
                height=new_height,
                prev_hash=self.prev_hash,
                merkle_root=merkle_root,
                timestamp=timestamp,
                difficulty=self.difficulty,
                target=target,
                reward=reward,
                coinbase_tx=coinbase_tx,
                header76=header76,
                mempool_txs=mempool_txs
            )
            
            self.jobs[job_id] = job
            self.current_job = job
            
            # Cleanup old jobs (keep last 10)
            if len(self.jobs) > 10:
                oldest_ids = sorted(self.jobs.keys())[:-10]
                for old_id in oldest_ids:
                    del self.jobs[old_id]
            
            logger.info(f"Created job {job_id} for height {new_height}")
            return job
    
    def get_job(self, job_id: str) -> Optional[MiningJob]:
        """Get job by ID."""
        with self.lock:
            return self.jobs.get(job_id)
    
    def get_current_job(self) -> Optional[MiningJob]:
        """Get current active job."""
        with self.lock:
            return self.current_job
    
    def is_job_stale(self, job_id: str) -> bool:
        """Check if job is stale (not current)."""
        with self.lock:
            return self.current_job is None or self.current_job.id != job_id
    
    def get_stratum_notify(self) -> Optional[dict]:
        """Get Stratum mining.notify message for current job."""
        job = self.current_job
        if not job:
            return None
        
        return {
            'id': None,
            'method': 'mining.notify',
            'params': job.to_stratum_params(self.share_target)
        }
    
    def get_stratum_target(self) -> dict:
        """Get Stratum mining.set_target message."""
        return {
            'id': None,
            'method': 'mining.set_target',
            'params': [format(self.share_target, '064x')]
        }
