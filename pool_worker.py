#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SALOCOIN Pool Worker - Command Line Pool Mining Client

Usage:
    python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_SALO_ADDRESS --gpu
    python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_SALO_ADDRESS --threads 4
"""

import sys
import os

# Fix Windows console encoding with line buffering for immediate output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
import socket
import json
import hashlib
import struct
import threading
import time
import random
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import GPU miner
HAS_OPENCL = False
try:
    import pyopencl as cl
    import numpy as np
    HAS_OPENCL = True
except ImportError:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# GPU Mining Kernel
# ─────────────────────────────────────────────────────────────────────────────

OPENCL_KERNEL = """
#define SWAP32(x) ((((x) >> 24) & 0xFF) | (((x) >> 8) & 0xFF00) | (((x) << 8) & 0xFF0000) | (((x) << 24) & 0xFF000000))

#define CH(x, y, z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define SIG0(x) (ROTR(x, 2) ^ ROTR(x, 13) ^ ROTR(x, 22))
#define SIG1(x) (ROTR(x, 6) ^ ROTR(x, 11) ^ ROTR(x, 25))
#define sig0(x) (ROTR(x, 7) ^ ROTR(x, 18) ^ ((x) >> 3))
#define sig1(x) (ROTR(x, 17) ^ ROTR(x, 19) ^ ((x) >> 10))

__constant uint K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

inline uint swap32(uint x) { return SWAP32(x); }

inline void sha256_transform(uint *state, const uint *block) {
    uint W[64];
    for (int i = 0; i < 16; i++) W[i] = block[i];
    for (int i = 16; i < 64; i++) W[i] = sig1(W[i-2]) + W[i-7] + sig0(W[i-15]) + W[i-16];
    
    uint a = state[0], b = state[1], c = state[2], d = state[3];
    uint e = state[4], f = state[5], g = state[6], h = state[7];
    
    for (int i = 0; i < 64; i++) {
        uint T1 = h + SIG1(e) + CH(e, f, g) + K[i] + W[i];
        uint T2 = SIG0(a) + MAJ(a, b, c);
        h = g; g = f; f = e; e = d + T1;
        d = c; c = b; b = a; a = T1 + T2;
    }
    
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

__kernel void mine(__global const uchar *header76, ulong target_hi, uint start_nonce,
                   __global uint *result_nonce, __global ulong *best_hash_hi) {
    uint nonce = start_nonce + get_global_id(0);
    
    uchar header[80];
    for (int i = 0; i < 76; i++) header[i] = header76[i];
    header[76] = nonce & 0xFF;
    header[77] = (nonce >> 8) & 0xFF;
    header[78] = (nonce >> 16) & 0xFF;
    header[79] = (nonce >> 24) & 0xFF;
    
    uint state[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                     0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    uint block1[16];
    for (int i = 0; i < 16; i++) {
        block1[i] = ((uint)header[i*4] << 24) | ((uint)header[i*4+1] << 16) |
                    ((uint)header[i*4+2] << 8) | (uint)header[i*4+3];
    }
    sha256_transform(state, block1);
    
    uint block2[16];
    block2[0] = ((uint)header[64] << 24) | ((uint)header[65] << 16) |
                ((uint)header[66] << 8) | (uint)header[67];
    block2[1] = ((uint)header[68] << 24) | ((uint)header[69] << 16) |
                ((uint)header[70] << 8) | (uint)header[71];
    block2[2] = ((uint)header[72] << 24) | ((uint)header[73] << 16) |
                ((uint)header[74] << 8) | (uint)header[75];
    block2[3] = ((uint)header[76] << 24) | ((uint)header[77] << 16) |
                ((uint)header[78] << 8) | (uint)header[79];
    block2[4] = 0x80000000;
    for (int i = 5; i < 15; i++) block2[i] = 0;
    block2[15] = 640;
    sha256_transform(state, block2);
    
    uint state2[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    uint block3[16];
    for (int i = 0; i < 8; i++) block3[i] = state[i];
    block3[8] = 0x80000000;
    for (int i = 9; i < 15; i++) block3[i] = 0;
    block3[15] = 256;
    sha256_transform(state2, block3);
    
    // Get first 8 bytes of display hash (last 8 bytes of raw hash, byte-swapped)
    uint h7 = swap32(state2[7]);
    uint h6 = swap32(state2[6]);
    ulong hash_hi = ((ulong)h7 << 32) | h6;
    
    // Check against target - store any hash below target
    if (hash_hi < target_hi) {
        *result_nonce = nonce;
        *best_hash_hi = hash_hi;
    }
}
"""


class GPUMiner:
    """GPU Mining support using OpenCL"""
    def __init__(self):
        self.device = None
        self.ctx = None
        self.queue = None
        self.program = None
        self.kernel = None
        self.device_name = "No GPU"
        self.batch_size = 2**18  # 262K per batch - smaller to catch more block candidates
        self.available = False
        
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
                self.kernel = self.program.mine
                max_work = self.device.max_work_group_size
                self.batch_size = min(self.batch_size, max_work * 4096)
                self.available = True
                print(f"   GPU: {self.device_name}")
                print(f"   Batch: {self.batch_size:,}")
        except Exception as e:
            print(f"   GPU error: {e}")
            self.available = False
    
    def get_target_hi(self, target):
        """Get upper 64 bits of target for GPU comparison."""
        target_hex = format(target, '064x')
        target_bytes = bytes.fromhex(target_hex)
        return struct.unpack('>Q', target_bytes[:8])[0]
    
    def mine_batch(self, header76_bytes, target, start_nonce):
        """Mine a batch of nonces. Returns (found, winning_nonce, hashes_done)"""
        if not self.available:
            return False, 0, 0
        
        mf = cl.mem_flags
        
        # Convert target to 64-bit for GPU
        target_hi = self.get_target_hi(target)
        
        # Create buffers
        header_buf = cl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=header76_bytes)
        result_nonce = np.array([0], dtype=np.uint32)
        best_hash = np.array([0xFFFFFFFFFFFFFFFF], dtype=np.uint64)
        result_buf = cl.Buffer(self.ctx, mf.READ_WRITE | mf.COPY_HOST_PTR, hostbuf=result_nonce)
        hash_buf = cl.Buffer(self.ctx, mf.READ_WRITE | mf.COPY_HOST_PTR, hostbuf=best_hash)
        
        # Run kernel
        self.kernel(
            self.queue, (self.batch_size,), None,
            header_buf, np.uint64(target_hi), np.uint32(start_nonce),
            result_buf, hash_buf
        )
        
        # Read results
        cl.enqueue_copy(self.queue, result_nonce, result_buf)
        cl.enqueue_copy(self.queue, best_hash, hash_buf)
        
        found = best_hash[0] < 0xFFFFFFFFFFFFFFFF
        return found, int(result_nonce[0]), self.batch_size


class PoolWorker:
    """Pool mining worker for command line"""
    
    def __init__(self, pool_host: str, pool_port: int, address: str, 
                 worker_name: str = "worker1", use_gpu: bool = True, threads: int = 4):
        self.pool_host = pool_host
        self.pool_port = pool_port
        self.address = address
        self.worker_name = worker_name
        self.use_gpu = use_gpu
        self.threads = threads
        
        # Connection state
        self.socket = None
        self.running = False
        self.extranonce1 = ""
        
        # Job state
        self.job = None
        self.job_lock = threading.Lock()
        self.target = 0
        self.difficulty = 1
        
        # Stats
        self.hashes = 0
        self.shares = 0
        self.accepted = 0
        self.rejected = 0
        self.blocks_found = 0
        self.start_time = 0
        
        # GPU miner
        self.gpu_miner = None
        if use_gpu and HAS_OPENCL:
            self.gpu_miner = GPUMiner()
            if not self.gpu_miner.available:
                print("⚠️  GPU not available, falling back to CPU")
                self.use_gpu = False
        elif use_gpu:
            print("⚠️  PyOpenCL not installed, falling back to CPU")
            self.use_gpu = False
    
    def log(self, msg):
        """Print log message with timestamp"""
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")
    
    def connect(self):
        """Connect to pool"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(30)
            self.socket.connect((self.pool_host, self.pool_port))
            self.log(f"✅ Connected to {self.pool_host}:{self.pool_port}")
            return True
        except Exception as e:
            self.log(f"❌ Connection failed: {e}")
            return False
    
    def send(self, msg):
        """Send message to pool"""
        try:
            data = json.dumps(msg) + '\n'
            self.socket.sendall(data.encode())
        except Exception as e:
            self.log(f"Send error: {e}")
    
    def subscribe(self):
        """Subscribe to pool"""
        self.send({'id': 1, 'method': 'mining.subscribe', 'params': ['salocoin-pool-worker/1.0']})
        time.sleep(1.0)
        
        # Read responses
        self.socket.settimeout(5)
        buffer = b''
        while True:
            try:
                chunk = self.socket.recv(8192)
                if not chunk:
                    break
                buffer += chunk
                if len(chunk) < 8192:
                    break
            except socket.timeout:
                break
        
        for line in buffer.split(b'\n'):
            if not line.strip():
                continue
            try:
                msg = json.loads(line.decode())
                if msg.get('id') == 1 and msg.get('result'):
                    self.extranonce1 = msg['result'][1]
                    self.log(f"✅ Subscribed (extranonce: {self.extranonce1})")
                elif msg.get('method') == 'mining.set_target':
                    target_hex = msg['params'][0]
                    self.target = int(target_hex, 16)
                elif msg.get('method') == 'mining.set_difficulty':
                    diff = msg['params'][0]
                    if isinstance(diff, (int, float)):
                        self.difficulty = diff
                        self.target = int(0xFFFF0000 * (2**208) / max(diff, 0.0001))
                elif msg.get('method') == 'mining.notify':
                    self._handle_job(msg['params'])
            except:
                pass
        
        return True
    
    def authorize(self):
        """Authorize with pool"""
        username = f"{self.address}.{self.worker_name}"
        self.send({'id': 2, 'method': 'mining.authorize', 'params': [username, 'x']})
        
        # Wait for auth and job
        for _ in range(10):
            try:
                self.socket.settimeout(0.5)
                data = self.socket.recv(4096)
                if data:
                    for line in data.split(b'\n'):
                        if not line.strip():
                            continue
                        try:
                            msg = json.loads(line.decode())
                            if msg.get('id') == 2 and msg.get('result'):
                                self.log(f"✅ Authorized as {self.worker_name}")
                            elif msg.get('method') == 'mining.notify':
                                self._handle_job(msg['params'])
                            elif msg.get('method') == 'mining.set_target':
                                target_hex = msg['params'][0]
                                self.target = int(target_hex, 16)
                        except:
                            pass
            except:
                pass
            time.sleep(0.5)
        
        return self.job is not None
    
    def _handle_job(self, params):
        """Handle new job from pool"""
        with self.job_lock:
            self.job = {
                'id': params[0],
                'prev_hash': params[1],
                'merkle1': params[2],
                'merkle2': params[3],
                'merkle_branches': params[4],
                'version': params[5],
                'nbits': params[6],
                'ntime': params[7],
                'clean': params[8] if len(params) > 8 else True
            }
        self.log(f"📋 New job: {params[0]}")
    
    def _receiver(self):
        """Receive messages from pool"""
        buffer = b''
        while self.running:
            try:
                self.socket.settimeout(1)
                data = self.socket.recv(4096)
                if not data:
                    self.log("⚠️ Lost connection")
                    break
                
                buffer += data
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    try:
                        msg = json.loads(line.decode())
                        method = msg.get('method', '')
                        
                        if method == 'mining.notify':
                            self._handle_job(msg['params'])
                        elif method == 'mining.set_target':
                            target_hex = msg['params'][0]
                            self.target = int(target_hex, 16)
                            self.log(f"🎯 Share target set")
                        elif method == 'pool.block_found':
                            params = msg.get('params', {})
                            height = params.get('height', '?')
                            finder = params.get('finder', 'Unknown')
                            reward = params.get('reward', 0) / 100000000
                            self.log(f"🎉 BLOCK #{height} FOUND by {finder}!")
                            self.log(f"   Reward: {reward:.8f} SALO")
                        elif method == 'pool.block_accepted':
                            params = msg.get('params', {})
                            height = params.get('height', '?')
                            block_hash = params.get('hash', '')[:32]
                            self.log(f"✅ Block #{height} ACCEPTED!")
                            self.log(f"   Hash: {block_hash}...")
                        elif method == 'pool.block_rejected':
                            params = msg.get('params', {})
                            height = params.get('height', '?')
                            reason = params.get('reason', 'Unknown')
                            self.log(f"❌ Block #{height} REJECTED: {reason}")
                        elif method == 'pool.reward_distributed':
                            params = msg.get('params', {})
                            height = params.get('height', '?')
                            distributions = params.get('distributions', [])
                            for dist in distributions:
                                if dist.get('address', '') == self.address:
                                    my_reward = dist.get('amount', 0) / 100000000
                                    my_shares = dist.get('shares', 0)
                                    self.log(f"💵 YOUR REWARD: {my_reward:.8f} SALO ({my_shares} shares)")
                        elif msg.get('result') == True and msg.get('id', 0) > 2:
                            self.accepted += 1
                        elif msg.get('result') == False and msg.get('id', 0) > 2:
                            self.rejected += 1
                    except:
                        pass
            except socket.timeout:
                continue
            except:
                break
    
    def _mine_gpu(self):
        """GPU mining thread"""
        nonce = random.randint(0, 0x0FFFFFFF)
        
        while self.running:
            with self.job_lock:
                job = self.job
            
            if not job:
                time.sleep(0.1)
                continue
            
            try:
                version = int(job['version'], 16)
                prev_hash = job['prev_hash'].ljust(64, '0')
                prev_bytes = bytes.fromhex(prev_hash)[::-1][:32]
                merkle = (job['merkle1'] + job['merkle2']).ljust(64, '0')
                merkle_bytes = bytes.fromhex(merkle[:64])[::-1][:32]
                ntime = int(job['ntime'], 16)
                nbits = int(job['nbits'], 16)
            except:
                time.sleep(0.5)
                continue
            
            # Calculate targets
            exponent = (nbits >> 24) & 0xFF
            coefficient = nbits & 0x007fffff  # 23-bit mantissa (Bitcoin format)
            if exponent <= 3:
                network_target = coefficient >> (8 * (3 - exponent))
            else:
                network_target = coefficient << (8 * (exponent - 3))
            share_target = network_target * 256
            
            # Build 76-byte header
            header76 = struct.pack('<I', version)
            header76 += prev_bytes
            header76 += merkle_bytes
            header76 += struct.pack('<I', ntime)
            header76 += struct.pack('<I', nbits)
            
            job_id = job['id']
            
            while self.running:
                with self.job_lock:
                    if self.job and self.job['id'] != job_id:
                        break
                
                found, winning_nonce, batch_hashes = self.gpu_miner.mine_batch(header76, share_target, nonce)
                self.hashes += batch_hashes
                nonce = (nonce + batch_hashes) & 0xFFFFFFFF
                
                if found:
                    header = header76 + struct.pack('<I', winning_nonce)
                    hash1 = hashlib.sha256(header).digest()
                    hash2 = hashlib.sha256(hash1).digest()
                    hash_int = int.from_bytes(hash2[::-1], 'big')
                    block_hash = hash2[::-1].hex()
                    
                    if hash_int < network_target:
                        self._submit_share(job, winning_nonce, block_hash, True)
                    elif hash_int < share_target:
                        self._submit_share(job, winning_nonce, block_hash, False)
                
                time.sleep(0.001)
    
    def _mine_cpu(self, thread_id):
        """CPU mining thread"""
        thread_offset = thread_id * (0xFFFFFFFF // self.threads)
        nonce = random.randint(0, 0x0FFFFFFF) + thread_offset
        
        while self.running:
            with self.job_lock:
                job = self.job
            
            if not job:
                time.sleep(0.1)
                continue
            
            try:
                version = int(job['version'], 16)
                prev_hash = job['prev_hash'].ljust(64, '0')
                prev_bytes = bytes.fromhex(prev_hash)[::-1][:32]
                merkle = (job['merkle1'] + job['merkle2']).ljust(64, '0')
                merkle_bytes = bytes.fromhex(merkle[:64])[::-1][:32]
                ntime = int(job['ntime'], 16)
                nbits = int(job['nbits'], 16)
            except:
                time.sleep(0.5)
                continue
            
            # Calculate targets
            exponent = (nbits >> 24) & 0xFF
            coefficient = nbits & 0x007fffff  # 23-bit mantissa (Bitcoin format)
            if exponent <= 3:
                network_target = coefficient >> (8 * (3 - exponent))
            else:
                network_target = coefficient << (8 * (exponent - 3))
            share_target = network_target * 256
            
            header_prefix = struct.pack('<I', version)
            header_prefix += prev_bytes
            header_prefix += merkle_bytes
            header_prefix += struct.pack('<I', ntime)
            header_prefix += struct.pack('<I', nbits)
            
            job_id = job['id']
            local_hashes = 0
            
            while self.running and local_hashes < 10000:
                if local_hashes % 500 == 0:
                    with self.job_lock:
                        if self.job and self.job['id'] != job_id:
                            break
                    time.sleep(0.002)
                
                header = header_prefix + struct.pack('<I', nonce)
                hash1 = hashlib.sha256(header).digest()
                hash2 = hashlib.sha256(hash1).digest()
                hash_int = int.from_bytes(hash2[::-1], 'big')
                block_hash = hash2[::-1].hex()
                
                self.hashes += 1
                local_hashes += 1
                
                if hash_int < network_target:
                    self._submit_share(job, nonce, block_hash, True)
                elif hash_int < share_target:
                    self._submit_share(job, nonce, block_hash, False)
                
                nonce = (nonce + 1) & 0xFFFFFFFF
            
            time.sleep(0.005)
    
    def _submit_share(self, job, nonce, block_hash, is_block):
        """Submit share to pool"""
        self.shares += 1
        
        if is_block:
            self.blocks_found += 1
            self.log(f"🎉 BLOCK CANDIDATE! Hash: {block_hash[:24]}...")
        
        # Create extranonce2
        extranonce2 = f"{random.randint(0, 0xFFFFFFFF):08x}"
        
        # Submit
        submit_msg = {
            'id': 100 + self.shares,
            'method': 'mining.submit',
            'params': [
                f"{self.address}.{self.worker_name}",
                job['id'],
                extranonce2,
                job['ntime'],
                f"{nonce:08x}",
                block_hash
            ]
        }
        self.send(submit_msg)
    
    def _stats_printer(self):
        """Print stats periodically"""
        while self.running:
            time.sleep(30)
            elapsed = time.time() - self.start_time
            hashrate = self.hashes / elapsed if elapsed > 0 else 0
            
            if hashrate >= 1_000_000_000:
                hr_str = f"{hashrate/1_000_000_000:.2f} GH/s"
            elif hashrate >= 1_000_000:
                hr_str = f"{hashrate/1_000_000:.2f} MH/s"
            elif hashrate >= 1_000:
                hr_str = f"{hashrate/1_000:.2f} KH/s"
            else:
                hr_str = f"{hashrate:.0f} H/s"
            
            self.log(f"📊 {hr_str} | Shares: {self.accepted}/{self.shares} | Blocks: {self.blocks_found}")
    
    def run(self):
        """Main run loop"""
        print()
        print("=" * 50)
        print("        SALOCOIN Pool Mining Worker")
        print("=" * 50)
        print()
        print(f"Pool:    {self.pool_host}:{self.pool_port}")
        print(f"Address: {self.address}")
        print(f"Worker:  {self.worker_name}")
        print(f"Mode:    {'GPU' if self.use_gpu else f'CPU ({self.threads} threads)'}")
        print()
        
        if not self.connect():
            return
        
        if not self.subscribe():
            self.log("❌ Subscribe failed")
            return
        
        if not self.authorize():
            self.log("❌ No job received")
            return
        
        self.running = True
        self.start_time = time.time()
        
        # Start receiver
        threading.Thread(target=self._receiver, daemon=True).start()
        
        # Start mining
        if self.use_gpu:
            self.log(f"⛏️  Starting GPU mining: {self.gpu_miner.device_name}")
            threading.Thread(target=self._mine_gpu, daemon=True).start()
        else:
            self.log(f"⛏️  Starting {self.threads} CPU mining threads")
            for i in range(self.threads):
                threading.Thread(target=self._mine_cpu, args=(i,), daemon=True).start()
        
        # Start stats printer
        threading.Thread(target=self._stats_printer, daemon=True).start()
        
        print("\nPress Ctrl+C to stop mining.\n")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.log("Stopping...")
            self.running = False
        
        # Final stats
        elapsed = time.time() - self.start_time
        hashrate = self.hashes / elapsed if elapsed > 0 else 0
        
        print(f"""
╔══════════════════════════════════════════════════════════╗
║                    Mining Summary                        ║
╠══════════════════════════════════════════════════════════╣
║  Time:           {elapsed/60:.1f} minutes                         
║  Hashrate:       {hashrate/1_000_000:.2f} MH/s                    
║  Shares:         {self.accepted}/{self.shares} accepted          
║  Blocks Found:   {self.blocks_found}                              
╚══════════════════════════════════════════════════════════╝
""")


def main():
    parser = argparse.ArgumentParser(
        description='SALOCOIN Pool Mining Worker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  GPU Mining:
    python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_ADDRESS --gpu
    
  CPU Mining (4 threads):
    python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_ADDRESS --threads 4
    
  With custom worker name:
    python pool_worker.py --pool pool.salocoin.org:7261 --address YOUR_ADDRESS --worker MyPC --gpu
"""
    )
    
    parser.add_argument('--pool', '-p', required=True, help='Pool address (host:port)')
    parser.add_argument('--address', '-a', required=True, help='SALO payout address')
    parser.add_argument('--worker', '-w', default='worker1', help='Worker name (default: worker1)')
    parser.add_argument('--gpu', '-g', action='store_true', help='Use GPU mining')
    parser.add_argument('--threads', '-t', type=int, default=4, help='CPU threads (default: 4)')
    
    args = parser.parse_args()
    
    # Parse pool address (handle stratum+tcp:// prefix)
    pool_addr = args.pool
    if pool_addr.startswith('stratum+tcp://'):
        pool_addr = pool_addr.replace('stratum+tcp://', '')
    elif pool_addr.startswith('stratum://'):
        pool_addr = pool_addr.replace('stratum://', '')
    
    if ':' in pool_addr:
        host, port = pool_addr.split(':')
        port = int(port)
    else:
        host = pool_addr
        port = 7261
    
    worker = PoolWorker(
        pool_host=host,
        pool_port=port,
        address=args.address,
        worker_name=args.worker,
        use_gpu=args.gpu,
        threads=args.threads
    )
    
    worker.run()


if __name__ == '__main__':
    main()
