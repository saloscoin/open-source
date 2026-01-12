"""
Tests for SALOCOIN crypto utilities.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.crypto import (
    sha256,
    sha256d,
    hash160,
    generate_keypair,
    sign_message,
    verify_signature,
    base58check_encode,
    base58check_decode,
    ExtendedKey,
)
import config


class TestHashing:
    """Test hashing functions."""
    
    def test_sha256(self):
        """Test SHA-256 hashing."""
        data = b"SALOCOIN"
        result = sha256(data)
        
        assert isinstance(result, bytes)
        assert len(result) == 32
        
    def test_sha256d(self):
        """Test double SHA-256 hashing."""
        data = b"SALOCOIN"
        result = sha256d(data)
        
        assert isinstance(result, bytes)
        assert len(result) == 32
        
        # Should be different from single SHA-256
        assert result != sha256(data)
        
        # Should equal SHA-256(SHA-256(data))
        assert result == sha256(sha256(data))
    
    def test_hash160(self):
        """Test HASH160 (SHA-256 + RIPEMD-160)."""
        data = b"SALOCOIN"
        result = hash160(data)
        
        assert isinstance(result, bytes)
        assert len(result) == 20
    
    def test_hash_consistency(self):
        """Test that hashing is deterministic."""
        data = b"test data"
        
        result1 = sha256d(data)
        result2 = sha256d(data)
        
        assert result1 == result2


class TestKeyPairs:
    """Test key pair generation and operations."""
    
    def test_generate_keypair(self):
        """Test key pair generation."""
        # generate_keypair returns (private_key, public_key)
        privkey, pubkey = generate_keypair()
        
        assert isinstance(pubkey, bytes)
        assert isinstance(privkey, bytes)
        assert len(privkey) == 32
        assert len(pubkey) in [33, 65]  # Compressed or uncompressed
    
    def test_keypair_uniqueness(self):
        """Test that generated key pairs are unique."""
        privkey1, pubkey1 = generate_keypair()
        privkey2, pubkey2 = generate_keypair()
        
        assert privkey1 != privkey2
        assert pubkey1 != pubkey2
    
    def test_sign_and_verify(self):
        """Test message signing and verification."""
        privkey, pubkey = generate_keypair()
        message = b"Hello SALOCOIN"
        
        signature = sign_message(privkey, message)
        
        assert isinstance(signature, bytes)
        assert len(signature) > 0
        
        # Verify signature
        valid = verify_signature(pubkey, message, signature)
        assert valid is True
    
    def test_verify_wrong_message(self):
        """Test that verification fails for wrong message."""
        privkey, pubkey = generate_keypair()
        message = b"Hello SALOCOIN"
        
        signature = sign_message(privkey, message)
        
        # Try to verify with wrong message
        valid = verify_signature(pubkey, b"Wrong message", signature)
        assert valid is False
    
    def test_verify_wrong_pubkey(self):
        """Test that verification fails for wrong public key."""
        privkey1, pubkey1 = generate_keypair()
        privkey2, pubkey2 = generate_keypair()
        message = b"Hello SALOCOIN"
        
        signature = sign_message(privkey1, message)
        
        # Try to verify with wrong public key
        valid = verify_signature(pubkey2, message, signature)
        assert valid is False


class TestBase58:
    """Test Base58Check encoding/decoding."""
    
    def test_encode_decode_roundtrip(self):
        """Test Base58Check encode/decode roundtrip."""
        version = config.MAINNET_PUBKEY_ADDRESS_PREFIX
        payload = b'\x00' * 20
        
        encoded = base58check_encode(version, payload)
        decoded_version, decoded_payload = base58check_decode(encoded)
        
        assert decoded_version == version
        assert decoded_payload == payload
    
    def test_address_prefix(self):
        """Test that addresses have correct prefix."""
        # Version 63 should produce 'S' prefix
        version = 63
        payload = b'\x00' * 20
        encoded = base58check_encode(version, payload)
        
        assert encoded[0] == 'S'
    
    def test_invalid_checksum(self):
        """Test that invalid checksum is rejected."""
        version = config.MAINNET_PUBKEY_ADDRESS_PREFIX
        payload = b'\x00' * 20
        encoded = base58check_encode(version, payload)
        
        # Corrupt the encoded string
        chars = list(encoded)
        chars[-1] = 'X' if chars[-1] != 'X' else 'Y'
        corrupted = ''.join(chars)
        
        with pytest.raises(ValueError):
            base58check_decode(corrupted)


class TestExtendedKey:
    """Test BIP32 extended keys."""
    
    def test_from_seed(self):
        """Test creating extended key from seed."""
        seed = b'\x00' * 32
        key = ExtendedKey.from_seed(seed)
        
        assert key is not None
        assert key.depth == 0
        assert key.child_number == 0
    
    def test_child_derivation(self):
        """Test child key derivation."""
        seed = b'\x00' * 32
        master = ExtendedKey.from_seed(seed)
        
        # Derive child
        child = master.derive_child(0)
        
        assert child.depth == 1
        assert child.child_number == 0
        assert child.key != master.key
    
    def test_hardened_derivation(self):
        """Test hardened child derivation."""
        seed = b'\x00' * 32
        master = ExtendedKey.from_seed(seed)
        
        # Derive hardened child (index >= 0x80000000)
        hardened = master.derive_child(0x80000000)
        normal = master.derive_child(0)
        
        # Hardened and normal should be different
        assert hardened.key != normal.key
    
    def test_path_derivation(self):
        """Test deriving from path string."""
        seed = b'\x00' * 32
        master = ExtendedKey.from_seed(seed)
        
        # BIP44 path for SALOCOIN: m/44'/9339'/0'/0/0
        # Manual derivation
        key = master
        key = key.derive_child(44 + 0x80000000)   # 44'
        key = key.derive_child(9339 + 0x80000000)  # 9339'
        key = key.derive_child(0 + 0x80000000)    # 0'
        key = key.derive_child(0)                  # 0
        key = key.derive_child(0)                  # 0
        
        assert key.depth == 5
    
    def test_deterministic(self):
        """Test that derivation is deterministic."""
        seed = b'\x12\x34' * 16
        
        master1 = ExtendedKey.from_seed(seed)
        master2 = ExtendedKey.from_seed(seed)
        
        child1 = master1.derive_child(0)
        child2 = master2.derive_child(0)
        
        assert child1.key == child2.key


class TestBlockReward:
    """Test block reward calculations."""
    
    def test_initial_reward(self):
        """Test initial block reward."""
        from config import calculate_block_reward, INITIAL_BLOCK_REWARD
        
        reward = calculate_block_reward(0)
        assert reward == INITIAL_BLOCK_REWARD
    
    def test_halving(self):
        """Test reward halving."""
        from config import calculate_block_reward, HALVING_INTERVAL, INITIAL_BLOCK_REWARD
        
        # Before first halving
        reward_before = calculate_block_reward(HALVING_INTERVAL - 1)
        assert reward_before == INITIAL_BLOCK_REWARD
        
        # After first halving
        reward_after = calculate_block_reward(HALVING_INTERVAL)
        assert reward_after == INITIAL_BLOCK_REWARD // 2
    
    def test_multiple_halvings(self):
        """Test multiple halvings."""
        from config import calculate_block_reward, HALVING_INTERVAL, INITIAL_BLOCK_REWARD
        
        # After 3 halvings
        reward = calculate_block_reward(HALVING_INTERVAL * 3)
        expected = INITIAL_BLOCK_REWARD >> 3  # Divide by 8
        
        assert reward == expected
    
    def test_minimum_reward(self):
        """Test minimum block reward."""
        from config import calculate_block_reward, HALVING_INTERVAL, MIN_BLOCK_REWARD
        
        # After many halvings
        reward = calculate_block_reward(HALVING_INTERVAL * 100)
        
        assert reward >= MIN_BLOCK_REWARD


class TestRewardDistribution:
    """Test reward distribution calculations."""
    
    def test_distribution_percentages(self):
        """Test reward distribution adds up correctly."""
        from config import calculate_reward_distribution
        
        dist = calculate_reward_distribution(0)
        
        # Should add up to approximately total (may have rounding)
        total = dist['masternode'] + dist['miner'] + dist['treasury']
        assert abs(total - dist['total']) <= 2  # Allow for rounding
    
    def test_reward_distribution_exists(self):
        """Test reward distribution returns valid values."""
        from config import calculate_reward_distribution
        
        dist = calculate_reward_distribution(0)
        
        # All values should be non-negative
        assert dist['masternode'] >= 0
        assert dist['miner'] >= 0
        assert dist['treasury'] >= 0
        assert dist['total'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
