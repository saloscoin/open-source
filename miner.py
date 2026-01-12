#!/usr/bin/env python3
"""
SALOCOIN Miner
Mine SALO coins to your wallet.
"""

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from core.wallet import Wallet
from core.blockchain import Blockchain, Block
from core.transaction import Transaction
from sync import BlockchainSync

# Use seed node for network mining
SEED_NODE = "https://api.salocoin.org"

SALO = config.COIN_UNIT


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
    mempool_txs = blockchain.mempool.get_transactions(max_count=100)
    for tx in mempool_txs:
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
    
    mempool_count = len(transactions) - 1  # Exclude coinbase
    print(f"\n⛏️  Mining block {height}...")
    print(f"   Transactions: {len(transactions)} ({mempool_count} from mempool)")
    
    # Show pending transactions that will be confirmed
    if mempool_count > 0:
        print(f"   ─────────────────────────────────────────────")
        print(f"   📨 Pending TXs to confirm:")
        for tx in mempool_txs[:10]:  # Show max 10
            tx_dict = tx.to_dict()
            total_out = sum(o.get('amount', 0) for o in tx_dict.get('outputs', []))
            to_addr = tx_dict.get('outputs', [{}])[0].get('address', '')[:16] if tx_dict.get('outputs') else ''
            print(f"      → {tx.txid[:16]}... {total_out / SALO:.4f} SALO → {to_addr}...")
        if mempool_count > 10:
            print(f"      ... and {mempool_count - 10} more")
        print(f"   ─────────────────────────────────────────────")
    
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


def main():
    parser = argparse.ArgumentParser(description='SALOCOIN Miner')
    parser.add_argument('--wallet', '-w', default='my_wallet',
                        help='Wallet name to mine to (default: my_wallet)')
    parser.add_argument('--blocks', '-b', type=int, default=0,
                        help='Number of blocks to mine (0 = continuous)')
    parser.add_argument('--address', '-a', default='',
                        help='Mine to specific address (overrides wallet)')
    args = parser.parse_args()
    
    # Data directory
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Get mining address
    if args.address:
        miner_address = args.address
    else:
        wallet_path = os.path.join(os.path.dirname(__file__), 'wallets', f'{args.wallet}.json')
        if not os.path.exists(wallet_path):
            print(f"Wallet '{args.wallet}' not found. Create one first:")
            print(f"  python wallet.py create --name {args.wallet}")
            return
        
        wallet = Wallet(filepath=wallet_path)
        wallet.load()
        miner_address = wallet.addresses[0].address
    
    # Load blockchain
    blockchain = Blockchain(data_dir=data_dir)
    
    print("""
╔══════════════════════════════════════════════════════════╗
║                   SALOCOIN Miner                         ║
╚══════════════════════════════════════════════════════════╝
""")
    print(f"Mining Address: {miner_address}")
    
    # Sync from seed node
    print(f"\n🔄 Syncing from seed node ({SEED_NODE})...")
    try:
        syncer = BlockchainSync(blockchain, seed_url=SEED_NODE)
        status = syncer.get_status()
        if status:
            print(f"   Seed node height: {status.get('height', 0)}")
            print(f"   Genesis: {status.get('genesis', '')[:32]}...")
            syncer.sync_from_seed()
            print(f"   ✓ Synced to height {blockchain.get_height()}")
        else:
            print(f"   ⚠ Seed node not reachable")
            print(f"   Mining from local chain...")
    except Exception as e:
        print(f"   ⚠ Sync failed: {e}")
        print(f"   Mining from local chain...")
    
    print(f"\nBlockchain Height: {blockchain.get_height()}")
    print(f"Block Reward: {config.calculate_block_reward(blockchain.get_height() + 1) / SALO} SALO")
    print(f"\nPress Ctrl+C to stop mining.\n")
    
    # Create syncer for submitting blocks
    syncer = BlockchainSync(blockchain, seed_url=SEED_NODE)
    
    blocks_mined = 0
    total_reward = 0
    
    try:
        while True:
            # Re-sync before each block to get latest chain and mempool
            try:
                syncer.sync_from_seed()
                syncer.sync_mempool()  # Sync pending transactions from network
            except:
                pass
                
            block = mine_block(blockchain, miner_address, syncer)
            
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
            
            if args.blocks > 0 and blocks_mined >= args.blocks:
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


if __name__ == '__main__':
    main()
