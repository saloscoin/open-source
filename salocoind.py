#!/usr/bin/env python3
"""
SALOCOIN Daemon
Full node daemon with RPC server.

Usage:
    python salocoind.py [options]

Options:
    --testnet           Use testnet
    --datadir=<dir>     Data directory
    --port=<port>       P2P port (default: 7339)
    --rpcport=<port>    RPC port (default: 7340)
    --rpcuser=<user>    RPC username
    --rpcpassword=<pw>  RPC password
    --rpcbind=<addr>    RPC bind address (default: 127.0.0.1)
    --masternode        Run as masternode
    --mnprivkey=<key>   Masternode private key
    --daemon            Run as daemon (background)
    --printtoconsole    Print to console
    --help              Show this help
"""

import sys
import os
import argparse
import signal
import time
import threading

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from network import Node
from rpc import RPCServer, RPCMethods
from core.wallet import WalletManager


class SALOCOINDaemon:
    """SALOCOIN daemon main class."""
    
    def __init__(self, args):
        """Initialize daemon."""
        self.args = args
        self.running = False
        
        # Determine network
        self.testnet = args.testnet
        
        # Data directory
        self.data_dir = args.datadir or config.get_data_dir(self.testnet)
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Node
        self.node = Node(
            data_dir=self.data_dir,
            host="0.0.0.0",
            port=args.port or (config.P2P_TESTNET_PORT if self.testnet else config.P2P_PORT),
            testnet=self.testnet,
        )
        
        # Wallet
        self.wallet_manager = WalletManager(self.data_dir)
        
        # RPC Server
        rpc_port = args.rpcport or (config.RPC_TESTNET_PORT if self.testnet else config.RPC_PORT)
        self.rpc_server = RPCServer(
            host=args.rpcbind or "127.0.0.1",
            port=rpc_port,
            username=args.rpcuser,
            password=args.rpcpassword,
            verbose=args.printtoconsole,
        )
        
        # RPC Methods
        self.rpc_methods = RPCMethods(self.node, self.wallet_manager)
        self.rpc_server.register_methods(self.rpc_methods.get_methods())
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\nReceived shutdown signal")
        self.stop()
    
    def start(self):
        """Start the daemon."""
        if self.running:
            return
        
        print(f"""
╔══════════════════════════════════════════════════════════╗
║                    SALOCOIN Core v1.0.0                  ║
║                Enterprise-Grade Masternode               ║
╠══════════════════════════════════════════════════════════╣
║  Network: {'Testnet' if self.testnet else 'Mainnet':>45}  ║
║  P2P Port: {self.node.port:>44}  ║
║  RPC Port: {self.rpc_server.port:>44}  ║
║  Data Dir: {self.data_dir[:42]:>44}  ║
╚══════════════════════════════════════════════════════════╝
""")
        
        self.running = True
        self.node.start_time = time.time()
        
        # Load or create wallet
        wallet = self.wallet_manager.load_default()
        if not wallet:
            wallet = self.wallet_manager.create_wallet("default")
            print("Created new wallet")
        
        self.rpc_methods.wallet = wallet
        
        # Start masternode if configured
        if self.args.masternode and self.args.mnprivkey:
            self._start_masternode()
        
        # Start node
        self.node.start()
        
        # Start RPC server
        self.rpc_server.start()
        
        print("\nDaemon started. Press Ctrl+C to stop.\n")
        
        # Main loop
        while self.running:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break
    
    def stop(self):
        """Stop the daemon."""
        if not self.running:
            return
        
        self.running = False
        
        # Stop RPC server
        self.rpc_server.stop()
        
        # Stop node
        self.node.stop()
        
        # Save wallet
        self.wallet_manager.save_all()
        
        print("Daemon stopped")
    
    def _start_masternode(self):
        """Start masternode mode."""
        print("Starting masternode...")
        
        privkey = self.args.mnprivkey
        
        try:
            success = self.node.masternode_manager.start(privkey)
            if success:
                print("Masternode started successfully")
            else:
                print("Failed to start masternode")
        except Exception as e:
            print(f"Masternode error: {e}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="SALOCOIN Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python salocoind.py
    python salocoind.py --testnet
    python salocoind.py --rpcuser=user --rpcpassword=pass
    python salocoind.py --masternode --mnprivkey=<key>
        """
    )
    
    parser.add_argument('--testnet', action='store_true',
                       help='Use testnet')
    parser.add_argument('--datadir', type=str,
                       help='Data directory')
    parser.add_argument('--port', type=int,
                       help='P2P port')
    parser.add_argument('--rpcport', type=int,
                       help='RPC port')
    parser.add_argument('--rpcuser', type=str,
                       help='RPC username')
    parser.add_argument('--rpcpassword', type=str,
                       help='RPC password')
    parser.add_argument('--rpcbind', type=str, default='127.0.0.1',
                       help='RPC bind address')
    parser.add_argument('--masternode', action='store_true',
                       help='Run as masternode')
    parser.add_argument('--mnprivkey', type=str,
                       help='Masternode private key')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon (background)')
    parser.add_argument('--printtoconsole', action='store_true',
                       help='Print to console')
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Run as daemon (background)
    if args.daemon:
        if os.name == 'nt':
            print("Daemon mode not supported on Windows")
            sys.exit(1)
        
        # Fork to background
        pid = os.fork()
        if pid > 0:
            print(f"Daemon started with PID {pid}")
            sys.exit(0)
        
        # Detach from terminal
        os.setsid()
        os.umask(0)
    
    # Create and start daemon
    daemon = SALOCOINDaemon(args)
    
    try:
        daemon.start()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
