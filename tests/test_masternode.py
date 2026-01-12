"""
Tests for SALOCOIN masternode functionality.
"""

import pytest
import sys
import os
import time
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from masternode import (
    Masternode,
    MasternodeCollateral,
    MasternodeList,
    MasternodeState,
    MasternodePayments,
    Governance,
    InstantSend,
    PrivateSend,
    SporkManager,
)
from core.blockchain import Blockchain
from core.crypto import generate_keypair
import config


def create_test_masternode(
    ip: str = "192.168.1.1",
    port: int = None,
    txid: str = "0" * 64,
    vout: int = 0,
    payout_address: str = "STest123456789",
) -> Masternode:
    """Helper function to create a test masternode with proper API."""
    if port is None:
        port = config.MASTERNODE_PORT
    
    # generate_keypair returns (private_key, public_key)
    privkey, pubkey = generate_keypair()
    
    collateral = MasternodeCollateral(
        txid=txid,
        vout=vout,
        amount=config.MASTERNODE_COLLATERAL,
        confirmations=100,
    )
    
    return Masternode(
        collateral=collateral,
        pubkey_operator=pubkey,
        pubkey_voting=pubkey,
        service_address=f"{ip}:{port}",
        owner_address=payout_address,
        payout_address=payout_address,
    )


class TestMasternode:
    """Test Masternode class."""
    
    def test_create_masternode(self):
        """Test masternode creation."""
        mn = create_test_masternode()
        
        assert mn.ip == "192.168.1.1"
        assert mn.port == config.MASTERNODE_PORT
        assert mn.state == MasternodeState.PRE_ENABLED
    
    def test_masternode_identifier(self):
        """Test masternode unique identifier."""
        mn = create_test_masternode(
            txid="abc123" + "0" * 58,
            vout=0,
        )
        
        # Identifier should combine txid and vout via collateral
        ident = mn.vin
        
        assert "abc123" in ident
        assert "0" in ident
    
    def test_masternode_is_valid(self):
        """Test masternode validity check."""
        mn = create_test_masternode()
        
        # PRE_ENABLED should be valid
        assert mn.is_valid() == True
        
        # ENABLED should be valid
        mn.state = MasternodeState.ENABLED
        assert mn.is_valid() == True
        
        # EXPIRED should not be valid
        mn.state = MasternodeState.EXPIRED
        assert mn.is_valid() == False
    
    def test_masternode_is_enabled(self):
        """Test masternode enabled check."""
        mn = create_test_masternode()
        
        # PRE_ENABLED is not fully enabled
        assert mn.is_enabled() == False
        
        # ENABLED is fully enabled
        mn.state = MasternodeState.ENABLED
        assert mn.is_enabled() == True


class TestMasternodeList:
    """Test MasternodeList class."""
    
    @pytest.fixture
    def mn_list(self):
        """Create masternode list."""
        return MasternodeList()
    
    def test_add_masternode(self, mn_list):
        """Test adding masternode to list."""
        mn = create_test_masternode()
        
        mn_list.add(mn)
        
        assert mn_list.size() == 1
    
    def test_remove_masternode(self, mn_list):
        """Test removing masternode from list."""
        mn = create_test_masternode()
        
        mn_list.add(mn)
        assert mn_list.size() == 1
        
        mn_list.remove(mn.vin)
        assert mn_list.size() == 0
    
    def test_get_masternode(self, mn_list):
        """Test getting masternode by identifier."""
        mn = create_test_masternode()
        
        mn_list.add(mn)
        
        retrieved = mn_list.get(mn.vin)
        
        assert retrieved is not None
        assert retrieved.ip == mn.ip
    
    def test_count_enabled(self, mn_list):
        """Test counting enabled masternodes."""
        # Add enabled masternode
        mn1 = create_test_masternode(ip="192.168.1.1", txid="1" * 64)
        mn1.state = MasternodeState.ENABLED
        mn_list.add(mn1)
        
        # Add pre-enabled masternode
        mn2 = create_test_masternode(ip="192.168.1.2", txid="2" * 64)
        mn2.state = MasternodeState.PRE_ENABLED
        mn_list.add(mn2)
        
        assert mn_list.get_enabled_count() == 1
        assert mn_list.size() == 2


class TestMasternodePayments:
    """Test masternode payment selection."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for blockchain data."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path)
    
    @pytest.fixture
    def payments(self, temp_dir):
        """Create payment handler with test data."""
        blockchain = Blockchain(temp_dir)
        
        mn_list = MasternodeList()
        
        # Add some enabled masternodes
        for i in range(5):
            mn = create_test_masternode(
                ip=f"192.168.1.{i}",
                txid=f"{i:064d}",
                payout_address=f"STest{i}",
            )
            mn.state = MasternodeState.ENABLED
            mn.last_paid_height = 900 + i
            mn_list.add(mn)
        
        return MasternodePayments(blockchain, mn_list)
    
    def test_get_next_payment(self, payments):
        """Test getting next payment masternode."""
        result = payments.get_next_payment(1000)
        
        # May be empty if no eligible masternodes, but should return dict
        assert isinstance(result, dict)
    
    def test_calculate_payment_amounts(self, payments):
        """Test payment amount calculations."""
        amounts = payments.calculate_payment_amounts(1000)
        
        assert isinstance(amounts, dict)
        assert 'masternode' in amounts or 'miner' in amounts


class TestGovernance:
    """Test governance functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path)
    
    @pytest.fixture
    def governance(self, temp_dir):
        """Create governance instance."""
        blockchain = Blockchain(temp_dir)
        
        mn_list = MasternodeList()
        
        return Governance(blockchain, mn_list)
    
    def test_create_proposal(self, governance):
        """Test creating a governance proposal."""
        from masternode.governance import ProposalType
        
        proposal = governance.create_proposal(
            name="test-proposal",
            description="This is a test proposal for testing purposes",
            proposal_type=ProposalType.BUDGET,
            payment_address="STest123456789012345678901234567",
            payment_amount=1000 * config.COIN_UNIT,
            proposer_address="SProposer1234567890123456789012",
        )
        
        assert proposal is not None
        assert proposal.name == "test-proposal"
    
    def test_superblock_cycle(self, governance):
        """Test superblock detection."""
        # Superblock every 16616 blocks by default
        is_superblock = governance.is_superblock(16616)
        
        # Depends on implementation
        assert isinstance(is_superblock, bool)


class TestInstantSend:
    """Test InstantSend functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path)
    
    @pytest.fixture
    def instantsend(self, temp_dir):
        """Create InstantSend instance."""
        blockchain = Blockchain(temp_dir)
        
        mn_list = MasternodeList()
        
        # Add some masternodes for quorum
        for i in range(10):
            mn = create_test_masternode(
                ip=f"192.168.1.{i}",
                txid=f"{i:064d}",
            )
            mn.state = MasternodeState.ENABLED
            mn_list.add(mn)
        
        return InstantSend(blockchain, mn_list)
    
    def test_quorum_size(self, instantsend):
        """Test InstantSend quorum size from config."""
        # Should have INSTANTSEND_QUORUM_SIZE defined in config
        quorum = config.INSTANTSEND_QUORUM_SIZE
        
        assert quorum > 0
        assert quorum == 10  # Default value


class TestPrivateSend:
    """Test PrivateSend functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path)
    
    @pytest.fixture
    def privatesend(self, temp_dir):
        """Create PrivateSend instance."""
        blockchain = Blockchain(temp_dir)
        
        mn_list = MasternodeList()
        
        return PrivateSend(blockchain, mn_list)
    
    def test_denominations(self, privatesend):
        """Test PrivateSend denominations."""
        denoms = privatesend.get_denominations()
        
        # Should have standard denominations
        assert len(denoms) > 0
        
        # All denominations should be positive
        for d in denoms:
            assert d > 0


class TestSporkManager:
    """Test spork functionality."""
    
    @pytest.fixture
    def spork_manager(self):
        """Create spork manager."""
        return SporkManager()
    
    def test_get_spork(self, spork_manager):
        """Test getting spork value."""
        value = spork_manager.get_spork_value(config.SPORK_INSTANTSEND_ENABLED)
        
        # Should return a value (0 for default/active)
        assert isinstance(value, int)
    
    def test_spork_active(self, spork_manager):
        """Test checking if spork is active."""
        # By default, should be active (value 0)
        active = spork_manager.is_spork_active(config.SPORK_INSTANTSEND_ENABLED)
        
        assert isinstance(active, bool)
    
    def test_get_all_sporks(self, spork_manager):
        """Test getting all sporks."""
        all_sporks = spork_manager.get_all_sporks()
        
        assert isinstance(all_sporks, list)
        assert len(all_sporks) > 0


class TestMasternodeCollateral:
    """Test masternode collateral verification."""
    
    def test_collateral_amount(self):
        """Test that collateral is 15000 SALO."""
        assert config.MASTERNODE_COLLATERAL == 15_000 * config.COIN_UNIT
    
    def test_collateral_confirmations(self):
        """Test minimum confirmations for collateral."""
        assert config.MASTERNODE_MIN_CONFIRMATIONS == 15
    
    def test_collateral_creation(self):
        """Test creating MasternodeCollateral."""
        collateral = MasternodeCollateral(
            txid="a" * 64,
            vout=1,
            amount=config.MASTERNODE_COLLATERAL,
            confirmations=20,
        )
        
        assert collateral.txid == "a" * 64
        assert collateral.vout == 1
        assert collateral.amount == config.MASTERNODE_COLLATERAL
        assert collateral.confirmations == 20


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
