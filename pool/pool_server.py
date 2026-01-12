"""
SALOCOIN Mining Pool Server
Stratum-compatible pool server with modular components.
"""

import sys
import os
import json
import time
import socket
import signal
import threading
import argparse
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .workers import WorkerManager, Worker
from .job_manager import JobManager
from .share import ShareValidator, ShareResult
from .payout import PayoutManager

try:
    import config
    COIN_UNIT = config.COIN_UNIT
except ImportError:
    COIN_UNIT = 100000000


class PoolServer:
    """
    SALOCOIN Mining Pool Server
    
    Accepts miner connections via Stratum protocol,
    validates shares, and distributes rewards.
    """
    
    # Dynamic pool fee configuration
    POOL_FEE_MIN = 1.0       # Minimum pool fee (%)
    POOL_FEE_MAX = 10.0      # Maximum pool fee (%)
    POOL_FEE_BASE = 5.0      # Base fee before adjustments (%)
    
    # Worker thresholds for fee reduction (halving-style)
    WORKER_THRESHOLDS = [
        (1, 10.0),    # 1 worker = 10% fee
        (2, 8.0),     # 2 workers = 8% fee
        (5, 5.0),     # 5 workers = 5% fee
        (10, 3.0),    # 10 workers = 3% fee
        (20, 2.0),    # 20 workers = 2% fee
        (50, 1.5),    # 50 workers = 1.5% fee
        (100, 1.0),   # 100+ workers = 1% fee (minimum)
    ]
    
    def __init__(self, 
                 pool_address: str,
                 pool_privkey: str,
                 stratum_port: int = 7261,
                 http_port: int = 7262,
                 seed_url: str = "https://api.salocoin.org",
                 fee_percent: float = 5.0,
                 dynamic_fee: bool = True):
        
        self.pool_address = pool_address
        self.stratum_port = stratum_port
        self.http_port = http_port
        self.seed_url = seed_url
        self.base_fee_percent = fee_percent
        self.dynamic_fee = dynamic_fee
        
        # Current dynamic fee (updated periodically)
        self._current_fee = fee_percent
        
        # Components
        self.workers = WorkerManager()
        self.jobs = JobManager(pool_address, seed_url)
        self.shares = ShareValidator(self.jobs)
        self.payouts = PayoutManager(pool_address, pool_privkey, seed_url, fee_percent)
        
        # State
        self.running = False
        self.start_time = time.time()
        
        # Stats
        self.blocks_found = 0
        self.blocks_accepted = 0
        
        logger.info(f"Pool initialized: {pool_address}")
        logger.info(f"Dynamic fee: {'Enabled' if dynamic_fee else 'Disabled'} (base: {fee_percent}%)")
    
    @property
    def fee_percent(self) -> float:
        """Get current pool fee (dynamic or static)."""
        if self.dynamic_fee:
            return self._current_fee
        return self.base_fee_percent
    
    def calculate_dynamic_fee(self) -> float:
        """
        Calculate dynamic pool fee based on worker count.
        
        More workers = Lower fee (volume discount / halving style)
        
        Returns:
            Current pool fee percentage (1-10%)
        """
        worker_count = len(self.workers.get_authorized_workers())
        
        # Find appropriate fee tier based on worker count
        fee = self.POOL_FEE_MAX
        for threshold, tier_fee in self.WORKER_THRESHOLDS:
            if worker_count >= threshold:
                fee = tier_fee
            else:
                break
        
        # Clamp to min/max bounds
        fee = max(self.POOL_FEE_MIN, min(self.POOL_FEE_MAX, fee))
        
        return fee
    
    def update_dynamic_fee(self):
        """Update the current dynamic fee and payout manager."""
        if not self.dynamic_fee:
            return
        
        old_fee = self._current_fee
        self._current_fee = self.calculate_dynamic_fee()
        
        # Update payout manager with new fee
        self.payouts.fee_percent = self._current_fee
        
        if old_fee != self._current_fee:
            worker_count = len(self.workers.get_authorized_workers())
            logger.info(f"📊 Dynamic fee updated: {old_fee}% → {self._current_fee}% ({worker_count} workers)")
    
    def start(self):
        """Start the pool server."""
        self.running = True
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Create initial job
        self.jobs.create_job(force=True)
        
        # Start threads
        threading.Thread(target=self._run_stratum, daemon=True).start()
        threading.Thread(target=self._run_http, daemon=True).start()
        threading.Thread(target=self._job_updater, daemon=True).start()
        threading.Thread(target=self._stats_printer, daemon=True).start()
        threading.Thread(target=self._payout_sender, daemon=True).start()
        threading.Thread(target=self._fee_updater, daemon=True).start()
        threading.Thread(target=self._periodic_stats_saver, daemon=True).start()
        
        logger.info(f"Stratum server on port {self.stratum_port}")
        logger.info(f"HTTP API on port {self.http_port}")
        logger.info(f"Mining at height {self.jobs.height + 1}")
        
        # Keep main thread alive
        while self.running:
            time.sleep(1)
    
    def stop(self):
        """Stop the pool server."""
        self.running = False
        logger.info("Pool shutting down...")
        
        # Save pending payouts before shutdown
        try:
            self.payouts._save_stats()
            logger.info("✅ Saved payout stats before shutdown")
        except Exception as e:
            logger.error(f"❌ Failed to save payout stats: {e}")
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals."""
        self.stop()
    
    # ─────────────────────────────────────────────────────────────
    # Stratum Server
    # ─────────────────────────────────────────────────────────────
    
    def _run_stratum(self):
        """Run the Stratum TCP server."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', self.stratum_port))
        server.listen(100)
        server.settimeout(1)
        
        while self.running:
            try:
                conn, addr = server.accept()
                threading.Thread(
                    target=self._handle_connection,
                    args=(conn, addr),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Accept error: {e}")
        
        server.close()
    
    def _handle_connection(self, conn: socket.socket, addr: tuple):
        """Handle a single miner connection."""
        worker = self.workers.add_worker(conn, f"{addr[0]}:{addr[1]}")
        
        buffer = b''
        last_activity = time.time()
        try:
            while self.running:
                conn.settimeout(30)  # 30s timeout for more responsive keepalive
                try:
                    data = conn.recv(4096)
                    if not data:
                        break
                    
                    last_activity = time.time()
                    buffer += data
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        try:
                            msg = json.loads(line.decode())
                            self._handle_message(worker, msg)
                        except json.JSONDecodeError:
                            pass
                except socket.timeout:
                    # Send keepalive ping if no activity for 30s
                    if time.time() - last_activity > 25:
                        try:
                            ping = json.dumps({'id': None, 'method': 'mining.ping', 'params': []}) + '\n'
                            conn.send(ping.encode())
                        except:
                            break
                    continue
        except Exception as e:
            logger.debug(f"Connection error for worker #{worker.id}: {e}")
        finally:
            self.workers.remove_worker(worker.id)
            conn.close()
    
    def _handle_message(self, worker: Worker, msg: dict):
        """Handle a Stratum message from a worker."""
        msg_id = msg.get('id')
        method = msg.get('method', '')
        params = msg.get('params', [])
        
        logger.info(f"Worker #{worker.id} -> {method}: {params}")
        
        if method == 'mining.subscribe':
            self._send(worker, {
                'id': msg_id,
                'result': [[], "", 4],  # subscriptions, extranonce1, extranonce2_size
                'error': None
            })
        
        elif method == 'mining.authorize':
            self._handle_authorize(worker, msg_id, params)
        
        elif method == 'mining.submit':
            self._handle_submit(worker, msg_id, params)
        
        elif method == 'mining.extranonce.subscribe':
            self._send(worker, {'id': msg_id, 'result': True, 'error': None})
    
    def _handle_authorize(self, worker: Worker, msg_id: int, params: list):
        """Handle mining.authorize message."""
        logger.info(f"Worker #{worker.id} authorize attempt: {params}")
        if not params:
            self._send(worker, {'id': msg_id, 'result': False, 'error': "No address"})
            return
        
        full_name = params[0]
        if '.' in full_name:
            address, name = full_name.split('.', 1)
        else:
            address = full_name
            name = 'default'
        
        # Validate address
        if not address.startswith('S') or len(address) < 30:
            self._send(worker, {'id': msg_id, 'result': False, 'error': "Invalid address"})
            return
        
        self.workers.authorize_worker(worker.id, address, name)
        self._send(worker, {'id': msg_id, 'result': True, 'error': None})
        
        # Send current job
        self._send_job(worker)
    
    def _handle_submit(self, worker: Worker, msg_id: int, params: list):
        """Handle mining.submit message."""
        if not worker.authorized:
            self._send(worker, {'id': msg_id, 'result': False, 'error': "Not authorized"})
            return
        
        # Parse params: [worker_name, job_id, extranonce2, ntime, nonce, ?block_hash]
        if len(params) < 5:
            self._send(worker, {'id': msg_id, 'result': False, 'error': "Invalid params"})
            return
        
        job_id = params[1]
        extranonce2 = params[2]
        nonce = params[4]
        submitted_hash = params[5] if len(params) > 5 else None
        
        # Create unique share identifier (job + extranonce2 + nonce)
        share_id = f"{extranonce2}:{nonce}"
        
        # Validate share
        submission = self.shares.validate(worker.id, job_id, share_id, submitted_hash)
        
        if submission.result == ShareResult.VALID_BLOCK:
            # Block found!
            logger.info(f"🎉🎉🎉 BLOCK FOUND! Hash: {submission.hash_result[:32]}...")
            self.blocks_found += 1
            self.workers.record_share(worker.id, True, is_block=True)
            
            # Build and submit block
            job = self.jobs.get_job(job_id)
            if job:
                logger.info(f"Building block for height {job.height}...")
                block = self.shares.build_block(job, submission.nonce, submission.hash_result)
                logger.info(f"Submitting block to network...")
                accepted = self._submit_block(block, worker)
                
                if accepted:
                    logger.info(f"✅ Block ACCEPTED! Processing payouts...")
                    self.blocks_accepted += 1
                    # Process payouts
                    shares_by_address = self.workers.get_shares_by_address()
                    self.payouts.process_block_reward(job.reward, shares_by_address)
                    self.workers.reset_shares()
                    
                    # Notify workers
                    self._broadcast_block_found(job.height, worker)
                    
                    # Create new job
                    self.jobs.create_job(force=True)
                    self._broadcast_job()
            
            self._send(worker, {'id': msg_id, 'result': True, 'error': None})
        
        elif submission.result == ShareResult.VALID_SHARE:
            self.workers.record_share(worker.id, True)
            self._send(worker, {'id': msg_id, 'result': True, 'error': None})
        
        elif submission.result == ShareResult.STALE_JOB:
            logger.info(f"❌ STALE share from #{worker.id}: job={job_id}")
            self.workers.record_share(worker.id, False, stale=True)
            self._send(worker, {'id': msg_id, 'result': False, 'error': "Stale job"})
        
        else:
            logger.info(f"❌ REJECTED share from #{worker.id}: {submission.result.value}")
            self.workers.record_share(worker.id, False)
            self._send(worker, {'id': msg_id, 'result': False, 'error': str(submission.result.value)})
    
    def _submit_block(self, block: dict, finder: Worker) -> bool:
        """Submit a block to the network."""
        try:
            logger.info(f"Submitting block #{block['height']} to network...")
            logger.info(f"  Hash: {block['hash'][:32]}...")
            logger.info(f"  Nonce: {block['nonce']}")
            
            resp = requests.post(
                f"{self.seed_url}/submit_block",
                json=block,
                timeout=30
            )
            
            logger.info(f"  Response: {resp.status_code}")
            
            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"  Result: {result}")
                if result.get('accepted') or result.get('success'):
                    logger.info(f"✅ Block #{block['height']} ACCEPTED!")
                    return True
                logger.warning(f"❌ Block rejected: {result.get('error')}")
            else:
                logger.error(f"Block submit failed: HTTP {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Block submit error: {e}")
        
        return False
    
    def _send(self, worker: Worker, msg: dict):
        """Send a message to a worker."""
        try:
            data = json.dumps(msg) + '\n'
            worker.socket.send(data.encode())
        except Exception as e:
            logger.debug(f"Send error to worker #{worker.id}: {e}")
    
    def _send_job(self, worker: Worker):
        """Send current job to a worker."""
        notify = self.jobs.get_stratum_notify()
        if notify:
            self._send(worker, notify)
            self._send(worker, self.jobs.get_stratum_target())
    
    def _broadcast_job(self):
        """Broadcast current job to all workers."""
        notify = self.jobs.get_stratum_notify()
        target = self.jobs.get_stratum_target()
        
        if notify:
            for worker in self.workers.get_authorized_workers():
                self._send(worker, notify)
                self._send(worker, target)
    
    def _broadcast_block_found(self, height: int, finder: Worker):
        """Notify all workers that a block was found."""
        msg = {
            'id': None,
            'method': 'pool.block_found',
            'params': {
                'height': height,
                'finder': finder.worker_name,
                'reward': self.jobs.current_job.reward if self.jobs.current_job else 0
            }
        }
        for worker in self.workers.get_authorized_workers():
            self._send(worker, msg)
    
    # ─────────────────────────────────────────────────────────────
    # Job Updater
    # ─────────────────────────────────────────────────────────────
    
    def _job_updater(self):
        """Periodically update jobs when new blocks are found."""
        while self.running:
            old_height = self.jobs.height
            job = self.jobs.create_job()
            
            if job and self.jobs.height != old_height:
                logger.info(f"📦 New block detected, updating to height {self.jobs.height + 1}")
                self._broadcast_job()
            
            time.sleep(5)
    
    def _payout_sender(self):
        """Periodically send pending payouts."""
        while self.running:
            time.sleep(60)  # Check every 60 seconds
            try:
                # Log payout check attempt
                pending_count = len(self.payouts.pending_payouts)
                pending_total = sum(p.amount for p in self.payouts.pending_payouts.values()) / 100_000_000
                logger.info(f"💰 Payout check: {pending_count} pending ({pending_total:.2f} SALO)")
                
                results = self.payouts.send_payouts()
                for addr, amount, success, result in results:
                    amount_salo = amount / 100_000_000
                    if success:
                        logger.info(f"💸 Sent payout: {amount_salo:.8f} SALO to {addr[:20]}...")
                    else:
                        logger.error(f"❌ Payout failed to {addr[:20]}...: {result}")
                
                # Always save stats after payout attempts (even if some failed)
                # This ensures pending payouts persist across restarts
                if results:
                    self.payouts._save_stats()
            except Exception as e:
                logger.error(f"Payout sender error: {e}")
    
    def _fee_updater(self):
        """Periodically update dynamic pool fee based on worker count."""
        while self.running:
            try:
                self.update_dynamic_fee()
            except Exception as e:
                logger.error(f"Fee updater error: {e}")
            time.sleep(30)  # Update fee every 30 seconds
    
    def _periodic_stats_saver(self):
        """Periodically save payout stats to prevent data loss."""
        while self.running:
            time.sleep(300)  # Save every 5 minutes
            try:
                self.payouts._save_stats()
                logger.debug("💾 Periodic stats save completed")
            except Exception as e:
                logger.error(f"Periodic stats save error: {e}")
    
    # ─────────────────────────────────────────────────────────────
    # HTTP API
    # ─────────────────────────────────────────────────────────────
    
    def _run_http(self):
        """Run HTTP stats API."""
        pool = self
        
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                stats = pool._get_stats()
                self.wfile.write(json.dumps(stats).encode())
        
        server = HTTPServer(('0.0.0.0', self.http_port), Handler)
        
        while self.running:
            server.handle_request()
        
        server.shutdown()
    
    def _get_stats(self) -> dict:
        """Get pool statistics."""
        uptime = int(time.time() - self.start_time)
        worker_stats = self.workers.get_stats()
        payout_stats = self.payouts.get_stats()
        
        # Estimate hashrate from shares
        total_shares = worker_stats['total_shares']
        if uptime > 0 and total_shares > 0:
            hashes_per_share = (2**32) / self.jobs.share_multiplier
            hashrate = int((total_shares * hashes_per_share) / uptime)
        else:
            hashrate = 0
        
        if hashrate >= 1e9:
            hashrate_str = f"{hashrate/1e9:.2f} GH/s"
        elif hashrate >= 1e6:
            hashrate_str = f"{hashrate/1e6:.2f} MH/s"
        elif hashrate >= 1e3:
            hashrate_str = f"{hashrate/1e3:.2f} KH/s"
        else:
            hashrate_str = f"{hashrate} H/s"
        
        # Get worker count for fee tier info
        worker_count = worker_stats['authorized_workers']
        
        # Determine next fee tier
        next_tier_workers = None
        next_tier_fee = None
        for threshold, tier_fee in self.WORKER_THRESHOLDS:
            if worker_count < threshold:
                next_tier_workers = threshold
                next_tier_fee = tier_fee
                break
        
        return {
            'pool_online': True,
            'pool_address': self.pool_address,
            'pool_fee': self.fee_percent,
            'pool_fee_dynamic': self.dynamic_fee,
            'pool_fee_min': self.POOL_FEE_MIN,
            'pool_fee_max': self.POOL_FEE_MAX,
            'next_fee_tier': {
                'workers_needed': next_tier_workers,
                'fee_percent': next_tier_fee
            } if next_tier_workers else None,
            'height': self.jobs.height,
            'difficulty': self.jobs.difficulty,
            'hashrate': hashrate,
            'hashrate_formatted': hashrate_str,
            'hashrate_str': hashrate_str,
            'uptime': uptime,
            'connected_workers': worker_stats['authorized_workers'],
            'authorized_workers': worker_stats['authorized_workers'],
            'total_connections': worker_stats['total_connections'],
            'total_shares': worker_stats['total_shares'],
            'total_rejected': worker_stats['total_rejected'],
            'blocks_found': self.blocks_found,
            'blocks_accepted': self.blocks_accepted,
            'total_rewards': payout_stats['total_paid'] / COIN_UNIT,
            'total_rewards_formatted': payout_stats['total_paid_formatted'],
            'pending_payouts': self.payouts.get_pending_payouts(),
            'workers': worker_stats['workers']
        }
    
    def _stats_printer(self):
        """Periodically print stats to console."""
        while self.running:
            time.sleep(30)
            stats = self._get_stats()
            fee_str = f"{stats['pool_fee']}%" if self.dynamic_fee else f"{stats['pool_fee']}% (fixed)"
            logger.info(
                f"[Pool] Workers: {stats['connected_workers']} | "
                f"Fee: {fee_str} | "
                f"Shares: {stats['total_shares']} | "
                f"Blocks: {stats['blocks_found']}/{stats['blocks_accepted']} | "
                f"Hashrate: {stats['hashrate_str']}"
            )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='SALOCOIN Mining Pool')
    parser.add_argument('--address', '-a', required=True, help='Pool wallet address')
    parser.add_argument('--privkey', '-k', default='', help='Pool private key (optional)')
    parser.add_argument('--port', '-p', type=int, default=7261, help='Stratum port')
    parser.add_argument('--http', type=int, default=7262, help='HTTP API port')
    parser.add_argument('--seed', '-s', default='https://api.salocoin.org', help='Seed URL')
    parser.add_argument('--fee', '-f', type=float, default=5.0, help='Base pool fee %% (default: 5)')
    parser.add_argument('--dynamic-fee', '-d', action='store_true', default=True,
                        help='Enable dynamic fee (1-10%% based on worker count)')
    parser.add_argument('--fixed-fee', action='store_true', default=False,
                        help='Disable dynamic fee, use fixed fee')
    
    args = parser.parse_args()
    
    # Determine if dynamic fee is enabled
    dynamic_fee = not args.fixed_fee
    
    fee_mode = "DYNAMIC (1-10%%)" if dynamic_fee else f"FIXED ({args.fee}%%)"
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║           SALOCOIN MINING POOL                           ║
╠══════════════════════════════════════════════════════════╣
║  Address: {args.address[:40]}...
║  Fee Mode: {fee_mode}
║  Stratum: 0.0.0.0:{args.port}
║  HTTP: 0.0.0.0:{args.http}
╠══════════════════════════════════════════════════════════╣
║  DYNAMIC FEE TIERS (more workers = lower fee):           ║
║    1 worker  = 10%%  │  5 workers  = 5%%                  ║
║    10 workers = 3%%  │  20 workers = 2%%                  ║
║    50 workers = 1.5%% │ 100+ workers = 1%%                 ║
╚══════════════════════════════════════════════════════════╝
""")
    
    pool = PoolServer(
        pool_address=args.address,
        pool_privkey=args.privkey,
        stratum_port=args.port,
        http_port=args.http,
        seed_url=args.seed,
        fee_percent=args.fee,
        dynamic_fee=dynamic_fee
    )
    
    pool.start()


if __name__ == '__main__':
    main()
