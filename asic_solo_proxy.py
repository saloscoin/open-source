#!/usr/bin/env python3
"""
SALOCOIN ASIC Solo Mining Proxy

This proxy allows ASICs to solo mine SALOCOIN.
It speaks Stratum protocol to ASICs and HTTP to the seed node.

Usage:
    python asic_solo_proxy.py --address YOUR_SALO_ADDRESS --port 3333

ASIC Config:
    Pool URL:     stratum+tcp://YOUR_SERVER_IP:3333
    Worker:       anything
    Password:     x
"""

import socket
import threading
import json
import time
import hashlib
import struct
import requests
import argparse
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

# Configuration
SEED_NODE = "https://api.salocoin.org"
COIN_UNIT = 100_000_000


def double_sha256(data: bytes) -> bytes:
    """Double SHA-256 hash."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def compact_to_target(bits: int) -> int:
    """Convert compact bits to full target."""
    exponent = bits >> 24
    mantissa = bits & 0x007fffff
    if exponent <= 3:
        return mantissa >> (8 * (3 - exponent))
    return mantissa << (8 * (exponent - 3))


def target_to_hex(target: int) -> str:
    """Convert target to 64-char hex string."""
    return format(target, '064x')


def swap_endian_words(hex_str: str) -> str:
    """Swap endianness of each 4-byte word."""
    result = ""
    for i in range(0, len(hex_str), 8):
        word = hex_str[i:i+8]
        result += ''.join(reversed([word[j:j+2] for j in range(0, 8, 2)]))
    return result


def build_coinbase(address: str, height: int, reward: int, extranonce1: str, extranonce2: str) -> bytes:
    """Build coinbase transaction."""
    # Simple coinbase - pays full reward to miner address
    coinbase = b'\x01\x00\x00\x00'  # Version
    coinbase += b'\x01'  # Input count
    
    # Coinbase input
    coinbase += b'\x00' * 32  # Previous tx (null)
    coinbase += b'\xff\xff\xff\xff'  # Previous index
    
    # Script sig with height and extranonces
    height_bytes = height.to_bytes((height.bit_length() + 7) // 8 or 1, 'little')
    script_sig = bytes([len(height_bytes)]) + height_bytes
    script_sig += bytes.fromhex(extranonce1)
    script_sig += bytes.fromhex(extranonce2)
    script_sig += b'\x00' * (100 - len(script_sig))  # Padding
    
    coinbase += bytes([len(script_sig)]) + script_sig
    coinbase += b'\xff\xff\xff\xff'  # Sequence
    
    # Output
    coinbase += b'\x01'  # Output count
    coinbase += struct.pack('<Q', reward)  # Amount
    
    # P2PKH script for address
    from core.crypto import address_to_pubkey_hash
    pubkey_hash = address_to_pubkey_hash(address)
    script_pubkey = b'\x76\xa9\x14' + pubkey_hash + b'\x88\xac'
    coinbase += bytes([len(script_pubkey)]) + script_pubkey
    
    coinbase += b'\x00\x00\x00\x00'  # Locktime
    
    return coinbase


@dataclass
class MiningJob:
    """Mining job for ASIC."""
    job_id: str
    prev_hash: str
    coinbase1: str
    coinbase2: str
    merkle_branches: list
    version: str
    nbits: str
    ntime: str
    clean: bool = True
    height: int = 0
    target: int = 0
    block_template: dict = None


@dataclass 
class ASICClient:
    """Connected ASIC miner."""
    socket: socket.socket
    address: tuple
    client_id: int = 0
    subscribed: bool = False
    authorized: bool = False
    extranonce1: str = ""
    extranonce2_size: int = 4
    worker_name: str = ""
    worker_address: str = ""  # SALO address for rewards
    difficulty: float = 1.0
    shares: int = 0
    recv_buffer: bytes = b""
    current_job: MiningJob = None  # Per-client job with their address


class ASICSoloProxy:
    """
    Solo mining proxy for ASICs.
    Speaks Stratum to ASICs, HTTP to seed node.
    """
    
    def __init__(self, address: str, port: int = 3333, seed_url: str = SEED_NODE):
        self.miner_address = address
        self.port = port
        self.seed_url = seed_url
        
        self._running = False
        self._server_socket = None
        self._clients: Dict[int, ASICClient] = {}
        self._client_counter = 0
        self._extranonce_counter = 0
        self._lock = threading.Lock()
        
        self._current_job: Optional[MiningJob] = None
        self._job_counter = 0
        
        print(f"""
╔══════════════════════════════════════════════════════════╗
║           SALOCOIN ASIC Solo Mining Proxy                ║
╚══════════════════════════════════════════════════════════╝

Default Address: {address}
Stratum Port:    {port}
Seed Node:       {seed_url}

ASIC Configuration:
  Pool URL:    stratum+tcp://YOUR_IP:{port}
  Worker:      YOUR_SALO_ADDRESS (rewards go here!)
  Password:    x

NOTE: Each ASIC uses their Worker name as reward address.
      If invalid address, falls back to default: {address}

Starting...
""")
    
    def start(self):
        """Start the proxy server."""
        self._running = True
        
        # Start job updater
        job_thread = threading.Thread(target=self._job_update_loop)
        job_thread.daemon = True
        job_thread.start()
        
        # Create server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(("0.0.0.0", self.port))
        self._server_socket.listen(100)
        self._server_socket.settimeout(1.0)
        
        print(f"✓ Stratum server listening on port {self.port}")
        print(f"✓ Waiting for ASIC connections...\n")
        
        # Accept connections
        while self._running:
            try:
                client_socket, addr = self._server_socket.accept()
                client = self._create_client(client_socket, addr)
                print(f"⚡ ASIC connected from {addr[0]}:{addr[1]}")
                
                thread = threading.Thread(target=self._handle_client, args=(client,))
                thread.daemon = True
                thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    print(f"Accept error: {e}")
    
    def _create_client(self, sock: socket.socket, address: tuple) -> ASICClient:
        """Create new ASIC client."""
        with self._lock:
            self._client_counter += 1
            self._extranonce_counter += 1
            
            client = ASICClient(
                socket=sock,
                address=address,
                client_id=self._client_counter,
                extranonce1=format(self._extranonce_counter, '08x'),
                extranonce2_size=4
            )
            
            self._clients[client.client_id] = client
            return client
    
    def _handle_client(self, client: ASICClient):
        """Handle ASIC client messages."""
        try:
            while self._running:
                # Receive data
                try:
                    data = client.socket.recv(4096)
                    if not data:
                        break
                    client.recv_buffer += data
                except socket.timeout:
                    continue
                except:
                    break
                
                # Process messages
                while b'\n' in client.recv_buffer:
                    line, client.recv_buffer = client.recv_buffer.split(b'\n', 1)
                    if line:
                        self._process_message(client, line.decode('utf-8', errors='ignore'))
                        
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            self._disconnect_client(client)
    
    def _process_message(self, client: ASICClient, message: str):
        """Process Stratum message from ASIC."""
        try:
            msg = json.loads(message)
            method = msg.get('method', '')
            msg_id = msg.get('id')
            params = msg.get('params', [])
            
            if method == 'mining.subscribe':
                self._handle_subscribe(client, msg_id, params)
            elif method == 'mining.authorize':
                self._handle_authorize(client, msg_id, params)
            elif method == 'mining.submit':
                self._handle_submit(client, msg_id, params)
            elif method == 'mining.extranonce.subscribe':
                self._send(client, {'id': msg_id, 'result': True, 'error': None})
                
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Message error: {e}")
    
    def _handle_subscribe(self, client: ASICClient, msg_id: int, params: list):
        """Handle mining.subscribe."""
        client.subscribed = True
        
        result = [
            [["mining.notify", client.extranonce1], ["mining.set_difficulty", client.extranonce1]],
            client.extranonce1,
            client.extranonce2_size
        ]
        
        self._send(client, {'id': msg_id, 'result': result, 'error': None})
        
        # Set difficulty (high for ASICs)
        self._send(client, {
            'id': None,
            'method': 'mining.set_difficulty',
            'params': [65536]  # High difficulty for ASICs
        })
        
        # Send current job
        if self._current_job:
            self._send_job(client, self._current_job)
    
    def _handle_authorize(self, client: ASICClient, msg_id: int, params: list):
        """Handle mining.authorize - worker name should be SALO address."""
        worker = params[0] if params else "unknown"
        client.worker_name = worker
        
        # Validate if worker name is a valid SALO address
        from core.crypto import address_to_pubkey_hash
        try:
            address_to_pubkey_hash(worker)
            client.worker_address = worker
            print(f"  ✓ ASIC authorized: {worker}")
            print(f"    Rewards will go to: {worker}")
        except:
            # Invalid address - use default
            client.worker_address = self.miner_address
            print(f"  ✓ ASIC authorized: {worker}")
            print(f"    ⚠️  Invalid address, using default: {self.miner_address}")
        
        client.authorized = True
        self._send(client, {'id': msg_id, 'result': True, 'error': None})
        
        # Send personalized job with their address
        self._send_personalized_job(client)
    
    def _handle_submit(self, client: ASICClient, msg_id: int, params: list):
        """Handle mining.submit - ASIC found a solution!"""
        if len(params) < 5:
            self._send(client, {'id': msg_id, 'result': False, 'error': [21, "Invalid params"]})
            return
        
        worker_name, job_id, extranonce2, ntime, nonce = params[:5]
        
        print(f"\n⛏️  Share received from {client.worker_name}")
        print(f"   Reward address: {client.worker_address}")
        print(f"   Job: {job_id}, Nonce: {nonce}")
        
        # Use client's personalized job (has their address in coinbase)
        job = client.current_job
        if not job or job.job_id != job_id:
            print(f"   ❌ Stale job")
            self._send(client, {'id': msg_id, 'result': False, 'error': [21, "Stale job"]})
            return
        
        # Build and verify block
        try:
            block = self._build_block(
                job,
                client.extranonce1,
                extranonce2,
                ntime,
                nonce
            )
            
            # Check if meets network difficulty
            block_hash = double_sha256(block[:80])
            hash_int = int.from_bytes(block_hash, 'little')
            
            if hash_int <= job.target:
                print(f"   🎉 BLOCK FOUND! Submitting to network...")
                print(f"   💰 Reward (100 SALO) → {client.worker_address}")
                
                # Submit to seed node
                if self._submit_block(block):
                    print(f"   ✅ BLOCK ACCEPTED! Height: {job.height}")
                    client.shares += 1
                    self._send(client, {'id': msg_id, 'result': True, 'error': None})
                    
                    # Get new job immediately for all clients
                    self._update_all_jobs()
                else:
                    print(f"   ❌ Block rejected by network")
                    self._send(client, {'id': msg_id, 'result': False, 'error': [20, "Block rejected"]})
            else:
                # Valid share but not a block
                client.shares += 1
                print(f"   ✓ Valid share (not a block)")
                self._send(client, {'id': msg_id, 'result': True, 'error': None})
                
        except Exception as e:
            print(f"   ❌ Submit error: {e}")
            self._send(client, {'id': msg_id, 'result': False, 'error': [20, str(e)]})
    
    def _build_block(self, job: MiningJob, extranonce1: str, extranonce2: str, ntime: str, nonce: str) -> bytes:
        """Build full block from job and ASIC solution."""
        # Build coinbase
        coinbase = bytes.fromhex(job.coinbase1) + bytes.fromhex(extranonce1) + bytes.fromhex(extranonce2) + bytes.fromhex(job.coinbase2)
        coinbase_hash = double_sha256(coinbase)
        
        # Build merkle root
        merkle_root = coinbase_hash
        for branch in job.merkle_branches:
            merkle_root = double_sha256(merkle_root + bytes.fromhex(branch))
        
        # Build header
        header = struct.pack('<I', int(job.version, 16))
        header += bytes.fromhex(swap_endian_words(job.prev_hash))[::-1]
        header += merkle_root
        header += struct.pack('<I', int(ntime, 16))
        header += struct.pack('<I', int(job.nbits, 16))
        header += struct.pack('<I', int(nonce, 16))
        
        # Full block = header + tx count + coinbase
        block = header
        block += b'\x01'  # tx count (just coinbase for solo)
        block += coinbase
        
        return block
    
    def _submit_block(self, block: bytes) -> bool:
        """Submit block to seed node."""
        try:
            # Convert block to dict format expected by API
            header = block[:80]
            
            version = struct.unpack('<I', header[0:4])[0]
            prev_hash = header[4:36][::-1].hex()
            merkle_root = header[36:68].hex()
            timestamp = struct.unpack('<I', header[68:72])[0]
            bits = struct.unpack('<I', header[72:76])[0]
            nonce = struct.unpack('<I', header[76:80])[0]
            
            block_hash = double_sha256(header)[::-1].hex()
            
            # Parse coinbase
            coinbase_raw = block[81:]  # Skip header + tx count
            
            block_data = {
                'hash': block_hash,
                'height': self._current_job.height,
                'version': version,
                'prev_hash': prev_hash,
                'merkle_root': merkle_root,
                'timestamp': timestamp,
                'difficulty': bits,
                'nonce': nonce,
                'transactions': [{
                    'txid': double_sha256(coinbase_raw).hex(),
                    'inputs': [{'txid': '0' * 64, 'vout': 0xffffffff}],
                    'outputs': [{'address': self.miner_address, 'amount': 100 * COIN_UNIT}]
                }]
            }
            
            response = requests.post(
                f"{self.seed_url}/submit_block",
                json=block_data,
                timeout=10
            )
            
            result = response.json()
            return result.get('success', False)
            
        except Exception as e:
            print(f"Submit error: {e}")
            return False
    
    def _job_update_loop(self):
        """Periodically update mining job."""
        while self._running:
            try:
                self._update_all_jobs()
            except Exception as e:
                print(f"Job update error: {e}")
            time.sleep(5)  # Update every 5 seconds
    
    def _get_chain_status(self):
        """Get current chain status from seed node."""
        response = requests.get(f"{self.seed_url}/status", timeout=10)
        status = response.json()
        
        height = status.get('height', 0) + 1
        prev_hash = status.get('best_block') or status.get('last_block_hash', '0' * 64)
        bits = status.get('difficulty') or status.get('current_difficulty', 0x1d00ffff)
        target = compact_to_target(bits)
        
        return height, prev_hash, bits, target
    
    def _create_job_for_address(self, miner_address: str, height: int, prev_hash: str, bits: int, target: int) -> MiningJob:
        """Create a mining job for a specific address."""
        self._job_counter += 1
        job_id = format(self._job_counter, 'x')
        
        # Build coinbase parts
        coinbase1 = "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff"
        height_hex = format(height, 'x')
        if len(height_hex) % 2:
            height_hex = '0' + height_hex
        height_len = format(len(height_hex) // 2, '02x')
        coinbase1 += height_len + height_hex
        
        # coinbase2 = extranonce space + output to THIS miner's address
        coinbase2 = "ffffffff01"
        reward = 100 * COIN_UNIT
        coinbase2 += format(reward, '016x')[::-1]  # Little endian reward
        
        # P2PKH output to THIS miner's address
        from core.crypto import address_to_pubkey_hash
        pubkey_hash = address_to_pubkey_hash(miner_address).hex()
        coinbase2 += "1976a914" + pubkey_hash + "88ac"
        coinbase2 += "00000000"  # Locktime
        
        return MiningJob(
            job_id=job_id,
            prev_hash=swap_endian_words(prev_hash),
            coinbase1=coinbase1,
            coinbase2=coinbase2,
            merkle_branches=[],
            version=format(1, '08x'),
            nbits=format(bits, '08x'),
            ntime=format(int(time.time()), '08x'),
            clean=True,
            height=height,
            target=target
        )
    
    def _send_personalized_job(self, client: ASICClient):
        """Send a personalized job to a specific client with their reward address."""
        try:
            height, prev_hash, bits, target = self._get_chain_status()
            
            # Create job with THIS client's address
            job = self._create_job_for_address(
                client.worker_address,
                height, prev_hash, bits, target
            )
            
            client.current_job = job
            self._send_job(client, job)
            
        except Exception as e:
            print(f"Error sending personalized job: {e}")
    
    def _update_all_jobs(self):
        """Update jobs for all connected clients."""
        try:
            height, prev_hash, bits, target = self._get_chain_status()
            
            # Check if new block (use default job to track)
            if self._current_job and self._current_job.height == height:
                return  # No new block
            
            # Update default job (for reference)
            self._current_job = self._create_job_for_address(
                self.miner_address, height, prev_hash, bits, target
            )
            
            # Update each client with their personalized job
            with self._lock:
                for client in self._clients.values():
                    if client.subscribed and client.authorized:
                        job = self._create_job_for_address(
                            client.worker_address or self.miner_address,
                            height, prev_hash, bits, target
                        )
                        client.current_job = job
                        self._send_job(client, job)
            
            print(f"📦 New job: Height {height}, Difficulty: {bits:08x}")
            
        except Exception as e:
            print(f"Job update error: {e}")
    
    def _update_job(self):
        """Legacy: Update job (now calls _update_all_jobs)."""
        self._update_all_jobs()
    
    def _send_job(self, client: ASICClient, job: MiningJob):
        """Send mining job to ASIC."""
        params = [
            job.job_id,
            job.prev_hash,
            job.coinbase1,
            job.coinbase2,
            job.merkle_branches,
            job.version,
            job.nbits,
            job.ntime,
            job.clean
        ]
        
        self._send(client, {
            'id': None,
            'method': 'mining.notify',
            'params': params
        })
    
    def _send(self, client: ASICClient, message: dict):
        """Send message to ASIC."""
        try:
            data = json.dumps(message) + '\n'
            client.socket.send(data.encode())
        except:
            pass
    
    def _disconnect_client(self, client: ASICClient):
        """Disconnect ASIC client."""
        try:
            client.socket.close()
        except:
            pass
        
        with self._lock:
            if client.client_id in self._clients:
                del self._clients[client.client_id]
        
        print(f"📴 ASIC disconnected: {client.address[0]} (Shares: {client.shares})")


def main():
    parser = argparse.ArgumentParser(description='SALOCOIN ASIC Solo Mining Proxy')
    parser.add_argument('--address', '-a', required=True, help='Your SALO address for rewards')
    parser.add_argument('--port', '-p', type=int, default=3333, help='Stratum port (default: 3333)')
    parser.add_argument('--seed', '-s', default=SEED_NODE, help='Seed node URL')
    
    args = parser.parse_args()
    
    proxy = ASICSoloProxy(
        address=args.address,
        port=args.port,
        seed_url=args.seed
    )
    
    try:
        proxy.start()
    except KeyboardInterrupt:
        print("\n\nShutting down...")


if __name__ == '__main__':
    main()
