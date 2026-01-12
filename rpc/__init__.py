"""
SALOCOIN RPC Module
JSON-RPC server for wallet and node control.
"""

from .server import RPCServer, RPCError, require_wallet_unlocked
from .client import RPCClient, RPCClientError, RPCResponseError
from .methods import RPCMethods

__all__ = [
    'RPCServer',
    'RPCClient',
    'RPCMethods',
    'RPCError',
    'RPCClientError',
    'RPCResponseError',
    'require_wallet_unlocked',
]
