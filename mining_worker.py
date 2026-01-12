#!/usr/bin/env python3
"""
SALOCOIN GPU Miner - Mining Worker Module
This module contains the worker function that can be pickled for multiprocessing.
"""

import hashlib


def mining_worker(core_id, start_nonce, step, header_prefix, target, found_flag, found_nonce, hash_counts):
    """
    Worker process for mining.
    Must be at module level for Windows multiprocessing compatibility.
    """
    nonce = start_nonce
    count = 0
    
    while found_flag.value == 0 and nonce < 0xFFFFFFFF:
        header = f"{header_prefix}{nonce}"
        hash_bytes = hashlib.sha256(hashlib.sha256(header.encode()).digest()).digest()
        hash_int = int.from_bytes(hash_bytes, 'big')
        
        if hash_int < target:
            found_flag.value = 1
            found_nonce.value = nonce
            hash_counts[core_id] = count
            return
        
        nonce += step
        count += 1
        
        # Update count periodically
        if count % 10000 == 0:
            hash_counts[core_id] = count
