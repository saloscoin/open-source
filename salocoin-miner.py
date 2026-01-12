#!/usr/bin/env python3
"""
SALOCOIN Miner CLI
Mine SALO coins to your wallet.

Usage:
    salocoin-miner start                      Start mining (uses default wallet)
    salocoin-miner start --address <addr>     Mine to specific address
    salocoin-miner start --nosync             Mine without seed node sync
    salocoin-miner status                     Check miner status
    salocoin-miner set-address <address>      Set default mining address
"""

import sys
import os
import time
import argparse
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from core.wallet import Wallet
from core.blockchain import Blockchain, Block
from core.transaction import Transaction
from sync import BlockchainSync

SEED_NODE = "https://api.salocoin.org"
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
WALLETS_DIR = os.path.join(os.path.dirname(__file__), 'wallets')
MINER_CONFIG = os.path.join(DATA_DIR, 'miner.json')
SALO = config.COIN_UNIT


def load_miner_config():
    """Load miner configuration."""
    if os.path.exists(MINER_CONFIG):
        with open(MINER_CONFIG, 'r') as f:
            return json.load(f)
    return {}


def save_miner_config(cfg):
    """Save miner configuration."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MINER_CONFIG, 'w') as f:
        json.dump(cfg, f, indent=2)


def get_default_address():
    """Get default mining address from config or wallet."""
    cfg = load_miner_config()
    if cfg.get('address'):
        return cfg['address']
    
    # Try to load default wallet
    default_wallet = os.path.join(WALLETS_DIR, 'my_wallet.json')
    if os.path.exists(default_wallet):
        wallet = Wallet(filepath=default_wallet)
        wallet.load()
        return wallet.addresses[0].address
    
    return None


def mine_block(blockchain: Blockchain, miner_address: str, syncer=None) -> Block:
    """Mine a single block."""
    latest = blockchain.get_latest_block()
    height = latest.height + 1
    original_height = blockchain.get_height()
    
    # Create coinbase transaction
    coinbase = Transaction.create_coinbase(
        block_height=height,
        miner_address=miner_address,
        extra_data=f"SALOCOIN Miner - Block {height}"
    )
    
    # Get pending transactions from mempool
    transactions = [coinbase.to_dict()]
    for tx in blockchain.mempool.get_transactions(max_count=100):
        transactions.append(tx.to_dict())
    
    # Create block
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
    
    # Mining
    target = Block.get_target_from_difficulty(block.difficulty)
    start_time = time.time()
    last_sync_time = time.time()
    sync_interval = 10  # Check for new blocks every 10 seconds
    
    print(f"\n⛏️  Mining block {height}...")
    print(f"   Transactions: {len(transactions)}")
    
    nonce = 0
    while True:
        block.nonce = nonce
        block.hash = block.calculate_hash()
        
        if int(block.hash, 16) < target:
            elapsed = time.time() - start_time
            hashrate = nonce / elapsed if elapsed > 0 else 0
            print(f"   ✓ Block found!")
            print(f"   Hash: {block.hash[:32]}...")
            print(f"   Nonce: {nonce:,}")
            print(f"   Time: {elapsed:.2f}s")
            print(f"   Hashrate: {hashrate/1000:.2f} KH/s")
            return block
        
        nonce += 1
        
        # Check for new blocks from network periodically
        if syncer and time.time() - last_sync_time > sync_interval:
            last_sync_time = time.time()
            try:
                syncer.sync_from_seed(quiet=True)
                if blockchain.get_height() > original_height:
                    print(f"\n   📢 New block found by network! Height: {blockchain.get_height()}")
                    return None  # Signal to restart mining
            except:
                pass
        
        if nonce % 500000 == 0:
            elapsed = time.time() - start_time
            hashrate = nonce / elapsed if elapsed > 0 else 0
            print(f"   ... {nonce:,} hashes ({hashrate/1000:.2f} KH/s)")


def cmd_start(args):
    """Start mining."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Get mining address
    if args.address:
        miner_address = args.address
    else:
        miner_address = get_default_address()
        if not miner_address:
            print("❌ No mining address specified!")
            print("   Use: salocoin-miner start --address <your_address>")
            print("   Or create a wallet first: salocoin-wallet create my_wallet")
            return
    
    # Load blockchain
    blockchain = Blockchain(data_dir=DATA_DIR)
    
    print("""
╔══════════════════════════════════════════════════════════╗
║                   SALOCOIN Miner                         ║
╚══════════════════════════════════════════════════════════╝
""")
    print(f"Mining Address: {miner_address}")
    
    # Use custom seed node if specified
    seed_url = args.seed if args.seed else SEED_NODE
    
    # Sync from seed node (unless --nosync)
    syncer = None
    if not args.nosync:
        print(f"\n🔄 Syncing from seed node ({seed_url})...")
        try:
            syncer = BlockchainSync(blockchain, seed_url=seed_url)
            status = syncer.get_status()
            if status:
                print(f"   Seed node height: {status.get('height', 0)}")
                print(f"   Genesis: {status.get('genesis', '')[:32]}...")
                syncer.sync_from_seed()
                print(f"   ✓ Synced to height {blockchain.get_height()}")
                # Sync mempool too
                print(f"   📝 Syncing mempool...")
                syncer.sync_mempool()
                print(f"   ✓ Mempool has {blockchain.mempool.size()} transactions")
            else:
                print(f"   ⚠ Seed node not reachable")
                print(f"   Mining from local chain...")
        except Exception as e:
            print(f"   ⚠ Sync failed: {e}")
            print(f"   Mining from local chain...")
    else:
        print("\n⚠ Sync disabled - mining on local chain only")
        syncer = BlockchainSync(blockchain, seed_url=seed_url)
    
    print(f"\nBlockchain Height: {blockchain.get_height()}")
    print(f"Block Reward: {config.calculate_block_reward(blockchain.get_height() + 1) / SALO} SALO")
    print(f"\nPress Ctrl+C to stop mining.\n")
    
    blocks_mined = 0
    total_reward = 0
    
    try:
        while True:
            # Re-sync before each block to get latest chain and mempool
            if not args.nosync:
                try:
                    syncer.sync_from_seed()
                    # Sync mempool to get new transactions
                    syncer.sync_mempool()
                    mempool_count = blockchain.mempool.size()
                    if mempool_count > 0:
                        print(f"   📝 Mempool: {mempool_count} pending transaction(s)")
                except:
                    pass
            
            block = mine_block(blockchain, miner_address, syncer if not args.nosync else None)
            
            # If block is None, another miner found a block - restart mining
            if block is None:
                continue
            
            if blockchain.add_block(block):
                reward = config.calculate_block_reward(block.height)
                blocks_mined += 1
                total_reward += reward
                
                print(f"   💰 Reward: {reward / SALO} SALO")
                print(f"   📊 Total mined: {total_reward / SALO} SALO ({blocks_mined} blocks)")
                
                # Submit block to seed node
                if syncer:
                    try:
                        if syncer.submit_block(block):
                            print(f"   📡 Block submitted to network")
                        else:
                            # Block rejected - someone else found a block first
                            # Use resync_chain to rollback and get correct chain
                            print(f"   ❌ Block rejected by network!")
                            try:
                                blocks_mined -= 1  # Don't count rejected block
                                total_reward -= reward
                                syncer.resync_chain()
                                print(f"   ✓ Chain resynced to height {blockchain.get_height()}")
                            except Exception as e:
                                print(f"   ⚠ Resync failed: {e}")
                    except Exception as e:
                        print(f"   ⚠ Failed to submit: {e}")
                        # Try to resync on any submit error
                        try:
                            syncer.resync_chain()
                        except:
                            pass
                
                # Save periodically
                if blocks_mined % 5 == 0:
                    blockchain.save()
                    print(f"   💾 Blockchain saved")
            
            if args.blocks and blocks_mined >= args.blocks:
                break
                
    except KeyboardInterrupt:
        print(f"\n\nMining stopped!")
    
    # Final save
    blockchain.save()
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║                   Mining Summary                         ║
╠══════════════════════════════════════════════════════════╣
║  Blocks Mined: {blocks_mined:<41} ║
║  Total Reward: {total_reward / SALO:<38} SALO ║
║  Blockchain Height: {blockchain.get_height():<35} ║
╚══════════════════════════════════════════════════════════╝
""")


def cmd_status(args):
    """Check miner status."""
    cfg = load_miner_config()
    
    # Load blockchain
    os.makedirs(DATA_DIR, exist_ok=True)
    blockchain = Blockchain(data_dir=DATA_DIR)
    
    print("\n📊 SALOCOIN Miner Status")
    print("═" * 50)
    print(f"  Default Address: {cfg.get('address', 'Not set')}")
    print(f"  Local Height: {blockchain.get_height()}")
    
    # Check seed node
    try:
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


def cmd_set_address(args):
    """Set default mining address."""
    cfg = load_miner_config()
    cfg['address'] = args.address
    save_miner_config(cfg)
    
    print(f"\n✓ Default mining address set to:")
    print(f"  {args.address}\n")


def main():
    parser = argparse.ArgumentParser(
        description='SALOCOIN Miner CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # start
    p_start = subparsers.add_parser('start', help='Start mining')
    p_start.add_argument('--address', '-a', help='Mining address')
    p_start.add_argument('--seed', '-s', help='Seed node URL (default: https://api.salocoin.org)')
    p_start.add_argument('--nosync', action='store_true', help='Skip seed node sync')
    p_start.add_argument('--blocks', '-b', type=int, help='Number of blocks to mine')
    
    # status
    subparsers.add_parser('status', help='Check miner status')
    
    # set-address
    p_setaddr = subparsers.add_parser('set-address', help='Set default mining address')
    p_setaddr.add_argument('address', help='Mining address')
    
    args = parser.parse_args()
    
    if args.command == 'start':
        cmd_start(args)
    elif args.command == 'status':
        cmd_status(args)
    elif args.command == 'set-address':
        cmd_set_address(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
