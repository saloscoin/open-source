#!/usr/bin/env python3
"""
SALOCOIN Daemon CLI
Manage the SALOCOIN node daemon.

Usage:
    salocoind start       Start the node daemon
    salocoind stop        Stop the daemon
    salocoind status      Check daemon status
    salocoind getinfo     Get blockchain info
    salocoind sync        Sync blockchain from seed
"""

import sys
import os
import argparse
import json
import time
import signal
import subprocess

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from core.blockchain import Blockchain
from sync import BlockchainSync

SEED_NODE = "https://api.salocoin.org"
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
PID_FILE = os.path.join(DATA_DIR, 'salocoind.pid')
SALO = config.COIN_UNIT


def is_daemon_running():
    """Check if daemon is running."""
    if not os.path.exists(PID_FILE):
        return False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists (Windows compatible)
        if sys.platform == 'win32':
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except (OSError, ValueError):
        # Process not running, clean up pid file
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        return False


def cmd_start(args):
    """Start the daemon."""
    if is_daemon_running():
        print("❌ Daemon is already running")
        return
    
    os.makedirs(DATA_DIR, exist_ok=True)
    
    print("🚀 Starting SALOCOIN daemon...")
    
    # Start the RPC server in background
    if sys.platform == 'win32':
        # Windows - use subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'salocoind.py')
        proc = subprocess.Popen(
            [sys.executable, script_path, '--daemon'],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Save PID
        with open(PID_FILE, 'w') as f:
            f.write(str(proc.pid))
        
        time.sleep(1)
        print(f"✓ Daemon started (PID: {proc.pid})")
        print(f"  RPC server: http://localhost:{config.RPC_PORT}")
    else:
        # Unix - use fork
        pid = os.fork()
        if pid == 0:
            # Child process
            os.setsid()
            
            # Run daemon
            from rpc.server import RPCServer
            blockchain = Blockchain(data_dir=DATA_DIR)
            syncer = BlockchainSync(blockchain, seed_url=SEED_NODE)
            syncer.start()
            
            server = RPCServer(blockchain)
            server.start()
        else:
            # Parent process
            with open(PID_FILE, 'w') as f:
                f.write(str(pid))
            
            time.sleep(1)
            print(f"✓ Daemon started (PID: {pid})")
            print(f"  RPC server: http://localhost:{config.RPC_PORT}")


def cmd_stop(args):
    """Stop the daemon."""
    if not is_daemon_running():
        print("❌ Daemon is not running")
        return
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        print(f"Stopping daemon (PID: {pid})...")
        
        if sys.platform == 'win32':
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(1, False, pid)  # PROCESS_TERMINATE
            if handle:
                kernel32.TerminateProcess(handle, 0)
                kernel32.CloseHandle(handle)
        else:
            os.kill(pid, signal.SIGTERM)
        
        os.remove(PID_FILE)
        print("✓ Daemon stopped")
    except Exception as e:
        print(f"❌ Failed to stop daemon: {e}")


def cmd_status(args):
    """Check daemon status."""
    print("\n🔍 SALOCOIN Daemon Status")
    print("═" * 50)
    
    if is_daemon_running():
        with open(PID_FILE, 'r') as f:
            pid = f.read().strip()
        print(f"  Status: ✓ Running (PID: {pid})")
    else:
        print(f"  Status: ✗ Not running")
    
    # Check local blockchain
    if os.path.exists(DATA_DIR):
        blockchain = Blockchain(data_dir=DATA_DIR)
        print(f"  Local Height: {blockchain.get_height()}")
    else:
        print(f"  Local Height: 0 (no data)")
    
    # Check seed node
    try:
        blockchain = Blockchain(data_dir=DATA_DIR) if os.path.exists(DATA_DIR) else Blockchain()
        syncer = BlockchainSync(blockchain, seed_url=SEED_NODE)
        status = syncer.get_status()
        if status:
            print(f"  Network Height: {status.get('height', 0)}")
            print(f"  Seed Node: ✓ Online")
        else:
            print(f"  Seed Node: ✗ Offline")
    except:
        print(f"  Seed Node: ✗ Unreachable")
    
    print()


def cmd_getinfo(args):
    """Get blockchain info."""
    os.makedirs(DATA_DIR, exist_ok=True)
    blockchain = Blockchain(data_dir=DATA_DIR)
    
    latest = blockchain.get_latest_block()
    
    info = {
        "version": config.PROTOCOL_VERSION,
        "network": config.NETWORK_NAME,
        "height": blockchain.get_height(),
        "difficulty": blockchain.current_difficulty,
        "best_block": latest.hash if latest else None,
        "block_reward": config.calculate_block_reward(blockchain.get_height() + 1) / SALO,
        "total_supply": sum(
            config.calculate_block_reward(h) for h in range(1, blockchain.get_height() + 1)
        ) / SALO,
        "mempool_size": len(blockchain.mempool.transactions),
        "connections": 0,  # TODO: implement peer tracking
    }
    
    print("\n📊 SALOCOIN Blockchain Info")
    print("═" * 50)
    for key, value in info.items():
        print(f"  {key}: {value}")
    print()


def cmd_sync(args):
    """Sync blockchain from seed."""
    os.makedirs(DATA_DIR, exist_ok=True)
    blockchain = Blockchain(data_dir=DATA_DIR)
    
    print(f"\n🔄 Syncing from {SEED_NODE}...")
    
    try:
        syncer = BlockchainSync(blockchain, seed_url=SEED_NODE)
        status = syncer.get_status()
        
        if not status:
            print("❌ Seed node not reachable")
            return
        
        print(f"   Local height: {blockchain.get_height()}")
        print(f"   Network height: {status.get('height', 0)}")
        
        syncer.sync_from_seed()
        blockchain.save()
        
        print(f"\n✓ Synced to height {blockchain.get_height()}")
    except Exception as e:
        print(f"❌ Sync failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='SALOCOIN Daemon CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # start
    subparsers.add_parser('start', help='Start the daemon')
    
    # stop
    subparsers.add_parser('stop', help='Stop the daemon')
    
    # status
    subparsers.add_parser('status', help='Check daemon status')
    
    # getinfo
    subparsers.add_parser('getinfo', help='Get blockchain info')
    
    # sync
    subparsers.add_parser('sync', help='Sync blockchain from seed')
    
    args = parser.parse_args()
    
    if args.command == 'start':
        cmd_start(args)
    elif args.command == 'stop':
        cmd_stop(args)
    elif args.command == 'status':
        cmd_status(args)
    elif args.command == 'getinfo':
        cmd_getinfo(args)
    elif args.command == 'sync':
        cmd_sync(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
