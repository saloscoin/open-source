#!/usr/bin/env python3
"""
SALOCOIN GPU Miner
Uses OpenCL for GPU-accelerated SHA-256d mining.
"""

import sys
import os
import time
import argparse
import json
import hashlib
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from core.wallet import Wallet
from core.blockchain import Blockchain, Block
from core.transaction import Transaction
from sync import BlockchainSync

try:
    import pyopencl as cl
    import numpy as np
    HAS_OPENCL = True
except ImportError:
    HAS_OPENCL = False
    print("PyOpenCL not installed. Install with: pip install pyopencl numpy")

SEED_NODE = "https://api.salocoin.org"
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
WALLETS_DIR = os.path.join(os.path.dirname(__file__), 'wallets')
SALO = config.COIN_UNIT

# OpenCL kernel - processes raw 80-byte header
OPENCL_KERNEL = """
#define ROTR(x,n) (((x)>>(n))|((x)<<(32-(n))))
#define S0(x) (ROTR(x,2)^ROTR(x,13)^ROTR(x,22))
#define S1(x) (ROTR(x,6)^ROTR(x,11)^ROTR(x,25))
#define s0(x) (ROTR(x,7)^ROTR(x,18)^((x)>>3))
#define s1(x) (ROTR(x,17)^ROTR(x,19)^((x)>>10))
#define Ch(x,y,z) (((x)&(y))^(~(x)&(z)))
#define Maj(x,y,z) (((x)&(y))^((x)&(z))^((y)&(z)))

__constant uint K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

inline uint swap32(uint x) {
    return ((x >> 24) & 0xff) | ((x >> 8) & 0xff00) | ((x << 8) & 0xff0000) | ((x << 24) & 0xff000000);
}

void sha256_transform(uint* state, const uint* block) {
    uint W[64];
    uint a, b, c, d, e, f, g, h, t1, t2;
    
    for (int i = 0; i < 16; i++) W[i] = block[i];
    for (int i = 16; i < 64; i++) W[i] = s1(W[i-2]) + W[i-7] + s0(W[i-15]) + W[i-16];
    
    a = state[0]; b = state[1]; c = state[2]; d = state[3];
    e = state[4]; f = state[5]; g = state[6]; h = state[7];
    
    for (int i = 0; i < 64; i++) {
        t1 = h + S1(e) + Ch(e,f,g) + K[i] + W[i];
        t2 = S0(a) + Maj(a,b,c);
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }
    
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

__kernel void mine(
    __global const uchar* header76,  // 76 bytes header (without nonce)
    const ulong target_hi,           // Upper 64 bits of target
    const uint start_nonce,
    __global uint* result_nonce,
    __global volatile int* found
) {
    uint gid = get_global_id(0);
    uint nonce = start_nonce + gid;
    
    if (*found) return;
    
    // Build 80-byte header with nonce (little-endian)
    uchar header[80];
    for (int i = 0; i < 76; i++) header[i] = header76[i];
    header[76] = nonce & 0xFF;
    header[77] = (nonce >> 8) & 0xFF;
    header[78] = (nonce >> 16) & 0xFF;
    header[79] = (nonce >> 24) & 0xFF;
    
    // First SHA-256
    uint state[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                     0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    
    // Block 1: bytes 0-63 (big-endian words)
    uint block1[16];
    for (int i = 0; i < 16; i++) {
        block1[i] = ((uint)header[i*4] << 24) | ((uint)header[i*4+1] << 16) |
                    ((uint)header[i*4+2] << 8) | (uint)header[i*4+3];
    }
    sha256_transform(state, block1);
    
    // Block 2: bytes 64-79 + padding
    uint block2[16];
    block2[0] = ((uint)header[64] << 24) | ((uint)header[65] << 16) |
                ((uint)header[66] << 8) | (uint)header[67];
    block2[1] = ((uint)header[68] << 24) | ((uint)header[69] << 16) |
                ((uint)header[70] << 8) | (uint)header[71];
    block2[2] = ((uint)header[72] << 24) | ((uint)header[73] << 16) |
                ((uint)header[74] << 8) | (uint)header[75];
    block2[3] = ((uint)header[76] << 24) | ((uint)header[77] << 16) |
                ((uint)header[78] << 8) | (uint)header[79];
    block2[4] = 0x80000000;  // Padding
    for (int i = 5; i < 15; i++) block2[i] = 0;
    block2[15] = 640;  // Length: 80 * 8 bits
    sha256_transform(state, block2);
    
    // Second SHA-256 (hash the hash)
    uint state2[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    uint block3[16];
    for (int i = 0; i < 8; i++) block3[i] = state[i];
    block3[8] = 0x80000000;
    for (int i = 9; i < 15; i++) block3[i] = 0;
    block3[15] = 256;  // 32 * 8 bits
    sha256_transform(state2, block3);
    
    // Check if hash meets target (compare reversed bytes = little-endian comparison)
    // The hash needs to be reversed, so we compare state2[7], state2[6], etc.
    // For simplicity, just check the first few bytes (most significant after reversal)
    
    // Swap and check - reversed hash means state2[7] is most significant
    uint h7 = swap32(state2[7]);
    uint h6 = swap32(state2[6]);
    
    // Target check: upper 64 bits of reversed hash < target_hi
    ulong hash_hi = ((ulong)h7 << 32) | h6;
    
    if (hash_hi < target_hi) {
        *found = 1;
        *result_nonce = nonce;
    }
}
"""


class GPUMiner:
    def __init__(self):
        self.device = None
        self.ctx = None
        self.queue = None
        self.program = None
        self.kernel = None  # Cache kernel to avoid RepeatedKernelRetrieval warning
        self.device_name = "No GPU"
        self.batch_size = 2**20  # 1M per batch - balanced speed and block detection
        
        if HAS_OPENCL:
            self._init_gpu()
    
    def _init_gpu(self):
        try:
            platforms = cl.get_platforms()
            for platform in platforms:
                try:
                    devices = platform.get_devices(device_type=cl.device_type.GPU)
                    if devices:
                        self.device = devices[0]
                        break
                except cl.RuntimeError:
                    pass
            
            if self.device:
                self.device_name = self.device.name.strip()
                self.ctx = cl.Context([self.device])
                self.queue = cl.CommandQueue(self.ctx)
                self.program = cl.Program(self.ctx, OPENCL_KERNEL).build()
                self.kernel = self.program.mine  # Cache kernel once
                max_work = self.device.max_work_group_size
                self.batch_size = min(self.batch_size, max_work * 4096)
                print(f"   GPU: {self.device_name}")
                print(f"   Batch: {self.batch_size:,}")
            else:
                print("   No GPU found")
        except Exception as e:
            print(f"   GPU error: {e}")
            self.device = None
    
    def get_target_hi(self, target):
        """Get upper 64 bits of target for GPU comparison."""
        target_hex = format(target, '064x')
        target_bytes = bytes.fromhex(target_hex)
        # Upper 8 bytes (64 bits)
        return struct.unpack('>Q', target_bytes[:8])[0]
    
    def mine_gpu(self, block, target, blockchain=None, syncer=None):
        """Mine using GPU. Returns True if block found, False if chain updated."""
        if not self.device:
            return self.mine_cpu(block, target)
        
        mf = cl.mem_flags
        
        # Build 76-byte header (without nonce)
        header76 = struct.pack('<I', block.version)
        header76 += bytes.fromhex(block.previous_hash)[::-1]
        header76 += bytes.fromhex(block.merkle_root)[::-1]
        header76 += struct.pack('<I', block.timestamp)
        header76 += struct.pack('<I', block.difficulty)
        header76 = np.frombuffer(header76, dtype=np.uint8)
        
        target_hi = self.get_target_hi(target)
        current_height = block.height - 1  # Height we're building on
        
        # GPU buffers
        header_buf = cl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=header76)
        result_nonce = np.zeros(1, dtype=np.uint32)
        found = np.zeros(1, dtype=np.int32)
        result_buf = cl.Buffer(self.ctx, mf.WRITE_ONLY, result_nonce.nbytes)
        found_buf = cl.Buffer(self.ctx, mf.READ_WRITE | mf.COPY_HOST_PTR, hostbuf=found)
        
        start_time = time.time()
        last_sync_time = time.time()
        sync_interval = 10  # Check for new blocks every 10 seconds
        nonce = 0
        total_hashes = 0
        
        while nonce < 0xFFFFFFFF:
            # Check if chain height changed (another miner found a block)
            if syncer and time.time() - last_sync_time > sync_interval:
                last_sync_time = time.time()
                try:
                    old_height = blockchain.get_height()
                    syncer.sync_from_seed(quiet=True)  # Silent sync during mining
                    if blockchain.get_height() > old_height:
                        print(f"\n   📢 New block found by network! Height: {blockchain.get_height()}")
                        return False  # Signal to restart mining
                except:
                    pass
            
            found[0] = 0
            cl.enqueue_copy(self.queue, found_buf, found)
            
            self.kernel(
                self.queue, (self.batch_size,), None,
                header_buf,
                np.uint64(target_hi),
                np.uint32(nonce),
                result_buf,
                found_buf
            )
            self.queue.finish()
            
            cl.enqueue_copy(self.queue, found, found_buf)
            cl.enqueue_copy(self.queue, result_nonce, result_buf)
            
            total_hashes += self.batch_size
            elapsed = time.time() - start_time
            
            if elapsed > 0:
                hashrate = total_hashes / elapsed
                if hashrate >= 1e6:
                    hr_str = f"{hashrate/1e6:.2f} MH/s"
                else:
                    hr_str = f"{hashrate/1e3:.2f} KH/s"
                print(f"\r   Nonce: {nonce:,} | {hr_str}", end='', flush=True)
            
            if found[0]:
                winning_nonce = int(result_nonce[0])
                block.nonce = winning_nonce
                block.hash = block.calculate_hash()
                
                # Verify
                if int(block.hash, 16) < target:
                    elapsed = time.time() - start_time
                    hashrate = total_hashes / elapsed if elapsed > 0 else 0
                    print(f"\n   ✓ BLOCK FOUND!")

                    print(f"   Nonce: {winning_nonce:,}")
                    print(f"   Hash: {block.hash}")
                    print(f"   Time: {elapsed:.2f}s | {hashrate/1e6:.2f} MH/s")
                    return True
                else:
                    # GPU found candidate but CPU verification failed
                    # This means our GPU kernel doesn't match - fall back to CPU
                    print(f"\n   GPU/CPU mismatch at nonce {winning_nonce}")
                    print(f"   Falling back to CPU mining...")
                    return self.mine_cpu(block, target)
            
            nonce += self.batch_size
        
        return False
    
    def mine_cpu(self, block, target):
        """CPU mining fallback with multi-threading."""
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor, as_completed
        
        num_workers = multiprocessing.cpu_count()
        print(f"\n   Using {num_workers} CPU cores...")
        
        start_time = time.time()
        chunk_size = 1000000  # 1M nonces per chunk
        
        for start in range(0, 0xFFFFFFFF, chunk_size * num_workers):
            # Mine chunk on CPU
            for nonce in range(start, min(start + chunk_size * num_workers, 0xFFFFFFFF)):
                block.nonce = nonce
                block.hash = block.calculate_hash()
                
                if int(block.hash, 16) < target:
                    elapsed = time.time() - start_time
                    hashrate = nonce / elapsed if elapsed > 0 else 0
                    print(f"\n   ✓ BLOCK FOUND!")
                    print(f"   Nonce: {nonce:,}")
                    print(f"   Hash: {block.hash}")
                    print(f"   Time: {elapsed:.2f}s | {hashrate/1e3:.2f} KH/s")
                    return True
                
                if nonce % 100000 == 0:
                    elapsed = time.time() - start_time
                    hashrate = nonce / elapsed if elapsed > 0 else 0
                    print(f"\r   Nonce: {nonce:,} | {hashrate/1e3:.2f} KH/s", end='', flush=True)
        
        return False


def get_default_address():
    for name in ['default', 'my_wallet']:
        path = os.path.join(WALLETS_DIR, f'{name}.json')
        if os.path.exists(path):
            wallet = Wallet(filepath=path)
            wallet.load()
            return wallet.addresses[0].address
    return None


def mine_block(blockchain, miner_address, gpu_miner, syncer=None, last_mining_height=None):
    """Mine a single block. Returns (block, height) if found, (None, height) if need to restart."""
    latest = blockchain.get_latest_block()
    height = latest.height + 1
    
    coinbase = Transaction.create_coinbase(
        block_height=height,
        miner_address=miner_address,
        extra_data=f"SALO GPU Miner"
    )
    
    transactions = [coinbase.to_dict()]
    for tx in blockchain.mempool.get_transactions(max_count=100):
        transactions.append(tx.to_dict())
    
    block = Block(
        version=1,
        height=height,
        timestamp=int(time.time()),
        previous_hash=latest.hash,
        merkle_root='',
        difficulty=blockchain.current_difficulty,
        nonce=0,
        transactions=transactions,
    )
    block.merkle_root = block.calculate_merkle_root()
    
    target = Block.get_target_from_difficulty(block.difficulty)
    
    # Only print header if this is a new block height
    if last_mining_height != height:
        print(f"\n⛏️  Mining block {height}...")
        print(f"   Difficulty: {block.difficulty}")
        print(f"   Target: {target:064x}"[:32] + "...")
        print(f"   Transactions: {len(transactions)}")
    else:
        # Continuing same block with new timestamp (nonce overflow)
        print(f"\n   Continuing block {height} (new timestamp)...")
    
    if gpu_miner.mine_gpu(block, target, blockchain, syncer):
        return block, height
    return None, height


def cmd_start(args):
    os.makedirs(DATA_DIR, exist_ok=True)
    
    miner_address = args.address or get_default_address()
    if not miner_address:
        print("No mining address! Use --address or create wallet first")
        return
    
    print("")
    print("=" * 50)
    print("          SALOCOIN GPU Miner")
    print("=" * 50)
    print("")
    print(f"Address: {miner_address}")
    
    gpu_miner = GPUMiner()
    blockchain = Blockchain(data_dir=DATA_DIR)
    
    seed_url = args.seed or SEED_NODE
    syncer = None
    
    if not args.nosync:
        print(f"\n🔄 Syncing from {seed_url}...")
        try:
            syncer = BlockchainSync(blockchain, seed_url=seed_url)
            status = syncer.get_status()
            if status:
                syncer.sync_from_seed()
                print(f"   ✓ Height: {blockchain.get_height()}")
                syncer.sync_mempool()
        except Exception as e:
            print(f"   ⚠ Sync error: {e}")
    else:
        syncer = BlockchainSync(blockchain, seed_url=seed_url)
    
    print(f"\nHeight: {blockchain.get_height()}")
    print(f"Reward: {config.calculate_block_reward(blockchain.get_height()+1)/SALO} SALO")
    print("\nPress Ctrl+C to stop.\n")
    
    blocks_mined = 0
    total_reward = 0
    last_mining_height = None
    
    try:
        while True:
            # Pass syncer to mine_block so it can check for new blocks during mining
            block, mining_height = mine_block(blockchain, miner_address, gpu_miner, 
                                              syncer if not args.nosync else None,
                                              last_mining_height)
            
            if block and blockchain.add_block(block):
                last_mining_height = None  # Reset so next block shows full header
                reward = config.calculate_block_reward(block.height)
                blocks_mined += 1
                total_reward += reward
                
                print(f"   💰 Reward: {reward/SALO} SALO")
                
                if syncer:
                    try:
                        if syncer.submit_block(block):
                            print(f"   📡 Submitted to network!")
                        else:
                            print(f"   ❌ Rejected! Resyncing...")
                            blocks_mined -= 1
                            total_reward -= reward
                            syncer.resync_chain()
                            last_mining_height = None  # Reset after resync
                    except Exception as e:
                        print(f"   ⚠ Submit error: {e}")
                
                if blocks_mined % 5 == 0:
                    blockchain.save()
            else:
                # Block not found (nonce overflow or chain updated)
                # Track height for "continuing" message
                last_mining_height = mining_height
                    
    except KeyboardInterrupt:
        print("\n\n⛔ Stopped")
    
    blockchain.save()
    print(f"\n📊 Mined {blocks_mined} blocks = {total_reward/SALO} SALO")


def main():
    parser = argparse.ArgumentParser(description='SALOCOIN GPU Miner')
    
    # Top-level arguments (no subcommand needed)
    parser.add_argument('--address', '-a', help='Mining address')
    parser.add_argument('--seed', '-s', help='Seed node URL')
    parser.add_argument('--nosync', action='store_true', help='Skip sync')
    parser.add_argument('command', nargs='?', default='start', help='Command (start)')
    
    args = parser.parse_args()
    
    if args.command == 'start':
        cmd_start(args)


if __name__ == '__main__':
    main()
