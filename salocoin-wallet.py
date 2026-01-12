#!/usr/bin/env python3
"""
SALOCOIN Wallet CLI
Create and manage SALOCOIN wallets.

Usage:
    salocoin-wallet create <name>           Create a new wallet
    salocoin-wallet list                    List all wallets
    salocoin-wallet balance <name>          Check wallet balance
    salocoin-wallet address new -n <name>   Generate new address
    salocoin-wallet address list -n <name>  List all addresses
    salocoin-wallet send <to> <amount> -n <name>  Send SALO
    salocoin-wallet history <name>          View transaction history
    salocoin-wallet receive <name>          Show receive address
    salocoin-wallet backup <name>           Show mnemonic backup
    salocoin-wallet restore <name>          Restore from mnemonic
"""

import sys
import os
import argparse
import json

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.wallet import Wallet
from core.blockchain import Blockchain
from sync import BlockchainSync
import config

SEED_NODE = "https://api.salocoin.org"
WALLETS_DIR = os.path.join(os.path.dirname(__file__), 'wallets')
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def get_wallet_path(name: str) -> str:
    return os.path.join(WALLETS_DIR, f'{name}.json')


def wallet_exists(name: str) -> bool:
    return os.path.exists(get_wallet_path(name))


def load_wallet(name: str) -> Wallet:
    """Load a wallet by name."""
    path = get_wallet_path(name)
    if not os.path.exists(path):
        print(f"❌ Wallet '{name}' not found")
        print(f"   Create one with: salocoin-wallet create {name}")
        sys.exit(1)
    
    wallet = Wallet(filepath=path)
    wallet.load()
    return wallet


def cmd_create(args):
    """Create a new wallet."""
    os.makedirs(WALLETS_DIR, exist_ok=True)
    
    if wallet_exists(args.name):
        print(f"❌ Wallet '{args.name}' already exists")
        return
    
    path = get_wallet_path(args.name)
    wallet = Wallet(filepath=path, name=args.name)
    mnemonic = wallet.create_hd_wallet()
    wallet.save()
    
    address = wallet.addresses[0].address
    
    print("""
╔══════════════════════════════════════════════════════════╗
║              SALOCOIN Wallet Created!                    ║
╚══════════════════════════════════════════════════════════╝
""")
    print(f"Wallet Name: {args.name}")
    print(f"\n⚠️  IMPORTANT - SAVE YOUR MNEMONIC PHRASE! ⚠️")
    print("═" * 60)
    print(f"\n{mnemonic}\n")
    print("═" * 60)
    print("\nThis is the ONLY way to recover your wallet!")
    print(f"\nYour Address: {address}")
    
    # Show QR code
    if HAS_QRCODE:
        print("\n📱 QR Code for your address:")
        print("═" * 40)
        qr = qrcode.QRCode(version=1, box_size=1, border=1)
        qr.add_data(address)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        print("═" * 40)
    else:
        print("\n💡 Install 'qrcode' package for QR code display: pip install qrcode")
    
    # Sync with network if seed provided
    if hasattr(args, 'seed') and args.seed:
        seed_url = args.seed
        print(f"\n🔄 Syncing with network ({seed_url})...")
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            blockchain = Blockchain(data_dir=DATA_DIR)
            syncer = BlockchainSync(blockchain, seed_url=seed_url)
            syncer.sync_from_seed()
            print("   ✓ Sync complete")
        except Exception as e:
            print(f"   ⚠ Sync failed: {e}")


def cmd_list(args):
    """List all wallets."""
    os.makedirs(WALLETS_DIR, exist_ok=True)
    
    wallets = [f[:-5] for f in os.listdir(WALLETS_DIR) if f.endswith('.json')]
    
    if not wallets:
        print("No wallets found. Create one with: salocoin-wallet create <name>")
        return
    
    print("\n📂 SALOCOIN Wallets")
    print("═" * 40)
    for name in wallets:
        wallet = load_wallet(name)
        print(f"  • {name}: {wallet.addresses[0].address}")
    print()


def cmd_balance(args):
    """Check wallet balance."""
    wallet = load_wallet(args.name)
    
    # Load blockchain and sync
    os.makedirs(DATA_DIR, exist_ok=True)
    blockchain = Blockchain(data_dir=DATA_DIR)
    
    seed_url = args.seed if args.seed else SEED_NODE
    print(f"\n🔄 Syncing with network ({seed_url})...")
    try:
        syncer = BlockchainSync(blockchain, seed_url=seed_url)
        syncer.sync_from_seed()
    except Exception as e:
        print(f"   ⚠ Sync failed: {e}")
    
    # Calculate balance for all addresses
    total = 0
    print(f"\n💰 Wallet: {args.name}")
    print("═" * 50)
    
    for addr_info in wallet.addresses:
        balance = blockchain.get_balance(addr_info.address)
        total += balance
        if balance > 0:
            print(f"  {addr_info.address}: {balance / config.COIN_UNIT:.8f} SALO")
    
    print("═" * 50)
    print(f"  Total Balance: {total / config.COIN_UNIT:.8f} SALO\n")


def cmd_address_new(args):
    """Generate a new address."""
    wallet = load_wallet(args.name)
    
    new_addr = wallet.derive_new_address()
    wallet.save()
    
    print(f"\n✓ New address generated for wallet '{args.name}':")
    print(f"  {new_addr.address}\n")


def cmd_address_list(args):
    """List all addresses in wallet."""
    wallet = load_wallet(args.name)
    
    print(f"\n📋 Addresses in wallet '{args.name}':")
    print("═" * 60)
    for i, addr_info in enumerate(wallet.addresses):
        label = f" ({addr_info.label})" if addr_info.label else ""
        print(f"  {i+1}. {addr_info.address}{label}")
    print()


def cmd_send(args):
    """Send SALO to an address."""
    wallet = load_wallet(args.name)
    
    # Load blockchain and sync
    os.makedirs(DATA_DIR, exist_ok=True)
    blockchain = Blockchain(data_dir=DATA_DIR)
    
    seed_url = args.seed if args.seed else SEED_NODE
    print(f"\n🔄 Syncing with network ({seed_url})...")
    try:
        syncer = BlockchainSync(blockchain, seed_url=seed_url)
        syncer.sync_from_seed()
    except Exception as e:
        print(f"   ⚠ Sync failed: {e}")
        return
    
    # Check balance
    from_addr = wallet.addresses[0].address
    balance = blockchain.get_balance(from_addr)
    amount_sats = int(args.amount * config.COIN_UNIT)
    
    if balance < amount_sats:
        print(f"\n❌ Insufficient balance!")
        print(f"   Available: {balance / config.COIN_UNIT:.8f} SALO")
        print(f"   Required:  {args.amount:.8f} SALO")
        return
    
    # Create and sign transaction
    from core.transaction import Transaction
    from core.crypto import private_key_to_public_key
    
    utxos = blockchain.get_utxos(from_addr)
    
    # Select UTXOs to cover amount + fee
    selected_utxos = []
    total_input = 0
    fee = 1000  # 0.00001 SALO fee
    
    for utxo in utxos:
        selected_utxos.append(utxo)
        total_input += utxo['value']
        if total_input >= amount_sats + fee:
            break
    
    if total_input < amount_sats + fee:
        print(f"\n❌ Insufficient UTXOs!")
        return
    
    # Build inputs
    inputs = []
    for utxo in selected_utxos:
        inputs.append({
            'txid': utxo['txid'],
            'vout': utxo['vout'],
            'value': utxo['value'],
            'prev_script': utxo.get('script_pubkey', ''),
            'address': from_addr
        })
    
    # Build outputs
    outputs = [{'address': args.to_address, 'value': amount_sats}]
    
    # Change output if needed
    change = total_input - amount_sats - fee
    if change > 0:
        outputs.append({'address': from_addr, 'value': change})
    
    tx = Transaction.create_transaction(inputs, outputs, change_address=from_addr)
    
    # Sign all inputs
    private_key_hex = wallet.addresses[0].private_key
    if isinstance(private_key_hex, bytes):
        private_key = private_key_hex
    else:
        private_key = bytes.fromhex(private_key_hex)
    public_key = private_key_to_public_key(private_key)
    
    for i in range(len(tx.inputs)):
        tx.sign_input(i, private_key, public_key)
    
    if not tx:
        print("❌ Failed to create transaction")
        return
    
    # Submit to network
    try:
        syncer = BlockchainSync(blockchain, seed_url=SEED_NODE)
        if syncer.submit_transaction(tx):
            print(f"\n✓ Transaction submitted!")
            print(f"  TXID: {tx.txid}")
            print(f"  Amount: {args.amount} SALO")
            print(f"  To: {args.to_address}")
        else:
            print("❌ Failed to submit transaction")
    except Exception as e:
        print(f"❌ Error: {e}")


def cmd_history(args):
    """View transaction history."""
    wallet = load_wallet(args.name)
    
    # Load blockchain and sync
    os.makedirs(DATA_DIR, exist_ok=True)
    blockchain = Blockchain(data_dir=DATA_DIR)
    
    print(f"\n🔄 Syncing with network...")
    try:
        syncer = BlockchainSync(blockchain, seed_url=SEED_NODE)
        syncer.sync_from_seed()
    except Exception as e:
        print(f"   ⚠ Sync failed: {e}")
    
    print(f"\n📜 Transaction History for '{args.name}'")
    print("═" * 70)
    
    addresses = [a.address for a in wallet.addresses]
    txs = blockchain.get_address_transactions(addresses[0])  # Primary address
    
    if not txs:
        print("  No transactions found")
    else:
        for tx in txs[-20:]:  # Last 20
            direction = "📥" if tx.get('received', 0) > 0 else "📤"
            amount = tx.get('received', 0) or tx.get('sent', 0)
            print(f"  {direction} {amount / config.COIN_UNIT:.8f} SALO - {tx.get('txid', '')[:32]}...")
    print()


def cmd_receive(args):
    """Show receive address with QR code."""
    wallet = load_wallet(args.name)
    
    address = wallet.addresses[0].address
    
    print(f"\n📥 Receive Address for '{args.name}':")
    print("═" * 50)
    print(f"\n  {address}\n")
    
    # Show QR code
    if HAS_QRCODE:
        print("📱 QR Code:")
        print("─" * 40)
        qr = qrcode.QRCode(version=1, box_size=1, border=1)
        qr.add_data(address)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        print("─" * 40)
    else:
        print("💡 Install 'qrcode' package for QR code display: pip install qrcode")
    
    print("\nShare this address to receive SALO coins.\n")


def cmd_backup(args):
    """Show wallet mnemonic for backup."""
    wallet = load_wallet(args.name)
    
    if not wallet.mnemonic:
        print("❌ No mnemonic found for this wallet")
        return
    
    print(f"""
⚠️  WALLET BACKUP - KEEP SECRET! ⚠️
══════════════════════════════════════════════════════════

Wallet: {args.name}

Mnemonic Phrase:
{wallet.mnemonic}

══════════════════════════════════════════════════════════
Anyone with this phrase can access your funds!
Store it safely offline.
""")


def cmd_restore(args):
    """Restore wallet from mnemonic."""
    os.makedirs(WALLETS_DIR, exist_ok=True)
    
    if wallet_exists(args.name):
        print(f"❌ Wallet '{args.name}' already exists")
        return
    
    print("\nEnter your 24-word mnemonic phrase:")
    mnemonic = input("> ").strip()
    
    if len(mnemonic.split()) != 24:
        print("❌ Invalid mnemonic. Must be 24 words.")
        return
    
    path = get_wallet_path(args.name)
    wallet = Wallet(filepath=path, name=args.name)
    
    try:
        wallet.restore_from_mnemonic(mnemonic)
        wallet.save()
        print(f"\n✓ Wallet '{args.name}' restored successfully!")
        print(f"  Address: {wallet.addresses[0].address}\n")
    except Exception as e:
        print(f"❌ Failed to restore: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='SALOCOIN Wallet CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # create
    p_create = subparsers.add_parser('create', help='Create a new wallet')
    p_create.add_argument('name', help='Wallet name')
    p_create.add_argument('--seed', '-s', help='Seed node URL to sync after creation')
    
    # list
    subparsers.add_parser('list', help='List all wallets')
    
    # balance
    p_balance = subparsers.add_parser('balance', help='Check wallet balance')
    p_balance.add_argument('name', help='Wallet name')
    p_balance.add_argument('--seed', '-s', help='Seed node URL (default: https://api.salocoin.org)')
    
    # address
    p_address = subparsers.add_parser('address', help='Address management')
    addr_sub = p_address.add_subparsers(dest='addr_cmd')
    
    p_addr_new = addr_sub.add_parser('new', help='Generate new address')
    p_addr_new.add_argument('-n', '--name', required=True, help='Wallet name')
    
    p_addr_list = addr_sub.add_parser('list', help='List all addresses')
    p_addr_list.add_argument('-n', '--name', required=True, help='Wallet name')
    
    # send
    p_send = subparsers.add_parser('send', help='Send SALO')
    p_send.add_argument('to_address', help='Recipient address')
    p_send.add_argument('amount', type=float, help='Amount in SALO')
    p_send.add_argument('-n', '--name', required=True, help='Wallet name')
    p_send.add_argument('--seed', '-s', help='Seed node URL (default: https://api.salocoin.org)')
    
    # history
    p_history = subparsers.add_parser('history', help='Transaction history')
    p_history.add_argument('name', help='Wallet name')
    
    # receive
    p_receive = subparsers.add_parser('receive', help='Show receive address')
    p_receive.add_argument('name', help='Wallet name')
    
    # backup
    p_backup = subparsers.add_parser('backup', help='Backup wallet (show mnemonic)')
    p_backup.add_argument('name', help='Wallet name')
    
    # restore
    p_restore = subparsers.add_parser('restore', help='Restore wallet from mnemonic')
    p_restore.add_argument('name', help='Wallet name')
    
    args = parser.parse_args()
    
    if args.command == 'create':
        cmd_create(args)
    elif args.command == 'list':
        cmd_list(args)
    elif args.command == 'balance':
        cmd_balance(args)
    elif args.command == 'address':
        if args.addr_cmd == 'new':
            cmd_address_new(args)
        elif args.addr_cmd == 'list':
            cmd_address_list(args)
        else:
            p_address.print_help()
    elif args.command == 'send':
        cmd_send(args)
    elif args.command == 'history':
        cmd_history(args)
    elif args.command == 'receive':
        cmd_receive(args)
    elif args.command == 'backup':
        cmd_backup(args)
    elif args.command == 'restore':
        cmd_restore(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
