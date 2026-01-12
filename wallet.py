#!/usr/bin/env python3
"""
SALOCOIN Wallet Creator
Create and manage SALOCOIN wallets.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.wallet import Wallet
import config


def create_wallet(name: str = "my_wallet"):
    """Create a new wallet and save it."""
    
    # Data directory
    data_dir = os.path.join(os.path.dirname(__file__), 'wallets')
    os.makedirs(data_dir, exist_ok=True)
    
    filepath = os.path.join(data_dir, f'{name}.json')
    
    # Check if wallet already exists
    if os.path.exists(filepath):
        print(f"Wallet '{name}' already exists at {filepath}")
        print("Use a different name or load the existing wallet.")
        return None
    
    # Create new wallet
    wallet = Wallet(filepath=filepath, name=name)
    mnemonic = wallet.create_hd_wallet()
    wallet.save()
    
    print("""
╔══════════════════════════════════════════════════════════╗
║              SALOCOIN Wallet Created!                    ║
╚══════════════════════════════════════════════════════════╝
""")
    print(f"Wallet Name: {name}")
    print(f"Saved to: {filepath}")
    print(f"\n⚠️  IMPORTANT - SAVE YOUR MNEMONIC PHRASE! ⚠️")
    print(f"═" * 60)
    print(f"\n{mnemonic}\n")
    print(f"═" * 60)
    print(f"\nThis is the ONLY way to recover your wallet!")
    print(f"\nYour Address: {wallet.addresses[0].address}")
    
    return wallet


def load_wallet(name: str = "my_wallet"):
    """Load an existing wallet."""
    
    data_dir = os.path.join(os.path.dirname(__file__), 'wallets')
    filepath = os.path.join(data_dir, f'{name}.json')
    
    if not os.path.exists(filepath):
        print(f"Wallet '{name}' not found at {filepath}")
        return None
    
    wallet = Wallet(filepath=filepath)
    wallet.load()
    
    print(f"\nWallet '{wallet.name}' loaded!")
    print(f"Addresses: {len(wallet.addresses)}")
    for i, addr in enumerate(wallet.addresses):
        print(f"  [{i}] {addr.address}")
    
    return wallet


def get_new_address(wallet: Wallet, label: str = ""):
    """Generate a new address in the wallet."""
    addr = wallet.create_address(label)
    print(f"\nNew address created: {addr.address}")
    if label:
        print(f"Label: {label}")
    return addr


def show_wallet_info(wallet: Wallet):
    """Display wallet information."""
    print(f"""
╔══════════════════════════════════════════════════════════╗
║                    Wallet Info                           ║
╚══════════════════════════════════════════════════════════╝
Name: {wallet.name}
Addresses: {len(wallet.addresses)}
""")
    for i, addr in enumerate(wallet.addresses):
        print(f"Address [{i}]: {addr.address}")
        if addr.label:
            print(f"  Label: {addr.label}")
        print(f"  Path: {addr.derivation_path}")


def get_balance(wallet: Wallet) -> float:
    """Calculate wallet balance from blockchain."""
    from core.blockchain import Blockchain
    from core.transaction import Transaction
    
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    blockchain = Blockchain(data_dir=data_dir)
    blockchain.load()
    
    addresses = [a.address for a in wallet.addresses]
    
    # Track spent outputs
    spent = set()
    for block in blockchain.chain:
        for tx_data in block.transactions:
            tx = Transaction.from_dict(tx_data) if isinstance(tx_data, dict) else tx_data
            for inp in tx.inputs:
                if inp.txid != '0' * 64:
                    spent.add((inp.txid, inp.vout))
    
    # Calculate unspent balance
    balance = 0
    for block in blockchain.chain:
        for tx_data in block.transactions:
            tx = Transaction.from_dict(tx_data) if isinstance(tx_data, dict) else tx_data
            for vout, output in enumerate(tx.outputs):
                if output.address in addresses and (tx.txid, vout) not in spent:
                    balance += output.value
    
    return balance / config.COIN_UNIT


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='SALOCOIN Wallet Manager')
    parser.add_argument('command', choices=['create', 'load', 'newaddress', 'info', 'balance'],
                        help='Command to execute')
    parser.add_argument('--name', '-n', default='my_wallet', 
                        help='Wallet name (default: my_wallet)')
    parser.add_argument('--label', '-l', default='',
                        help='Label for new address')
    
    args = parser.parse_args()
    
    if args.command == 'create':
        create_wallet(args.name)
    
    elif args.command == 'load':
        load_wallet(args.name)
    
    elif args.command == 'newaddress':
        wallet = load_wallet(args.name)
        if wallet:
            get_new_address(wallet, args.label)
            wallet.save()
    
    elif args.command == 'info':
        wallet = load_wallet(args.name)
        if wallet:
            show_wallet_info(wallet)
    
    elif args.command == 'balance':
        wallet = load_wallet(args.name)
        if wallet:
            balance = get_balance(wallet)
            print(f"\n💰 Balance: {balance} SALO")
