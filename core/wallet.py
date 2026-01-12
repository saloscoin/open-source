"""
SALOCOIN Wallet Implementation
HD wallet with BIP32/39/44 support.
"""

import os
import json
import time
import secrets
import threading
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from threading import Lock, RLock

from .crypto import (
    generate_keypair,
    private_key_to_public_key,
    public_key_to_address,
    private_key_to_wif,
    wif_to_private_key,
    sign_message,
    sha256d,
    base58check_encode,
    base58check_decode,
    generate_mnemonic,
    mnemonic_to_seed,
    ExtendedKey,
    create_hd_wallet,
)
from .transaction import Transaction, TxInput, TxOutput
from .blockchain import Blockchain
import config


@dataclass
class Address:
    """Wallet address with keypair."""
    
    address: str
    public_key: bytes
    private_key: bytes
    label: str = ''
    created_at: int = 0
    
    # HD wallet path (if derived from HD wallet)
    derivation_path: str = ''
    
    # Balance cache
    balance: int = 0
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = int(time.time())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without private key for safety)."""
        return {
            'address': self.address,
            'public_key': self.public_key.hex(),
            'label': self.label,
            'created_at': self.created_at,
            'derivation_path': self.derivation_path,
            'balance': self.balance,
        }
    
    def to_dict_with_private(self) -> Dict[str, Any]:
        """Convert to dictionary including private key."""
        data = self.to_dict()
        data['private_key'] = self.private_key.hex()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Address':
        """Create from dictionary."""
        return cls(
            address=data['address'],
            public_key=bytes.fromhex(data.get('public_key', '')),
            private_key=bytes.fromhex(data.get('private_key', '')),
            label=data.get('label', ''),
            created_at=data.get('created_at', 0),
            derivation_path=data.get('derivation_path', ''),
            balance=data.get('balance', 0),
        )
    
    def get_wif(self) -> str:
        """Get private key in WIF format."""
        return private_key_to_wif(
            self.private_key,
            version=config.MAINNET_SECRET_KEY_PREFIX
        )
    
    def sign(self, message: bytes) -> bytes:
        """Sign a message with this address's private key."""
        return sign_message(self.private_key, message)


@dataclass
class Wallet:
    """
    SALOCOIN Wallet
    Supports HD wallet (BIP32/39/44) and legacy addresses.
    """
    
    filepath: str = ''
    name: str = 'Default Wallet'
    addresses: List[Address] = field(default_factory=list)
    
    # HD wallet
    mnemonic: str = ''
    master_key: Optional[ExtendedKey] = None
    hd_account_index: int = 0
    hd_address_index: int = 0
    
    # Encryption
    encrypted: bool = False
    encryption_salt: bytes = b''
    
    # State
    locked: bool = False
    created_at: int = 0
    
    _lock: Lock = field(default_factory=RLock, repr=False)
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = int(time.time())
        
        # Try to load existing wallet
        if self.filepath and os.path.exists(self.filepath):
            self.load()
    
    def create_hd_wallet(self, mnemonic: str = None, passphrase: str = "") -> str:
        """
        Initialize as HD wallet.
        
        Args:
            mnemonic: Mnemonic phrase (generates new if None)
            passphrase: Optional passphrase
            
        Returns:
            Mnemonic phrase
        """
        with self._lock:
            if mnemonic is None:
                mnemonic = generate_mnemonic()
            
            self.mnemonic = mnemonic
            seed = mnemonic_to_seed(mnemonic, passphrase)
            self.master_key = ExtendedKey.from_seed(
                seed,
                version=config.MAINNET_BIP32_PRIVATE
            )
            
            # Generate first address
            self.create_address("Default Address")
            
            return mnemonic
    
    def create_address(self, label: str = "") -> Address:
        """
        Create a new address.
        
        Args:
            label: Label for the address
            
        Returns:
            New address
        """
        with self._lock:
            if self.locked:
                raise ValueError("Wallet is locked")
            
            if self.master_key:
                # HD wallet derivation: m/44'/9339'/account'/0/index
                path = f"m/44'/{config.BIP44_COIN_TYPE}'/{self.hd_account_index}'/0/{self.hd_address_index}"
                
                derived_key = self.master_key.derive_path(path)
                private_key = derived_key.key
                public_key = private_key_to_public_key(private_key)
                address_str = public_key_to_address(
                    public_key,
                    version=config.MAINNET_PUBKEY_ADDRESS_PREFIX
                )
                
                address = Address(
                    address=address_str,
                    public_key=public_key,
                    private_key=private_key,
                    label=label or f"Address #{self.hd_address_index}",
                    derivation_path=path,
                )
                
                self.hd_address_index += 1
            else:
                # Legacy address generation
                private_key, public_key = generate_keypair()
                address_str = public_key_to_address(
                    public_key,
                    version=config.MAINNET_PUBKEY_ADDRESS_PREFIX
                )
                
                address = Address(
                    address=address_str,
                    public_key=public_key,
                    private_key=private_key,
                    label=label or f"Address #{len(self.addresses)}",
                )
            
            self.addresses.append(address)
            self.save()
            
            return address
    
    def get_address(self, address_str: str) -> Optional[Address]:
        """Get address by string."""
        for addr in self.addresses:
            if addr.address == address_str:
                return addr
        return None
    
    def get_addresses(self) -> List[str]:
        """Get list of all addresses."""
        return [addr.address for addr in self.addresses]
    
    def import_private_key(self, wif: str, label: str = "") -> Address:
        """
        Import address from WIF private key.
        
        Args:
            wif: WIF-encoded private key
            label: Label for the address
            
        Returns:
            Imported address
        """
        with self._lock:
            if self.locked:
                raise ValueError("Wallet is locked")
            
            private_key, compressed = wif_to_private_key(wif)
            public_key = private_key_to_public_key(private_key, compressed)
            address_str = public_key_to_address(
                public_key,
                version=config.MAINNET_PUBKEY_ADDRESS_PREFIX
            )
            
            # Check if already exists
            existing = self.get_address(address_str)
            if existing:
                return existing
            
            address = Address(
                address=address_str,
                public_key=public_key,
                private_key=private_key,
                label=label or "Imported",
            )
            
            self.addresses.append(address)
            self.save()
            
            return address
    
    def get_total_balance(self, blockchain: Blockchain) -> int:
        """
        Get total balance across all addresses.
        
        Args:
            blockchain: Blockchain instance
            
        Returns:
            Total balance in satoshis
        """
        total = 0
        for addr in self.addresses:
            addr.balance = blockchain.get_balance(addr.address)
            total += addr.balance
        return total
    
    def get_all_utxos(self, blockchain: Blockchain) -> List[Dict]:
        """
        Get all UTXOs for wallet addresses.
        
        Args:
            blockchain: Blockchain instance
            
        Returns:
            List of UTXOs with address info
        """
        utxos = []
        for addr in self.addresses:
            addr_utxos = blockchain.get_utxos(addr.address)
            for utxo in addr_utxos:
                utxo['address'] = addr.address
            utxos.extend(addr_utxos)
        return utxos
    
    def create_transaction(
        self,
        blockchain: Blockchain,
        recipients: List[Dict[str, Any]],
        fee_rate: int = config.DEFAULT_TX_FEE,
        change_address: str = None,
    ) -> Transaction:
        """
        Create and sign a transaction.
        
        Args:
            blockchain: Blockchain instance
            recipients: List of {address: str, amount: int} dicts
            fee_rate: Fee rate in satoshis per KB
            change_address: Address for change (uses first address if None)
            
        Returns:
            Signed transaction
        """
        if self.locked:
            raise ValueError("Wallet is locked")
        
        # Calculate total amount needed
        total_needed = sum(r['amount'] for r in recipients)
        
        # Get UTXOs
        utxos = self.get_all_utxos(blockchain)
        
        # Select inputs (simple algorithm - use all available)
        selected_utxos = []
        total_input = 0
        
        for utxo in sorted(utxos, key=lambda x: x['value'], reverse=True):
            selected_utxos.append(utxo)
            total_input += utxo['value']
            
            # Estimate fee
            est_size = 10 + (148 * len(selected_utxos)) + (34 * (len(recipients) + 1))
            est_fee = (est_size * fee_rate) // 1000
            
            if total_input >= total_needed + est_fee:
                break
        
        if total_input < total_needed:
            raise ValueError(f"Insufficient funds: have {total_input}, need {total_needed}")
        
        # Create transaction
        inputs = []
        for utxo in selected_utxos:
            inputs.append({
                'txid': utxo['txid'],
                'vout': utxo['vout'],
                'value': utxo['value'],
                'prev_script': utxo['script'],
                'address': utxo['address'],
            })
        
        outputs = []
        for recipient in recipients:
            outputs.append({
                'address': recipient['address'],
                'value': recipient['amount'],
            })
        
        if not change_address:
            change_address = self.addresses[0].address if self.addresses else None
        
        tx = Transaction.create_transaction(inputs, outputs, change_address)
        
        # Sign inputs
        for i, inp in enumerate(inputs):
            addr = self.get_address(inp['address'])
            if addr:
                tx.sign_input(i, addr.private_key, addr.public_key)
        
        return tx
    
    def sign_message(self, address: str, message: str) -> str:
        """
        Sign a message with an address.
        
        Args:
            address: Address to sign with
            message: Message to sign
            
        Returns:
            Base64-encoded signature
        """
        if self.locked:
            raise ValueError("Wallet is locked")
        
        addr = self.get_address(address)
        if not addr:
            raise ValueError(f"Address not in wallet: {address}")
        
        # Bitcoin-style message signing
        msg_prefix = b"\x18Salocoin Signed Message:\n"
        msg_bytes = message.encode('utf-8')
        full_msg = msg_prefix + bytes([len(msg_bytes)]) + msg_bytes
        
        signature = addr.sign(full_msg)
        
        import base64
        return base64.b64encode(signature).decode('ascii')
    
    def encrypt(self, passphrase: str):
        """
        Encrypt the wallet.
        
        Args:
            passphrase: Encryption passphrase
        """
        # Note: Full implementation would use AES-256-CBC
        # This is a simplified version
        if self.encrypted:
            raise ValueError("Wallet already encrypted")
        
        self.encryption_salt = secrets.token_bytes(32)
        self.encrypted = True
        self.locked = True
        self.save()
    
    def unlock(self, passphrase: str, timeout: int = 60):
        """
        Unlock encrypted wallet.
        
        Args:
            passphrase: Encryption passphrase
            timeout: Seconds to keep unlocked (0 = forever)
        """
        if not self.encrypted:
            return
        
        # Note: Full implementation would verify passphrase
        self.locked = False
        
        if timeout > 0:
            import threading
            def lock_wallet():
                time.sleep(timeout)
                self.locked = True
            
            t = threading.Thread(target=lock_wallet, daemon=True)
            t.start()
    
    def lock(self):
        """Lock the wallet."""
        self.locked = True
    
    def save(self):
        """Save wallet to file."""
        if not self.filepath:
            return
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.filepath) or '.', exist_ok=True)
        
        data = {
            'name': self.name,
            'created_at': self.created_at,
            'encrypted': self.encrypted,
            'encryption_salt': self.encryption_salt.hex() if self.encryption_salt else '',
            'hd_account_index': self.hd_account_index,
            'hd_address_index': self.hd_address_index,
            'addresses': [addr.to_dict_with_private() for addr in self.addresses],
        }
        
        # Only save mnemonic if not encrypted
        if self.mnemonic and not self.encrypted:
            data['mnemonic'] = self.mnemonic
        
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self) -> bool:
        """Load wallet from file."""
        if not self.filepath or not os.path.exists(self.filepath):
            return False
        
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
            
            self.name = data.get('name', 'Default Wallet')
            self.created_at = data.get('created_at', 0)
            self.encrypted = data.get('encrypted', False)
            self.encryption_salt = bytes.fromhex(data.get('encryption_salt', ''))
            self.hd_account_index = data.get('hd_account_index', 0)
            self.hd_address_index = data.get('hd_address_index', 0)
            
            self.addresses = [
                Address.from_dict(addr) for addr in data.get('addresses', [])
            ]
            
            # Load mnemonic if available
            if 'mnemonic' in data:
                self.mnemonic = data['mnemonic']
                seed = mnemonic_to_seed(self.mnemonic)
                self.master_key = ExtendedKey.from_seed(seed)
            
            self.locked = self.encrypted
            
            return True
            
        except Exception as e:
            print(f"Error loading wallet: {e}")
            return False
    
    def backup(self, backup_path: str):
        """
        Backup wallet to file.
        
        Args:
            backup_path: Path for backup file
        """
        import shutil
        
        if self.filepath and os.path.exists(self.filepath):
            shutil.copy2(self.filepath, backup_path)
        else:
            # Save current state to backup path
            original_path = self.filepath
            self.filepath = backup_path
            self.save()
            self.filepath = original_path
    
    def get_info(self) -> Dict[str, Any]:
        """Get wallet information."""
        return {
            'name': self.name,
            'encrypted': self.encrypted,
            'locked': self.locked,
            'hd_wallet': self.master_key is not None,
            'address_count': len(self.addresses),
            'created_at': self.created_at,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert wallet to dictionary (without sensitive data)."""
        return {
            'name': self.name,
            'encrypted': self.encrypted,
            'address_count': len(self.addresses),
            'addresses': [addr.to_dict() for addr in self.addresses],
            'created_at': self.created_at,
        }


class WalletManager:
    """Manages multiple wallets."""
    
    def __init__(self, wallet_dir: str = None):
        """
        Initialize wallet manager.
        
        Args:
            wallet_dir: Directory for wallet files
        """
        self.wallet_dir = wallet_dir or os.path.join(config.get_data_dir(), 'wallets')
        os.makedirs(self.wallet_dir, exist_ok=True)
        
        self.wallets: Dict[str, Wallet] = {}
        self.active_wallet: Optional[str] = None
    
    def create_wallet(self, name: str, hd: bool = True, 
                      mnemonic: str = None) -> Wallet:
        """
        Create a new wallet.
        
        Args:
            name: Wallet name
            hd: Create HD wallet
            mnemonic: Optional mnemonic for HD wallet
            
        Returns:
            New wallet
        """
        filepath = os.path.join(self.wallet_dir, f"{name}.wallet")
        
        if os.path.exists(filepath):
            raise ValueError(f"Wallet already exists: {name}")
        
        wallet = Wallet(filepath=filepath, name=name)
        
        if hd:
            wallet.create_hd_wallet(mnemonic)
        else:
            wallet.create_address("Default Address")
        
        self.wallets[name] = wallet
        
        if self.active_wallet is None:
            self.active_wallet = name
        
        return wallet
    
    def load_wallet(self, name: str) -> Wallet:
        """Load a wallet by name."""
        filepath = os.path.join(self.wallet_dir, f"{name}.wallet")
        
        if not os.path.exists(filepath):
            raise ValueError(f"Wallet not found: {name}")
        
        wallet = Wallet(filepath=filepath)
        self.wallets[name] = wallet
        
        return wallet
    
    def get_wallet(self, name: str = None) -> Optional[Wallet]:
        """Get wallet by name or active wallet."""
        if name is None:
            name = self.active_wallet
        
        if name is None:
            return None
        
        if name not in self.wallets:
            try:
                return self.load_wallet(name)
            except Exception:
                return None
        
        return self.wallets.get(name)
    
    def list_wallets(self) -> List[str]:
        """List available wallet names."""
        wallets = []
        
        for filename in os.listdir(self.wallet_dir):
            if filename.endswith('.wallet'):
                wallets.append(filename[:-7])  # Remove .wallet extension
        
        return wallets
    
    def set_active(self, name: str):
        """Set active wallet."""
        if name not in self.list_wallets():
            raise ValueError(f"Wallet not found: {name}")
        
        self.active_wallet = name
    
    def get_default_wallet(self) -> Optional[Wallet]:
        """
        Get the default wallet.
        
        Creates a default wallet if none exists.
        
        Returns:
            Default wallet or None
        """
        # Try to get active wallet first
        if self.active_wallet:
            wallet = self.get_wallet(self.active_wallet)
            if wallet:
                return wallet
        
        # Try to load any existing wallet
        available = self.list_wallets()
        if available:
            wallet = self.load_wallet(available[0])
            self.active_wallet = available[0]
            return wallet
        
        # Create a default wallet if none exists
        try:
            wallet = self.create_wallet("default", hd=True)
            return wallet
        except Exception:
            return None
    
    def load_default(self) -> Optional[Wallet]:
        """
        Load the default wallet if it exists.
        
        Returns:
            Default wallet or None if not found
        """
        # Try to get active wallet first
        if self.active_wallet:
            wallet = self.get_wallet(self.active_wallet)
            if wallet:
                return wallet
        
        # Try to load any existing wallet
        available = self.list_wallets()
        if available:
            try:
                wallet = self.load_wallet(available[0])
                self.active_wallet = available[0]
                return wallet
            except Exception:
                pass
        
        return None
