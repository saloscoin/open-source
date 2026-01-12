"""
SALOCOIN Cryptographic Utilities
SHA-256d, ECDSA secp256k1, BIP32/39/44 support
"""

import hashlib
import hmac
import os
import secrets
from typing import Tuple, Optional, List
from dataclasses import dataclass

try:
    from ecdsa import SECP256k1, SigningKey, VerifyingKey, BadSignatureError
    from ecdsa.util import sigencode_der, sigdecode_der
    ECDSA_AVAILABLE = True
except ImportError:
    ECDSA_AVAILABLE = False


# ============================================================================
# HASHING FUNCTIONS
# ============================================================================

def sha256(data: bytes) -> bytes:
    """Single SHA-256 hash."""
    return hashlib.sha256(data).digest()


def sha256d(data: bytes) -> bytes:
    """
    Double SHA-256 hash (Bitcoin-style).
    Used for block hashes, transaction hashes, etc.
    """
    return sha256(sha256(data))


def sha512(data: bytes) -> bytes:
    """SHA-512 hash."""
    return hashlib.sha512(data).digest()


def ripemd160(data: bytes) -> bytes:
    """RIPEMD-160 hash with fallback for systems without OpenSSL legacy support."""
    try:
        h = hashlib.new('ripemd160')
        h.update(data)
        return h.digest()
    except ValueError:
        # Fallback: use pure Python implementation for systems where ripemd160 is unsupported
        # (e.g., Ubuntu 22.04+ with OpenSSL 3.0)
        try:
            from Crypto.Hash import RIPEMD160
            return RIPEMD160.new(data).digest()
        except ImportError:
            # Pure Python fallback implementation of RIPEMD-160
            return _ripemd160_pure(data)


def _ripemd160_pure(data: bytes) -> bytes:
    """Pure Python RIPEMD-160 implementation for systems without OpenSSL support."""
    # Constants
    K = [0x00000000, 0x5a827999, 0x6ed9eba1, 0x8f1bbcdc, 0xa953fd4e]
    KP = [0x50a28be6, 0x5c4dd124, 0x6d703ef3, 0x7a6d76e9, 0x00000000]
    
    # Selection of message word
    R = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,
         7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,
         3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,
         1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,
         4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13]
    RP = [5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,
          6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,
          15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,
          8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14,
          12,15,10,4,1,5,8,7,6,2,13,14,0,3,9,11]
    
    # Amount of rotate left
    S = [11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,
         7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,
         11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,
         11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12,
         9,15,5,11,6,8,13,12,5,12,13,14,11,8,5,6]
    SP = [8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,
          9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,
          9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,
          15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8,
          8,5,12,9,12,5,14,6,8,13,6,5,15,13,11,11]
    
    def ROL(x, n):
        return ((x << n) | (x >> (32 - n))) & 0xffffffff
    
    def f(j, x, y, z):
        if j < 16: return x ^ y ^ z
        elif j < 32: return (x & y) | (~x & z)
        elif j < 48: return (x | ~y) ^ z
        elif j < 64: return (x & z) | (y & ~z)
        else: return x ^ (y | ~z)
    
    # Padding
    msg = bytearray(data)
    msg_len = len(data)
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0x00)
    msg += (msg_len * 8).to_bytes(8, 'little')
    
    # Initial hash values
    h0, h1, h2, h3, h4 = 0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476, 0xc3d2e1f0
    
    # Process each 64-byte block
    for i in range(0, len(msg), 64):
        block = msg[i:i+64]
        X = [int.from_bytes(block[j:j+4], 'little') for j in range(0, 64, 4)]
        
        A, B, C, D, E = h0, h1, h2, h3, h4
        AP, BP, CP, DP, EP = h0, h1, h2, h3, h4
        
        for j in range(80):
            rnd = j // 16
            T = (A + f(j, B, C, D) + X[R[j]] + K[rnd]) & 0xffffffff
            T = (ROL(T, S[j]) + E) & 0xffffffff
            A, E, D, C, B = E, D, ROL(C, 10), B, T
            
            T = (AP + f(79-j, BP, CP, DP) + X[RP[j]] + KP[rnd]) & 0xffffffff
            T = (ROL(T, SP[j]) + EP) & 0xffffffff
            AP, EP, DP, CP, BP = EP, DP, ROL(CP, 10), BP, T
        
        T = (h1 + C + DP) & 0xffffffff
        h1 = (h2 + D + EP) & 0xffffffff
        h2 = (h3 + E + AP) & 0xffffffff
        h3 = (h4 + A + BP) & 0xffffffff
        h4 = (h0 + B + CP) & 0xffffffff
        h0 = T
    
    return b''.join(x.to_bytes(4, 'little') for x in [h0, h1, h2, h3, h4])


def hash160(data: bytes) -> bytes:
    """
    HASH160 = RIPEMD160(SHA256(data))
    Used for address generation.
    """
    return ripemd160(sha256(data))


def hash256(data: bytes) -> bytes:
    """Alias for sha256d."""
    return sha256d(data)


def hmac_sha256(key: bytes, data: bytes) -> bytes:
    """HMAC-SHA256."""
    return hmac.new(key, data, hashlib.sha256).digest()


def hmac_sha512(key: bytes, data: bytes) -> bytes:
    """HMAC-SHA512."""
    return hmac.new(key, data, hashlib.sha512).digest()


# ============================================================================
# ECDSA SECP256K1
# ============================================================================

def generate_private_key() -> bytes:
    """Generate a random 256-bit private key."""
    return secrets.token_bytes(32)


def private_key_to_public_key(private_key: bytes, compressed: bool = True) -> bytes:
    """
    Derive public key from private key.
    
    Args:
        private_key: 32-byte private key
        compressed: If True, return 33-byte compressed public key
        
    Returns:
        Public key bytes
    """
    if not ECDSA_AVAILABLE:
        raise ImportError("ecdsa library required for key operations")
    
    sk = SigningKey.from_string(private_key, curve=SECP256k1)
    vk = sk.get_verifying_key()
    
    if compressed:
        # Compressed public key: 02/03 prefix + x coordinate
        x = vk.pubkey.point.x()
        y = vk.pubkey.point.y()
        prefix = b'\x02' if y % 2 == 0 else b'\x03'
        return prefix + x.to_bytes(32, 'big')
    else:
        # Uncompressed: 04 prefix + x + y
        return b'\x04' + vk.to_string()


def generate_keypair(compressed: bool = True) -> Tuple[bytes, bytes]:
    """
    Generate a new ECDSA keypair.
    
    Args:
        compressed: If True, return compressed public key
        
    Returns:
        Tuple of (private_key, public_key)
    """
    private_key = generate_private_key()
    public_key = private_key_to_public_key(private_key, compressed)
    return private_key, public_key


def sign_message(private_key: bytes, message: bytes) -> bytes:
    """
    Sign a message with ECDSA.
    
    Args:
        private_key: 32-byte private key
        message: Message to sign (will be hashed with SHA256d)
        
    Returns:
        DER-encoded signature
    """
    if not ECDSA_AVAILABLE:
        raise ImportError("ecdsa library required for signing")
    
    sk = SigningKey.from_string(private_key, curve=SECP256k1)
    message_hash = sha256d(message)
    signature = sk.sign_digest(message_hash, sigencode=sigencode_der)
    return signature


def verify_signature(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """
    Verify an ECDSA signature.
    
    Args:
        public_key: Public key (compressed or uncompressed)
        message: Original message
        signature: DER-encoded signature
        
    Returns:
        True if signature is valid
    """
    if not ECDSA_AVAILABLE:
        raise ImportError("ecdsa library required for verification")
    
    try:
        # Decompress public key if needed
        if len(public_key) == 33:
            vk = decompress_public_key(public_key)
        elif len(public_key) == 65:
            vk = VerifyingKey.from_string(public_key[1:], curve=SECP256k1)
        else:
            return False
        
        message_hash = sha256d(message)
        return vk.verify_digest(signature, message_hash, sigdecode=sigdecode_der)
    except (BadSignatureError, Exception):
        return False


def decompress_public_key(compressed: bytes) -> 'VerifyingKey':
    """
    Decompress a compressed public key.
    
    Args:
        compressed: 33-byte compressed public key
        
    Returns:
        VerifyingKey object
    """
    if not ECDSA_AVAILABLE:
        raise ImportError("ecdsa library required")
    
    if len(compressed) != 33:
        raise ValueError("Invalid compressed public key length")
    
    prefix = compressed[0]
    x = int.from_bytes(compressed[1:], 'big')
    
    # Curve parameters for secp256k1
    p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
    
    # Calculate y^2 = x^3 + 7 (mod p)
    y_squared = (pow(x, 3, p) + 7) % p
    
    # Calculate y using Tonelli-Shanks algorithm
    y = pow(y_squared, (p + 1) // 4, p)
    
    # Choose correct y based on prefix
    if prefix == 0x02:
        y = y if y % 2 == 0 else p - y
    elif prefix == 0x03:
        y = y if y % 2 == 1 else p - y
    else:
        raise ValueError("Invalid public key prefix")
    
    # Reconstruct uncompressed public key
    uncompressed = x.to_bytes(32, 'big') + y.to_bytes(32, 'big')
    return VerifyingKey.from_string(uncompressed, curve=SECP256k1)


# ============================================================================
# BASE58CHECK ENCODING
# ============================================================================

BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def base58_encode(data: bytes) -> str:
    """Encode bytes to Base58."""
    num = int.from_bytes(data, 'big')
    
    result = ''
    while num > 0:
        num, remainder = divmod(num, 58)
        result = BASE58_ALPHABET[remainder] + result
    
    # Handle leading zeros
    for byte in data:
        if byte == 0:
            result = '1' + result
        else:
            break
    
    return result or '1'


def base58_decode(string: str) -> bytes:
    """Decode Base58 string to bytes."""
    num = 0
    for char in string:
        num = num * 58 + BASE58_ALPHABET.index(char)
    
    # Calculate result length
    result = []
    while num > 0:
        result.append(num & 0xff)
        num >>= 8
    
    # Handle leading '1's (zeros)
    for char in string:
        if char == '1':
            result.append(0)
        else:
            break
    
    return bytes(reversed(result))


def base58check_encode(version: int, payload: bytes) -> str:
    """
    Encode data with Base58Check (version byte + payload + checksum).
    
    Args:
        version: Version byte
        payload: Data to encode
        
    Returns:
        Base58Check encoded string
    """
    data = bytes([version]) + payload
    checksum = sha256d(data)[:4]
    return base58_encode(data + checksum)


def base58check_decode(string: str) -> Tuple[int, bytes]:
    """
    Decode Base58Check string.
    
    Args:
        string: Base58Check encoded string
        
    Returns:
        Tuple of (version, payload)
        
    Raises:
        ValueError: If checksum is invalid
    """
    data = base58_decode(string)
    
    if len(data) < 5:
        raise ValueError("Invalid Base58Check string")
    
    payload = data[:-4]
    checksum = data[-4:]
    
    if sha256d(payload)[:4] != checksum:
        raise ValueError("Invalid Base58Check checksum")
    
    return payload[0], payload[1:]


# ============================================================================
# ADDRESS GENERATION
# ============================================================================

def public_key_to_address(public_key: bytes, version: int = 63) -> str:
    """
    Generate address from public key.
    
    Args:
        public_key: Public key bytes
        version: Address version byte (63 for SALO mainnet = 'S' prefix)
        
    Returns:
        Base58Check encoded address
    """
    pubkey_hash = hash160(public_key)
    return base58check_encode(version, pubkey_hash)


def private_key_to_wif(private_key: bytes, version: int = 191, compressed: bool = True) -> str:
    """
    Encode private key to Wallet Import Format (WIF).
    
    Args:
        private_key: 32-byte private key
        version: WIF version byte (191 for SALO mainnet)
        compressed: If True, indicate compressed public key
        
    Returns:
        WIF encoded private key
    """
    payload = private_key
    if compressed:
        payload = payload + b'\x01'
    return base58check_encode(version, payload)


def wif_to_private_key(wif: str) -> Tuple[bytes, bool]:
    """
    Decode WIF to private key.
    
    Args:
        wif: WIF encoded private key
        
    Returns:
        Tuple of (private_key, compressed)
    """
    version, payload = base58check_decode(wif)
    
    if len(payload) == 33 and payload[-1] == 1:
        return payload[:-1], True
    elif len(payload) == 32:
        return payload, False
    else:
        raise ValueError("Invalid WIF format")


# ============================================================================
# BIP39 MNEMONIC SUPPORT
# ============================================================================

# BIP39 English wordlist (2048 words)
BIP39_WORDLIST_EN = None  # Loaded on demand


def load_bip39_wordlist() -> List[str]:
    """Load BIP39 English wordlist."""
    global BIP39_WORDLIST_EN
    
    if BIP39_WORDLIST_EN is not None:
        return BIP39_WORDLIST_EN
    
    # Try to load from file or use embedded list
    wordlist_path = os.path.join(os.path.dirname(__file__), 'wordlist', 'english.txt')
    
    if os.path.exists(wordlist_path):
        with open(wordlist_path, 'r') as f:
            BIP39_WORDLIST_EN = [word.strip() for word in f.readlines()]
    else:
        # Fallback: generate placeholder (should be replaced with actual wordlist)
        BIP39_WORDLIST_EN = []
    
    return BIP39_WORDLIST_EN


def generate_mnemonic(strength: int = 256) -> str:
    """
    Generate BIP39 mnemonic phrase.
    
    Args:
        strength: Entropy bits (128, 160, 192, 224, or 256)
        
    Returns:
        Mnemonic phrase (space-separated words)
    """
    if strength not in [128, 160, 192, 224, 256]:
        raise ValueError("Invalid strength, must be 128, 160, 192, 224, or 256")
    
    wordlist = load_bip39_wordlist()
    if not wordlist:
        raise RuntimeError("BIP39 wordlist not available")
    
    # Generate entropy
    entropy = secrets.token_bytes(strength // 8)
    
    # Calculate checksum
    h = sha256(entropy)
    checksum_bits = strength // 32
    
    # Combine entropy and checksum
    entropy_int = int.from_bytes(entropy, 'big')
    checksum_int = h[0] >> (8 - checksum_bits)
    combined = (entropy_int << checksum_bits) | checksum_int
    
    # Convert to mnemonic
    word_count = (strength + checksum_bits) // 11
    words = []
    
    for i in range(word_count):
        word_index = (combined >> (11 * (word_count - 1 - i))) & 0x7FF
        words.append(wordlist[word_index])
    
    return ' '.join(words)


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    """
    Convert BIP39 mnemonic to seed.
    
    Args:
        mnemonic: Mnemonic phrase
        passphrase: Optional passphrase
        
    Returns:
        512-bit seed
    """
    import hashlib
    
    salt = ("mnemonic" + passphrase).encode('utf-8')
    mnemonic_bytes = mnemonic.encode('utf-8')
    
    # PBKDF2-HMAC-SHA512 with 2048 iterations
    seed = hashlib.pbkdf2_hmac('sha512', mnemonic_bytes, salt, 2048)
    return seed


# ============================================================================
# BIP32 HD WALLET
# ============================================================================

@dataclass
class ExtendedKey:
    """BIP32 Extended Key."""
    key: bytes          # 33 bytes (public) or 32 bytes (private)
    chain_code: bytes   # 32 bytes
    depth: int          # 0-255
    parent_fingerprint: bytes  # 4 bytes
    child_number: int   # 0 to 2^31-1 (or 2^31 to 2^32-1 for hardened)
    is_private: bool
    version: int        # 4 bytes, network version
    
    def get_fingerprint(self) -> bytes:
        """Get fingerprint (first 4 bytes of HASH160 of public key)."""
        if self.is_private:
            pubkey = private_key_to_public_key(self.key)
        else:
            pubkey = self.key
        return hash160(pubkey)[:4]
    
    def serialize(self) -> str:
        """Serialize to Base58Check encoded string (xpub/xprv)."""
        data = self.version.to_bytes(4, 'big')
        data += bytes([self.depth])
        data += self.parent_fingerprint
        data += self.child_number.to_bytes(4, 'big')
        data += self.chain_code
        
        if self.is_private:
            data += b'\x00' + self.key
        else:
            data += self.key
        
        checksum = sha256d(data)[:4]
        return base58_encode(data + checksum)
    
    @classmethod
    def from_seed(cls, seed: bytes, version: int = 0x0488ADE4) -> 'ExtendedKey':
        """
        Create master key from seed.
        
        Args:
            seed: 64-byte seed (from mnemonic)
            version: Network version (xprv for mainnet)
            
        Returns:
            Master ExtendedKey
        """
        I = hmac_sha512(b"Bitcoin seed", seed)  # Same as Bitcoin
        master_key = I[:32]
        chain_code = I[32:]
        
        return cls(
            key=master_key,
            chain_code=chain_code,
            depth=0,
            parent_fingerprint=b'\x00\x00\x00\x00',
            child_number=0,
            is_private=True,
            version=version
        )
    
    def derive_child(self, index: int) -> 'ExtendedKey':
        """
        Derive child key (BIP32).
        
        Args:
            index: Child index (>= 0x80000000 for hardened)
            
        Returns:
            Child ExtendedKey
        """
        if not ECDSA_AVAILABLE:
            raise ImportError("ecdsa library required for key derivation")
        
        hardened = index >= 0x80000000
        
        if hardened:
            if not self.is_private:
                raise ValueError("Cannot derive hardened child from public key")
            data = b'\x00' + self.key + index.to_bytes(4, 'big')
        else:
            if self.is_private:
                pubkey = private_key_to_public_key(self.key)
            else:
                pubkey = self.key
            data = pubkey + index.to_bytes(4, 'big')
        
        I = hmac_sha512(self.chain_code, data)
        child_key_add = I[:32]
        child_chain = I[32:]
        
        # Calculate child key
        order = SECP256k1.order
        child_key_int = (int.from_bytes(child_key_add, 'big') + 
                         int.from_bytes(self.key, 'big')) % order
        child_key = child_key_int.to_bytes(32, 'big')
        
        return ExtendedKey(
            key=child_key,
            chain_code=child_chain,
            depth=self.depth + 1,
            parent_fingerprint=self.get_fingerprint(),
            child_number=index,
            is_private=self.is_private,
            version=self.version
        )
    
    def derive_path(self, path: str) -> 'ExtendedKey':
        """
        Derive key from BIP32 path.
        
        Args:
            path: Derivation path (e.g., "m/44'/9339'/0'/0/0")
            
        Returns:
            Derived ExtendedKey
        """
        if path.startswith('m/'):
            path = path[2:]
        elif path == 'm':
            return self
        
        key = self
        for level in path.split('/'):
            if not level:
                continue
            
            hardened = level.endswith("'") or level.endswith('h')
            index = int(level.rstrip("'h"))
            
            if hardened:
                index += 0x80000000
            
            key = key.derive_child(index)
        
        return key


def create_hd_wallet(mnemonic: str = None, passphrase: str = "") -> Tuple[str, ExtendedKey]:
    """
    Create a new HD wallet.
    
    Args:
        mnemonic: Optional mnemonic (generates new if None)
        passphrase: Optional passphrase
        
    Returns:
        Tuple of (mnemonic, master_key)
    """
    if mnemonic is None:
        mnemonic = generate_mnemonic()
    
    seed = mnemonic_to_seed(mnemonic, passphrase)
    master_key = ExtendedKey.from_seed(seed)
    
    return mnemonic, master_key


# ============================================================================
# MERKLE TREE
# ============================================================================

def merkle_root(hashes: List[bytes]) -> bytes:
    """
    Calculate Merkle root of transaction hashes.
    
    Args:
        hashes: List of transaction hashes
        
    Returns:
        Merkle root hash
    """
    if not hashes:
        return b'\x00' * 32
    
    if len(hashes) == 1:
        return hashes[0]
    
    # Make a copy and ensure even number
    level = list(hashes)
    if len(level) % 2 == 1:
        level.append(level[-1])
    
    # Build tree
    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            combined = level[i] + level[i + 1]
            next_level.append(sha256d(combined))
        
        level = next_level
        if len(level) > 1 and len(level) % 2 == 1:
            level.append(level[-1])
    
    return level[0]


# ============================================================================
# PROOF OF WORK
# ============================================================================

def check_proof_of_work(block_hash: bytes, target: int) -> bool:
    """
    Check if block hash meets difficulty target.
    
    Args:
        block_hash: 32-byte block hash
        target: Difficulty target
        
    Returns:
        True if hash meets target
    """
    hash_int = int.from_bytes(block_hash, 'big')
    return hash_int < target


def compact_to_target(bits: int) -> int:
    """
    Convert compact difficulty representation to target.
    
    Args:
        bits: Compact difficulty (nBits)
        
    Returns:
        Full target value
    """
    exponent = bits >> 24
    mantissa = bits & 0x007fffff
    
    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        target = mantissa << (8 * (exponent - 3))
    
    return target


def target_to_compact(target: int) -> int:
    """
    Convert target to compact difficulty representation.
    
    Args:
        target: Full target value
        
    Returns:
        Compact difficulty (nBits)
    """
    # Count leading zero bytes
    size = (target.bit_length() + 7) // 8
    
    if size <= 3:
        mantissa = target << (8 * (3 - size))
    else:
        mantissa = target >> (8 * (size - 3))
    
    # Ensure positive (set high bit to 0 if needed)
    if mantissa & 0x00800000:
        mantissa >>= 8
        size += 1
    
    return (size << 24) | (mantissa & 0x007fffff)
