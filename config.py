"""
SALOCOIN Configuration
Enterprise-Grade Masternode Cryptocurrency
"""

from typing import Dict, Any
import os

# ============================================================================
# CORE SPECIFICATIONS
# ============================================================================

COIN_NAME = "SALOCOIN"
COIN_TICKER = "SALO"
COIN_UNIT = 100_000_000  # Satoshis per SALO (8 decimal places)

# Maximum Supply: 39,000,000 SALO
MAX_SUPPLY = 39_000_000 * COIN_UNIT

# ============================================================================
# NETWORK PORTS
# ============================================================================

# Mainnet
P2P_PORT = 7339
RPC_PORT = 7340
MASTERNODE_PORT = 7341

# Testnet
TESTNET_P2P_PORT = 17339
TESTNET_RPC_PORT = 17340
TESTNET_MASTERNODE_PORT = 17341

# Mining Pool Port
MINING_POOL_PORT = 39261

# ============================================================================
# BLOCK PARAMETERS
# ============================================================================

# Block version
BLOCK_VERSION = 1

# Block time: 150 seconds (2.5 minutes)
BLOCK_TIME_TARGET = 150

# Block reward: 100 SALO (Bitcoin-style halving)
INITIAL_BLOCK_REWARD = 100 * COIN_UNIT

# Halving schedule (Bitcoin-style - reduces by 50% at each milestone)
# Halving every 210,000 blocks (~1 year at 2.5 min blocks)
HALVING_INTERVAL = 210_000

# Reward milestones:
# Blocks 0 - 209,999:       100 SALO
# Blocks 210,000 - 419,999:  50 SALO
# Blocks 420,000 - 629,999:  25 SALO
# Blocks 630,000 - 839,999:  12.5 SALO
# Blocks 840,000 - 1,049,999: 6.25 SALO
# Blocks 1,050,000 - 1,259,999: 3.125 SALO
# Blocks 1,260,000 - 1,469,999: 1.5625 SALO
# Blocks 1,470,000 - 1,679,999: 0.78125 SALO
# Blocks 1,680,000 - 1,889,999: 0.390625 SALO
# Blocks 1,890,000 - 2,099,999: 0.1953125 SALO
# After block 2,100,000: 0.1 SALO (minimum)

# Minimum block reward (after all halvings)
MIN_BLOCK_REWARD = COIN_UNIT // 10  # 0.1 SALO minimum

# ============================================================================
# REWARD DISTRIBUTION
# ============================================================================

# Masternodes: 0%
MASTERNODE_REWARD_PERCENT = 0

# Miners: 100% (full block reward)
MINER_REWARD_PERCENT = 100

# Treasury/Development: 0%
TREASURY_REWARD_PERCENT = 0


def calculate_block_reward(height: int) -> int:
    """
    Calculate block reward at given height with Bitcoin-style halving.
    
    Reward Schedule:
    - Blocks 0 - 209,999:       100 SALO
    - Blocks 210,000 - 419,999:  50 SALO
    - Blocks 420,000 - 629,999:  25 SALO
    - And so on... (halves every 210,000 blocks)
    
    Args:
        height: Block height
        
    Returns:
        Block reward in satoshis
    """
    halvings = height // HALVING_INTERVAL
    reward = INITIAL_BLOCK_REWARD >> halvings  # Right shift = divide by 2^halvings
    return max(reward, MIN_BLOCK_REWARD)


def get_difficulty_multiplier(height: int) -> int:
    """
    Get difficulty multiplier for block height.
    Increases base difficulty at milestone blocks for network security.
    
    Args:
        height: Block height
        
    Returns:
        Difficulty multiplier
    """
    multiplier = 1
    for milestone_height, mult in sorted(DIFFICULTY_MILESTONES.items()):
        if height >= milestone_height:
            multiplier = mult
        else:
            break
    return multiplier


def get_reward_schedule() -> list:
    """
    Get full reward schedule showing halving milestones.
    
    Returns:
        List of (start_block, end_block, reward) tuples
    """
    schedule = []
    reward = INITIAL_BLOCK_REWARD
    start = 0
    
    while reward > MIN_BLOCK_REWARD:
        end = start + HALVING_INTERVAL - 1
        schedule.append({
            'start_block': start,
            'end_block': end,
            'reward_salo': reward / COIN_UNIT,
            'total_coins': (HALVING_INTERVAL * reward) / COIN_UNIT
        })
        start = end + 1
        reward = reward >> 1  # Halve
    
    # Final era with minimum reward
    schedule.append({
        'start_block': start,
        'end_block': 'infinity',
        'reward_salo': MIN_BLOCK_REWARD / COIN_UNIT,
        'total_coins': 'ongoing'
    })
    
    return schedule


def calculate_reward_distribution(height: int) -> Dict[str, int]:
    """
    Calculate reward distribution at given height.
    
    Args:
        height: Block height
        
    Returns:
        Dictionary with masternode, miner, and treasury rewards
    """
    total_reward = calculate_block_reward(height)
    
    return {
        'masternode': (total_reward * MASTERNODE_REWARD_PERCENT) // 100,
        'miner': (total_reward * MINER_REWARD_PERCENT) // 100,
        'treasury': (total_reward * TREASURY_REWARD_PERCENT) // 100,
        'total': total_reward
    }


# ============================================================================
# MASTERNODE PARAMETERS
# ============================================================================

# Collateral: 15,000 SALO
MASTERNODE_COLLATERAL = 15_000 * COIN_UNIT

# Minimum confirmations for collateral
MASTERNODE_MIN_CONFIRMATIONS = 15

# Masternode payment maturity
MASTERNODE_MATURITY = 100

# Proof-of-Service check interval (seconds)
MASTERNODE_POS_CHECK_INTERVAL = 300

# Masternode ban score threshold
MASTERNODE_BAN_SCORE_THRESHOLD = 100

# Masternode expiration time (seconds)
MASTERNODE_EXPIRATION_SECONDS = 3600 * 24  # 24 hours

# ============================================================================
# CONSENSUS PARAMETERS
# ============================================================================

# Transaction confirmations required
TRANSACTION_CONFIRMATIONS = 6

# Coinbase maturity (blocks before coinbase can be spent)
COINBASE_MATURITY = 100

# Maximum block size (bytes)
MAX_BLOCK_SIZE = 2_000_000  # 2 MB

# Maximum transaction size (bytes)
MAX_TX_SIZE = 100_000  # 100 KB

# Minimum transaction fee (satoshis per byte)
MIN_TX_FEE_PER_BYTE = 1

# Default transaction fee (satoshis per KB)
DEFAULT_TX_FEE = 10000  # 0.0001 SALO per KB

# Dynamic fee estimation (Bitcoin-style)
FEE_ESTIMATION_BLOCKS = 10          # Look at last N blocks for fee analysis
MIN_FEE_RATE = 1                    # Minimum 1 sat/byte
MAX_FEE_RATE = 1000                 # Maximum 1000 sat/byte (safety cap)
TARGET_BLOCK_FILL_PERCENT = 50      # Target block utilization

# ============================================================================
# DIFFICULTY ADJUSTMENT (Dark Gravity Wave v3)
# ============================================================================

# Difficulty adjustment: every block (real-time adjustment)
DIFFICULTY_ADJUSTMENT_INTERVAL = 1

# Target timespan for difficulty calculation
DIFFICULTY_TARGET_TIMESPAN = BLOCK_TIME_TARGET * 24  # 24 blocks

# Number of blocks for DGW calculation
DGW_PAST_BLOCKS = 24

# Maximum difficulty adjustment per block (±200%)
# Smaller value = more gradual changes, less volatility
MAX_DIFFICULTY_ADJUSTMENT = 2

# Emergency difficulty reduction: If no block found for this many seconds,
# reduce difficulty. This prevents network stalls when miners leave.
# 10 minutes = 4x target block time (reasonable for small networks)
EMERGENCY_DIFFICULTY_THRESHOLD = BLOCK_TIME_TARGET * 4  # 10 minutes (600 seconds)

# Emergency difficulty reduction factor per threshold period
# Every 10 min without a block, difficulty is reduced by this factor
EMERGENCY_DIFFICULTY_REDUCTION = 2  # 2x easier per period (gradual)

# Initial difficulty (very easy for starting)
INITIAL_DIFFICULTY = 0x1e0fffff  # Low difficulty for genesis

# Minimum difficulty (floor - easiest allowed)
MIN_DIFFICULTY = 0x1e0fffff

# Maximum difficulty (ceiling - hardest allowed, prevents overflow)
# 0x1c00ffff allows for much higher difficulty than Bitcoin's initial
MAX_DIFFICULTY = 0x0100ffff  # Very hard - allows natural difficulty scaling

# Difficulty scaling milestones (increases base difficulty at block heights)
# This ensures network security grows with adoption
DIFFICULTY_MILESTONES = {
    0: 1,           # Genesis: normal difficulty
    1_000: 2,       # After 1K blocks: 2x harder
    10_000: 4,      # After 10K blocks: 4x harder  
    100_000: 8,     # After 100K blocks: 8x harder
    500_000: 16,    # After 500K blocks: 16x harder
    1_000_000: 32,  # After 1M blocks: 32x harder
    2_000_000: 64,  # After 2M blocks: 64x harder
}

# ============================================================================
# CHAIN SECURITY PARAMETERS
# ============================================================================

# Maximum reorg depth (blocks) - prevents deep chain reorganizations
# Bitcoin uses ~100, we use 100 for similar security
MAX_REORG_DEPTH = 100

# Coinbase maturity - number of confirmations before coinbase can be spent
# Bitcoin uses 100, we use 100 for security
COINBASE_MATURITY = 100

# Median Time Past (MTP) - number of blocks for median time calculation
# Bitcoin uses 11
MTP_BLOCK_COUNT = 11

# Maximum block timestamp in future (seconds)
# Bitcoin uses 2 hours
MAX_FUTURE_BLOCK_TIME = 7200  # 2 hours

# Minimum block timestamp must be greater than MTP of last 11 blocks
# This prevents timestamp manipulation attacks

# ============================================================================
# INSTANTSEND PARAMETERS
# ============================================================================

# InstantSend quorum size
INSTANTSEND_QUORUM_SIZE = 10

# InstantSend confirmations (0 = instant)
INSTANTSEND_CONFIRMATIONS = 0

# Maximum input value for InstantSend
INSTANTSEND_MAX_VALUE = 1000 * COIN_UNIT  # 1000 SALO

# ============================================================================
# PRIVATESEND PARAMETERS
# ============================================================================

# PrivateSend mixing rounds
PRIVATESEND_ROUNDS = 4

# PrivateSend denominations
PRIVATESEND_DENOMINATIONS = [
    10 * COIN_UNIT,      # 10 SALO
    1 * COIN_UNIT,       # 1 SALO
    COIN_UNIT // 10,     # 0.1 SALO
    COIN_UNIT // 100,    # 0.01 SALO
]

# Maximum PrivateSend amount
PRIVATESEND_MAX_AMOUNT = 10000 * COIN_UNIT  # 10,000 SALO

# Collateral transaction amount
PRIVATESEND_COLLATERAL = COIN_UNIT // 1000  # 0.001 SALO

# ============================================================================
# GOVERNANCE PARAMETERS
# ============================================================================

# Governance voting period (blocks)
GOVERNANCE_VOTING_PERIOD = 16616  # ~28 days

# Superblock interval (blocks)
SUPERBLOCK_INTERVAL = 16616

# Minimum governance proposal fee
GOVERNANCE_PROPOSAL_FEE = 5 * COIN_UNIT  # 5 SALO

# Minimum votes required (percentage of masternodes)
GOVERNANCE_MIN_VOTES_PERCENT = 10

# ============================================================================
# NETWORK PARAMETERS
# ============================================================================

# Magic bytes for network messages
MAINNET_MAGIC = b'\xf9\xbe\xb4\xd9'
TESTNET_MAGIC = b'\x0b\x11\x09\x07'

# Protocol version
PROTOCOL_VERSION = 70220

# Minimum protocol version
MIN_PROTOCOL_VERSION = 70210

# User agent
USER_AGENT = f"/{COIN_NAME}:1.0.0/"

# Maximum connections
MAX_CONNECTIONS = 256

# Connection timeout (seconds)
CONNECTION_TIMEOUT = 60

# Peer discovery interval (seconds)
PEER_DISCOVERY_INTERVAL = 60

# Maximum peer age (seconds)
MAX_PEER_AGE = 86400 * 7  # 7 days

# ============================================================================
# ADDRESS PARAMETERS
# ============================================================================

# Address prefixes (Base58Check)
MAINNET_PUBKEY_ADDRESS_PREFIX = 63  # 'S' prefix
MAINNET_SCRIPT_ADDRESS_PREFIX = 125  # 's' prefix
MAINNET_SECRET_KEY_PREFIX = 191  # 'V' prefix

TESTNET_PUBKEY_ADDRESS_PREFIX = 111  # 'm' or 'n' prefix
TESTNET_SCRIPT_ADDRESS_PREFIX = 196  # '2' prefix
TESTNET_SECRET_KEY_PREFIX = 239  # '9' or 'c' prefix

# BIP32 HD wallet versions
MAINNET_BIP32_PUBLIC = 0x0488B21E  # xpub
MAINNET_BIP32_PRIVATE = 0x0488ADE4  # xprv

TESTNET_BIP32_PUBLIC = 0x043587CF  # tpub
TESTNET_BIP32_PRIVATE = 0x04358394  # tprv

# BIP44 coin type
BIP44_COIN_TYPE = 9339  # Unique to SALOCOIN

# ============================================================================
# GENESIS BLOCK - HARDCODED - DO NOT MODIFY
# Network will reject any blocks that don't chain from this genesis
# ============================================================================

GENESIS_BLOCK = {
    'version': 1,
    'prev_hash': '0' * 64,
    'timestamp': 1768147700,  # January 11, 2026 - Fresh start with security fixes
    'bits': INITIAL_DIFFICULTY,
    'nonce': 0,  # Genesis nonce
    'coinbase_message': b'SALOCOIN v2.0 - Fresh Start January 2026',
    'merkle_root': '',  # Will be calculated
}

# Genesis block hash - Will be updated after first run
GENESIS_HASH = "eb10c14305279ea93196041b4e31a64e9fc9682152debb2e36c869b453b438dc"

# ============================================================================
# CHECKPOINTS - Hardcoded block hashes for security
# ============================================================================

CHECKPOINTS = {
    0: "eb10c14305279ea93196041b4e31a64e9fc9682152debb2e36c869b453b438dc",
    # Add more checkpoints as blockchain grows
}

# ============================================================================
# DNS SEEDS
# ============================================================================

# Note: These are placeholder domains. In production, set up real DNS seeds.
# For local testing, leave empty to avoid DNS lookup delays.
DNS_SEEDS = [
    "api.salocoin.org",
    "seed.salocoin.org",
    "bootstrap.salocoin.org",
]

# Seed nodes (IP:port) - Official nodes for initial sync
# Add your own seed node IPs here for production deployment
SEED_NODES = [
    "api.salocoin.org:7339",    # Official seed node
    "seed.salocoin.org:7339",   # Official seed node
    # "YOUR_IP:7339",           # Add your seed node IP here
]

# Bootstrap node for fast initial sync
BOOTSTRAP_NODES = [
    "https://bootstrap.salocoin.org",
    # "http://YOUR_IP:7340",    # Add your bootstrap node IP here
]

# ============================================================================
# FILE PATHS
# ============================================================================

def get_data_dir(testnet: bool = False) -> str:
    """Get default data directory."""
    if os.name == 'nt':  # Windows
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        data_dir = os.path.join(base, 'Salocoin')
    elif os.name == 'posix':
        if os.uname().sysname == 'Darwin':  # macOS
            data_dir = os.path.expanduser('~/Library/Application Support/Salocoin')
        else:  # Linux
            data_dir = os.path.expanduser('~/.salocoin')
    else:
        data_dir = os.path.expanduser('~/.salocoin')
    
    if testnet:
        data_dir = os.path.join(data_dir, 'testnet')
    
    return data_dir


# Default filenames
WALLET_FILENAME = "wallet.dat"
BLOCKCHAIN_FILENAME = "blocks.dat"
PEERS_FILENAME = "peers.dat"
MEMPOOL_FILENAME = "mempool.dat"
MASTERNODE_FILENAME = "masternodes.dat"
CONFIG_FILENAME = "salocoin.conf"

# ============================================================================
# SPORK KEYS (for network-wide feature activation)
# ============================================================================

# Spork IDs
SPORK_INSTANTSEND_ENABLED = 10001
SPORK_INSTANTSEND_BLOCK_FILTERING = 10002
SPORK_MASTERNODE_PAYMENT_ENFORCEMENT = 10007
SPORK_RECONSIDER_BLOCKS = 10010
SPORK_GOVERNANCE_ENABLED = 10011
SPORK_PRIVATESEND_ENABLED = 10012

# Default spork values
SPORK_DEFAULTS = {
    SPORK_INSTANTSEND_ENABLED: 0,  # Enabled
    SPORK_INSTANTSEND_BLOCK_FILTERING: 0,  # Enabled
    SPORK_MASTERNODE_PAYMENT_ENFORCEMENT: 0,  # Enabled
    SPORK_RECONSIDER_BLOCKS: 0,
    SPORK_GOVERNANCE_ENABLED: 0,  # Enabled
    SPORK_PRIVATESEND_ENABLED: 0,  # Enabled
}

# ============================================================================
# LOGGING
# ============================================================================

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = "salocoin.log"

# ============================================================================
# DEVELOPMENT/DEBUG
# ============================================================================

DEBUG = False
REGTEST = False

# ============================================================================
# VERSION INFO
# ============================================================================

VERSION = "1.0.0"
VERSION_MAJOR = 1
VERSION_MINOR = 0
VERSION_PATCH = 0
VERSION_BUILD = 0

CLIENT_NAME = f"{COIN_NAME} Core"
CLIENT_VERSION = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_data_dir(testnet: bool = False) -> str:
    """Get default data directory."""
    import platform
    
    if platform.system() == 'Windows':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        dir_name = 'SALOCOIN' if not testnet else 'SALOCOIN/testnet'
    elif platform.system() == 'Darwin':
        base = os.path.expanduser('~/Library/Application Support')
        dir_name = 'SALOCOIN' if not testnet else 'SALOCOIN/testnet'
    else:
        base = os.path.expanduser('~')
        dir_name = '.salocoin' if not testnet else '.salocoin/testnet'
    
    return os.path.join(base, dir_name)


def get_config_file(testnet: bool = False) -> str:
    """Get config file path."""
    return os.path.join(get_data_dir(testnet), 'salocoin.conf')


def get_block_reward(height: int) -> int:
    """Get block reward at height (alias for calculate_block_reward)."""
    return calculate_block_reward(height)


# Pool port alias
POOL_PORT = MINING_POOL_PORT

# Testnet port aliases
P2P_TESTNET_PORT = TESTNET_P2P_PORT
RPC_TESTNET_PORT = TESTNET_RPC_PORT
