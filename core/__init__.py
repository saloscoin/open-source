"""
SALOCOIN Core Module
Contains blockchain, transactions, wallet, and crypto primitives.
"""

from .blockchain import Blockchain, Block
from .transaction import Transaction, TxInput, TxOutput
from .wallet import Wallet, Address
from .crypto import (
    sha256d,
    hash160,
    generate_keypair,
    sign_message,
    verify_signature,
)

__all__ = [
    'Blockchain',
    'Block',
    'Transaction',
    'TxInput',
    'TxOutput',
    'Wallet',
    'Address',
    'sha256d',
    'hash160',
    'generate_keypair',
    'sign_message',
    'verify_signature',
]
