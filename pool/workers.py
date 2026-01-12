"""
Worker Management for SALOCOIN Pool
Tracks connected workers, their stats, and authentication.
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class Worker:
    """Represents a connected mining worker."""
    id: int
    socket: Any
    address: str  # Remote IP:port
    wallet_address: Optional[str] = None
    worker_name: str = "default"
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    shares_accepted: int = 0
    shares_rejected: int = 0
    shares_stale: int = 0
    blocks_found: int = 0
    authorized: bool = False
    difficulty: float = 1.0
    
    @property
    def uptime(self) -> int:
        """Worker uptime in seconds."""
        return int(time.time() - self.connected_at)
    
    @property
    def share_rate(self) -> float:
        """Shares per minute."""
        uptime_min = max(self.uptime / 60, 1)
        return self.shares_accepted / uptime_min
    
    @property
    def reject_rate(self) -> float:
        """Rejection rate as percentage."""
        total = self.shares_accepted + self.shares_rejected
        if total == 0:
            return 0.0
        return (self.shares_rejected / total) * 100
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API."""
        return {
            'id': self.id,
            'address': self.wallet_address or 'unauthorized',
            'name': self.worker_name,
            'connected_at': self.connected_at,
            'uptime': self.uptime,
            'shares_accepted': self.shares_accepted,
            'shares_rejected': self.shares_rejected,
            'shares_stale': self.shares_stale,
            'blocks_found': self.blocks_found,
            'share_rate': round(self.share_rate, 2),
            'reject_rate': round(self.reject_rate, 2),
            'difficulty': self.difficulty,
            'authorized': self.authorized
        }


class WorkerManager:
    """Manages all connected workers."""
    
    def __init__(self):
        self.workers: Dict[int, Worker] = {}
        self.lock = threading.RLock()
        self._next_id = 1
    
    def add_worker(self, socket: Any, address: str) -> Worker:
        """Register a new worker connection."""
        with self.lock:
            worker_id = self._next_id
            self._next_id += 1
            
            worker = Worker(
                id=worker_id,
                socket=socket,
                address=address
            )
            self.workers[worker_id] = worker
            logger.info(f"Worker #{worker_id} connected from {address}")
            return worker
    
    def remove_worker(self, worker_id: int) -> Optional[Worker]:
        """Remove a worker connection."""
        with self.lock:
            worker = self.workers.pop(worker_id, None)
            if worker:
                logger.info(f"Worker #{worker_id} disconnected ({worker.wallet_address or 'unauthorized'})")
            return worker
    
    def get_worker(self, worker_id: int) -> Optional[Worker]:
        """Get worker by ID."""
        with self.lock:
            return self.workers.get(worker_id)
    
    def get_worker_by_socket(self, socket: Any) -> Optional[Worker]:
        """Get worker by socket."""
        with self.lock:
            for worker in self.workers.values():
                if worker.socket is socket:
                    return worker
        return None
    
    def authorize_worker(self, worker_id: int, wallet_address: str, worker_name: str = "default") -> bool:
        """Authorize a worker with wallet address."""
        with self.lock:
            worker = self.workers.get(worker_id)
            if worker:
                worker.wallet_address = wallet_address
                worker.worker_name = worker_name
                worker.authorized = True
                logger.info(f"Worker #{worker_id} authorized: {wallet_address}/{worker_name}")
                return True
            return False
    
    def record_share(self, worker_id: int, accepted: bool, is_block: bool = False, stale: bool = False):
        """Record a share submission."""
        with self.lock:
            worker = self.workers.get(worker_id)
            if worker:
                worker.last_activity = time.time()
                if stale:
                    worker.shares_stale += 1
                elif accepted:
                    worker.shares_accepted += 1
                    if is_block:
                        worker.blocks_found += 1
                else:
                    worker.shares_rejected += 1
    
    def get_authorized_workers(self) -> list:
        """Get list of authorized workers."""
        with self.lock:
            return [w for w in self.workers.values() if w.authorized]
    
    def get_all_workers(self) -> list:
        """Get all workers."""
        with self.lock:
            return list(self.workers.values())
    
    def get_worker_count(self) -> int:
        """Get count of authorized workers."""
        with self.lock:
            return sum(1 for w in self.workers.values() if w.authorized)
    
    def get_total_shares(self) -> int:
        """Get total accepted shares across all workers."""
        with self.lock:
            return sum(w.shares_accepted for w in self.workers.values())
    
    def get_shares_by_address(self) -> Dict[str, int]:
        """Get shares grouped by wallet address."""
        with self.lock:
            shares = {}
            for worker in self.workers.values():
                if worker.wallet_address:
                    shares[worker.wallet_address] = shares.get(worker.wallet_address, 0) + worker.shares_accepted
            return shares
    
    def reset_shares(self):
        """Reset all worker share counts (after payout)."""
        with self.lock:
            for worker in self.workers.values():
                worker.shares_accepted = 0
                worker.shares_rejected = 0
                worker.shares_stale = 0
    
    def get_stats(self) -> dict:
        """Get aggregate worker statistics."""
        with self.lock:
            authorized = [w for w in self.workers.values() if w.authorized]
            return {
                'total_connections': len(self.workers),
                'authorized_workers': len(authorized),
                'total_shares': sum(w.shares_accepted for w in self.workers.values()),
                'total_rejected': sum(w.shares_rejected for w in self.workers.values()),
                'total_blocks': sum(w.blocks_found for w in self.workers.values()),
                'workers': [w.to_dict() for w in authorized]
            }
    
    def broadcast(self, message: bytes):
        """Broadcast message to all workers."""
        with self.lock:
            for worker in list(self.workers.values()):
                try:
                    worker.socket.send(message)
                except Exception as e:
                    logger.debug(f"Failed to send to worker #{worker.id}: {e}")
    
    def cleanup_inactive(self, timeout: int = 300):
        """Remove workers inactive for longer than timeout seconds."""
        now = time.time()
        to_remove = []
        
        with self.lock:
            for worker_id, worker in self.workers.items():
                if now - worker.last_activity > timeout:
                    to_remove.append(worker_id)
        
        for worker_id in to_remove:
            self.remove_worker(worker_id)
            logger.info(f"Removed inactive worker #{worker_id}")
