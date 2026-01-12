"""
Share Validation for SALOCOIN Pool
Validates submitted shares and blocks.
"""

import struct
import hashlib
from dataclasses import dataclass
from typing import Tuple, Optional
from enum import Enum
import logging

from .job_manager import JobManager, MiningJob, double_sha256

logger = logging.getLogger(__name__)


class ShareResult(Enum):
    """Result of share validation."""
    VALID_SHARE = "valid_share"
    VALID_BLOCK = "valid_block"
    INVALID_NONCE = "invalid_nonce"
    INVALID_HASH = "invalid_hash"
    STALE_JOB = "stale_job"
    DUPLICATE = "duplicate"
    LOW_DIFFICULTY = "low_difficulty"


@dataclass
class ShareSubmission:
    """Represents a share submission from a worker."""
    worker_id: int
    job_id: str
    nonce: int
    hash_result: str = ""
    is_block: bool = False
    result: ShareResult = ShareResult.INVALID_HASH


class ShareValidator:
    """Validates mining shares."""
    
    def __init__(self, job_manager: JobManager):
        self.job_manager = job_manager
        self.submitted_shares: dict = {}  # job_id -> set of share_ids (extranonce2:nonce)
    
    def validate(self, worker_id: int, job_id: str, share_id: str, submitted_hash: str = None) -> ShareSubmission:
        """
        Validate a share submission.
        
        Args:
            worker_id: The worker submitting the share
            job_id: The job ID this share is for
            share_id: Unique share identifier (extranonce2:nonce)
            submitted_hash: Optional block hash computed by the miner
            
        Returns:
            ShareSubmission with result
        """
        # Extract nonce from share_id
        nonce_hex = share_id.split(':')[-1] if ':' in share_id else share_id
        
        submission = ShareSubmission(
            worker_id=worker_id,
            job_id=job_id,
            nonce=0
        )
        
        # Parse nonce
        try:
            nonce = int(nonce_hex, 16)
            submission.nonce = nonce
        except (ValueError, TypeError):
            submission.result = ShareResult.INVALID_NONCE
            logger.debug(f"Invalid nonce from worker #{worker_id}: {nonce_hex}")
            return submission
        
        # Get job
        job = self.job_manager.get_job(job_id)
        if not job:
            submission.result = ShareResult.STALE_JOB
            logger.debug(f"Stale job {job_id} from worker #{worker_id}")
            return submission
        
        # Check for duplicate using full share_id (extranonce2:nonce)
        if job_id not in self.submitted_shares:
            self.submitted_shares[job_id] = set()
        
        if share_id in self.submitted_shares[job_id]:
            submission.result = ShareResult.DUPLICATE
            logger.debug(f"Duplicate share {share_id} from worker #{worker_id}")
            return submission
        
        # Build full header and hash
        header = job.header76 + struct.pack('<I', nonce)
        hash_result = double_sha256(header)
        hash_int = int.from_bytes(hash_result[::-1], 'big')
        hash_hex = hash_result[::-1].hex()
        
        # Log what we received and computed
        if submitted_hash:
            logger.info(f"Share from #{worker_id}: nonce={nonce:08x}")
            logger.info(f"  Wallet hash:  {submitted_hash[:24]}...")
            logger.info(f"  Pool hash:    {hash_hex[:24]}...")
            if submitted_hash != hash_hex:
                logger.warning(f"  ⚠️ HASH MISMATCH!")
        
        # If miner submitted a hash, check if it's a block candidate
        if submitted_hash:
            try:
                logger.info(f"  submitted_hash len={len(submitted_hash)}: {submitted_hash}")
                submitted_int = int(submitted_hash, 16)
                logger.info(f"  submitted_int: {submitted_int}")
                logger.info(f"  job.target:    {job.target}")
                logger.info(f"  Block check: submitted_int < job.target? {submitted_int < job.target}")
                # Check if this hash meets block target
                if submitted_int < job.target:
                    # Valid block!
                    submission.hash_result = submitted_hash
                    submission.is_block = True
                    submission.result = ShareResult.VALID_BLOCK
                    self.submitted_shares[job_id].add(share_id)
                    logger.info(f"🎉 BLOCK FOUND (wallet hash) by worker #{worker_id}! Hash: {submitted_hash[:32]}...")
                    return submission
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid submitted_hash: {e}")
        
        submission.hash_result = hash_hex
        
        # Check against share target
        share_target = self.job_manager.share_target
        logger.info(f"  hash_int:      {hash_int}")
        logger.info(f"  share_target:  {share_target}")
        logger.info(f"  job.target:    {job.target}")
        logger.info(f"  ratio:         {share_target // job.target}x")
        logger.info(f"  Check: hash_int >= share_target? {hash_int >= share_target}")
        if hash_int >= share_target:
            submission.result = ShareResult.LOW_DIFFICULTY
            logger.info(f"  ❌ LOW_DIFFICULTY - rejected")
            return submission
        
        # Valid share - record share_id
        self.submitted_shares[job_id].add(share_id)
        
        # Check if it's a valid block
        logger.info(f"  Block check: hash_int({len(str(hash_int))}d) < job.target({len(str(job.target))}d)? {hash_int < job.target}")
        if hash_int < job.target:
            submission.is_block = True
            submission.result = ShareResult.VALID_BLOCK
            logger.info(f"🎉 BLOCK FOUND by worker #{worker_id}! Hash: {hash_hex[:32]}...")
        else:
            submission.result = ShareResult.VALID_SHARE
            logger.info(f"  Valid share (not block) - hash_int has more digits")
        
        return submission
    
    def build_block(self, job: MiningJob, nonce: int, block_hash: str) -> dict:
        """Build block data for submission."""
        # Include coinbase + all mempool transactions
        all_transactions = [job.coinbase_tx] + job.mempool_txs
        logger.info(f"Building block with {len(all_transactions)} transactions (1 coinbase + {len(job.mempool_txs)} mempool)")
        return {
            'version': 1,
            'height': job.height,
            'hash': block_hash,
            'previous_hash': job.prev_hash,  # Note: key is 'previous_hash' not 'prev_hash'
            'merkle_root': job.merkle_root,
            'timestamp': job.timestamp,
            'difficulty': job.difficulty,
            'nonce': nonce,
            'transactions': all_transactions,
            'masternode_payee': ''
        }
    
    def cleanup_old_jobs(self, keep_jobs: int = 5):
        """Clean up share tracking for old jobs."""
        current_jobs = set(self.job_manager.jobs.keys())
        old_jobs = set(self.submitted_shares.keys()) - current_jobs
        
        # Keep only recent jobs
        if len(self.submitted_shares) > keep_jobs:
            sorted_jobs = sorted(self.submitted_shares.keys())
            for old_job in sorted_jobs[:-keep_jobs]:
                if old_job in self.submitted_shares:
                    del self.submitted_shares[old_job]
