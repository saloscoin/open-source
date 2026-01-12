"""
SALOCOIN Masternode Module
Complete masternode implementation with governance.
"""

from .masternode import Masternode, MasternodeList, MasternodeManager, MasternodeState, MasternodeCollateral
from .payments import MasternodePayments
from .governance import Governance, Proposal, Vote
from .instantsend import InstantSend
from .privatesend import PrivateSend
from .spork import SporkManager

__all__ = [
    'Masternode',
    'MasternodeCollateral',
    'MasternodeList',
    'MasternodeManager',
    'MasternodeState',
    'MasternodePayments',
    'Governance',
    'Proposal',
    'Vote',
    'InstantSend',
    'PrivateSend',
    'SporkManager',
]
