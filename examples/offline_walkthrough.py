#!/usr/bin/env python3
"""Explore keys, signatures and a block template without connecting to a network."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from core.blockchain import Block
from core.crypto import verify_signature
from core.transaction import Transaction
from core.wallet import Wallet


def run_demo():
    """Use disposable keys and temporary storage; never mine or broadcast."""
    with TemporaryDirectory(prefix='salocoin-example-') as directory:
        wallet_path = str(Path(directory) / 'demo.wallet')
        wallet = Wallet(filepath=wallet_path, name='Disposable example')
        address = wallet.create_address('Example miner')
        message = b'Learning with SALOCOIN'
        signature = address.sign(message)
        signature_valid = verify_signature(address.public_key, message, signature)
        tampered_rejected = not verify_signature(
            address.public_key, b'Changed message', signature)
        restored = Wallet(filepath=wallet_path)
        restored_key_matches = (
            restored.addresses[0].private_key == address.private_key)

        coinbase = Transaction.create_coinbase(
            block_height=1, miner_address=address.address,
            extra_data='offline learning example')
        block = Block(
            version=config.BLOCK_VERSION, height=1,
            previous_hash=config.GENESIS_HASH,
            timestamp=config.GENESIS_BLOCK['timestamp'] + config.BLOCK_TIME_TARGET,
            merkle_root='', difficulty=config.INITIAL_DIFFICULTY,
            nonce=0, transactions=[coinbase.to_dict()])
        block.merkle_root = block.calculate_merkle_root()
        header_bytes = len(block.serialize_header())
        if not all((signature_valid, tampered_rejected, restored_key_matches)):
            raise RuntimeError('Offline walkthrough checks failed')
        return {
            'signature_verified': signature_valid,
            'changed_message_rejected': tampered_rejected,
            'wallet_reload_verified': restored_key_matches,
            'block_template_height': block.height,
            'block_header_bytes': header_bytes,
            'template_mined_or_broadcast': False,
        }


if __name__ == '__main__':
    print(json.dumps(run_demo(), indent=2))
