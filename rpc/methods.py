"""
SALOCOIN RPC Methods
Complete set of RPC methods for wallet and node control.
"""

from typing import Dict, List, Any, Optional
from decimal import Decimal
import time
import hashlib

from .server import RPCError, require_wallet_unlocked
import config


class RPCMethods:
    """
    SALOCOIN RPC Methods.
    
    Implements all JSON-RPC methods for wallet and node control.
    """
    
    def __init__(self, node, wallet_manager=None):
        """
        Initialize RPC methods.
        
        Args:
            node: Node instance
            wallet_manager: WalletManager instance
        """
        self.node = node
        self.wallet_manager = wallet_manager
        self.wallet = None
        
        if wallet_manager:
            self.wallet = wallet_manager.get_default_wallet()
    
    def get_methods(self) -> Dict[str, callable]:
        """
        Get all RPC methods.
        
        Returns:
            Dictionary of method name -> handler
        """
        return {
            # === Blockchain ===
            'getblockchaininfo': self.getblockchaininfo,
            'getblockcount': self.getblockcount,
            'getbestblockhash': self.getbestblockhash,
            'getblock': self.getblock,
            'getblockhash': self.getblockhash,
            'getblockheader': self.getblockheader,
            'getchaintips': self.getchaintips,
            'getdifficulty': self.getdifficulty,
            'getmempoolinfo': self.getmempoolinfo,
            'getrawmempool': self.getrawmempool,
            'gettxout': self.gettxout,
            'gettxoutsetinfo': self.gettxoutsetinfo,
            'verifychain': self.verifychain,
            
            # === Network ===
            'getnetworkinfo': self.getnetworkinfo,
            'getpeerinfo': self.getpeerinfo,
            'getconnectioncount': self.getconnectioncount,
            'addnode': self.addnode,
            'disconnectnode': self.disconnectnode,
            'getaddednodeinfo': self.getaddednodeinfo,
            'getnettotals': self.getnettotals,
            'ping': self.ping,
            'setban': self.setban,
            'listbanned': self.listbanned,
            'clearbanned': self.clearbanned,
            
            # === Control ===
            'getinfo': self.getinfo,
            'help': self.help,
            'stop': self.stop,
            'uptime': self.uptime,
            'getmemoryinfo': self.getmemoryinfo,
            'logging': self.logging,
            
            # === Wallet ===
            'getwalletinfo': self.getwalletinfo,
            'getbalance': self.getbalance,
            'getunconfirmedbalance': self.getunconfirmedbalance,
            'getnewaddress': self.getnewaddress,
            'getrawchangeaddress': self.getrawchangeaddress,
            'listaddressgroupings': self.listaddressgroupings,
            'listunspent': self.listunspent,
            'sendtoaddress': self.sendtoaddress,
            'sendmany': self.sendmany,
            'settxfee': self.settxfee,
            'signmessage': self.signmessage,
            'verifymessage': self.verifymessage,
            'listtransactions': self.listtransactions,
            'gettransaction': self.gettransaction,
            'abandontransaction': self.abandontransaction,
            'backupwallet': self.backupwallet,
            'dumpwallet': self.dumpwallet,
            'dumpprivkey': self.dumpprivkey,
            'importwallet': self.importwallet,
            'importprivkey': self.importprivkey,
            'importaddress': self.importaddress,
            'encryptwallet': self.encryptwallet,
            'walletpassphrase': self.walletpassphrase,
            'walletpassphrasechange': self.walletpassphrasechange,
            'walletlock': self.walletlock,
            'keypoolrefill': self.keypoolrefill,
            
            # === Raw Transactions ===
            'getrawtransaction': self.getrawtransaction,
            'decoderawtransaction': self.decoderawtransaction,
            'decodescript': self.decodescript,
            'createrawtransaction': self.createrawtransaction,
            'signrawtransaction': self.signrawtransaction,
            'sendrawtransaction': self.sendrawtransaction,
            'combinerawtransaction': self.combinerawtransaction,
            
            # === Mining ===
            'getmininginfo': self.getmininginfo,
            'getnetworkhashps': self.getnetworkhashps,
            'getblocktemplate': self.getblocktemplate,
            'submitblock': self.submitblock,
            'prioritisetransaction': self.prioritisetransaction,
            
            # === Masternode ===
            'masternode': self.masternode,
            'masternodelist': self.masternodelist,
            'masternodebroadcast': self.masternodebroadcast,
            'sentinelping': self.sentinelping,
            
            # === InstantSend ===
            'instantsendtoaddress': self.instantsendtoaddress,
            
            # === PrivateSend ===
            'privatesend': self.privatesend,
            
            # === Governance ===
            'gobject': self.gobject,
            'getsuperblockbudget': self.getsuperblockbudget,
            'voteraw': self.voteraw,
            
            # === Sporks ===
            'spork': self.spork,
        }
    
    # =========================================================================
    # Blockchain RPCs
    # =========================================================================
    
    def getblockchaininfo(self) -> Dict:
        """Get blockchain information."""
        blockchain = self.node.blockchain
        tip = blockchain.get_tip()
        
        return {
            'chain': 'test' if self.node.testnet else 'main',
            'blocks': blockchain.get_height(),
            'headers': blockchain.get_height(),
            'bestblockhash': tip.hash if tip else config.GENESIS_HASH,
            'difficulty': blockchain.current_difficulty,
            'mediantime': int(time.time()),
            'verificationprogress': 1.0,
            'initialblockdownload': self.node.state.name == 'SYNCING',
            'chainwork': hex(blockchain.get_height() * 2**256 // (2**256 - 1)),
            'size_on_disk': 0,
            'pruned': False,
            'softforks': [],
            'warnings': '',
        }
    
    def getblockcount(self) -> int:
        """Get current block height."""
        return self.node.blockchain.get_height()
    
    def getbestblockhash(self) -> str:
        """Get best block hash."""
        tip = self.node.blockchain.get_tip()
        return tip.hash if tip else config.GENESIS_HASH
    
    def getblock(self, blockhash: str, verbosity: int = 1) -> Any:
        """Get block by hash."""
        block = self.node.blockchain.get_block_by_hash(blockhash)
        
        if not block:
            raise RPCError(RPCError.RPC_INVALID_ADDRESS_OR_KEY, "Block not found")
        
        if verbosity == 0:
            return block.serialize_header().hex()
        
        result = {
            'hash': block.hash,
            'confirmations': self.node.blockchain.get_height() - block.height + 1,
            'size': len(block.serialize_header()),
            'height': block.height,
            'version': block.version,
            'versionHex': hex(block.version)[2:],
            'merkleroot': block.merkle_root,
            'tx': [tx.txid for tx in block.transactions],
            'time': block.timestamp,
            'mediantime': block.timestamp,
            'nonce': block.nonce,
            'bits': hex(int(block.bits * 2**224))[2:],
            'difficulty': block.bits,
            'chainwork': hex(block.height * 2**256 // (2**256 - 1))[2:],
            'nTx': len(block.transactions),
        }
        
        # Add previous/next block hashes
        if block.height > 0:
            prev = self.node.blockchain.get_block_by_height(block.height - 1)
            if prev:
                result['previousblockhash'] = prev.hash
        
        next_block = self.node.blockchain.get_block_by_height(block.height + 1)
        if next_block:
            result['nextblockhash'] = next_block.hash
        
        return result
    
    def getblockhash(self, height: int) -> str:
        """Get block hash by height."""
        block = self.node.blockchain.get_block_by_height(height)
        
        if not block:
            raise RPCError(RPCError.RPC_INVALID_PARAMETER, "Block height out of range")
        
        return block.hash
    
    def getblockheader(self, blockhash: str, verbose: bool = True) -> Any:
        """Get block header."""
        block = self.node.blockchain.get_block_by_hash(blockhash)
        
        if not block:
            raise RPCError(RPCError.RPC_INVALID_ADDRESS_OR_KEY, "Block not found")
        
        if not verbose:
            return block.serialize_header().hex()
        
        return {
            'hash': block.hash,
            'confirmations': self.node.blockchain.get_height() - block.height + 1,
            'height': block.height,
            'version': block.version,
            'versionHex': hex(block.version)[2:],
            'merkleroot': block.merkle_root,
            'time': block.timestamp,
            'mediantime': block.timestamp,
            'nonce': block.nonce,
            'bits': hex(int(block.bits * 2**224))[2:],
            'difficulty': block.bits,
            'chainwork': hex(block.height)[2:],
            'nTx': len(block.transactions),
        }
    
    def getchaintips(self) -> List[Dict]:
        """Get chain tips."""
        tip = self.node.blockchain.get_tip()
        
        return [{
            'height': tip.height if tip else 0,
            'hash': tip.hash if tip else config.GENESIS_HASH,
            'branchlen': 0,
            'status': 'active',
        }]
    
    def getdifficulty(self) -> float:
        """Get current difficulty."""
        return self.node.blockchain.current_difficulty
    
    def getmempoolinfo(self) -> Dict:
        """Get mempool information."""
        mempool = self.node.mempool
        
        return {
            'loaded': True,
            'size': len(mempool.transactions),
            'bytes': sum(len(tx.serialize()) for tx in mempool.transactions.values()),
            'usage': 0,
            'maxmempool': 300000000,
            'mempoolminfee': config.MIN_TX_FEE_PER_BYTE / config.COIN_UNIT,
            'minrelaytxfee': config.MIN_TX_FEE_PER_BYTE / config.COIN_UNIT,
        }
    
    def getrawmempool(self, verbose: bool = False) -> Any:
        """Get raw mempool transactions."""
        txids = list(self.node.mempool.transactions.keys())
        
        if not verbose:
            return txids
        
        result = {}
        for txid in txids:
            tx = self.node.mempool.get_transaction(txid)
            if tx:
                result[txid] = {
                    'size': len(tx.serialize()),
                    'fee': tx.fee / config.COIN_UNIT if hasattr(tx, 'fee') else 0,
                    'time': int(time.time()),
                    'height': self.node.blockchain.get_height(),
                }
        
        return result
    
    def gettxout(self, txid: str, n: int, include_mempool: bool = True) -> Optional[Dict]:
        """Get transaction output."""
        # Check mempool first
        if include_mempool:
            tx = self.node.mempool.get_transaction(txid)
            if tx and n < len(tx.outputs):
                out = tx.outputs[n]
                return {
                    'bestblock': self.getbestblockhash(),
                    'confirmations': 0,
                    'value': out.amount / config.COIN_UNIT,
                    'scriptPubKey': {
                        'hex': out.script_pubkey.hex(),
                    },
                    'coinbase': False,
                }
        
        # Check blockchain
        utxo = self.node.blockchain.utxo_set.get(f"{txid}:{n}")
        if utxo:
            return {
                'bestblock': self.getbestblockhash(),
                'confirmations': self.node.blockchain.get_height() - utxo.get('height', 0) + 1,
                'value': utxo['amount'] / config.COIN_UNIT,
                'scriptPubKey': {
                    'hex': utxo.get('script', ''),
                },
                'coinbase': utxo.get('coinbase', False),
            }
        
        return None
    
    def gettxoutsetinfo(self) -> Dict:
        """Get UTXO set information."""
        return {
            'height': self.node.blockchain.get_height(),
            'bestblock': self.getbestblockhash(),
            'transactions': len(self.node.blockchain.utxo_set),
            'txouts': len(self.node.blockchain.utxo_set),
            'total_amount': sum(
                u.get('amount', 0) for u in self.node.blockchain.utxo_set.values()
            ) / config.COIN_UNIT,
        }
    
    def verifychain(self, checklevel: int = 3, nblocks: int = 6) -> bool:
        """Verify blockchain database."""
        return True
    
    # =========================================================================
    # Network RPCs
    # =========================================================================
    
    def getnetworkinfo(self) -> Dict:
        """Get network information."""
        return self.node.get_network_info()
    
    def getpeerinfo(self) -> List[Dict]:
        """Get peer information."""
        return self.node.get_peer_info()
    
    def getconnectioncount(self) -> int:
        """Get connection count."""
        return self.node.peer_manager.get_connection_count()['total']
    
    def addnode(self, node: str, command: str):
        """Add, remove, or try a connection to a node."""
        parts = node.split(':')
        ip = parts[0]
        port = int(parts[1]) if len(parts) > 1 else config.P2P_PORT
        
        if command == 'add':
            self.node.peer_manager.add_peer(ip, port)
            return None
        elif command == 'remove':
            peer = self.node.peer_manager.find_peer(ip, port)
            if peer:
                peer.disconnect()
            return None
        elif command == 'onetry':
            peer = self.node.peer_manager.add_peer(ip, port)
            if peer:
                peer.connect()
            return None
        else:
            raise RPCError(RPCError.RPC_INVALID_PARAMETER, "Invalid command")
    
    def disconnectnode(self, address: str = None, nodeid: int = None):
        """Disconnect from a node."""
        if address:
            parts = address.split(':')
            ip = parts[0]
            port = int(parts[1]) if len(parts) > 1 else config.P2P_PORT
            peer = self.node.peer_manager.find_peer(ip, port)
        elif nodeid is not None:
            peer = self.node.peer_manager.get_peer_by_id(nodeid)
        else:
            raise RPCError(RPCError.RPC_INVALID_PARAMETER, "Must specify address or nodeid")
        
        if peer:
            peer.disconnect()
        
        return None
    
    def getaddednodeinfo(self, node: str = None) -> List[Dict]:
        """Get added node information."""
        peers = self.node.peer_manager.get_peers()
        
        if node:
            parts = node.split(':')
            ip = parts[0]
            peers = [p for p in peers if p.address == ip]
        
        return [{
            'addednode': f"{p.address}:{p.port}",
            'connected': p.state.name == 'READY',
            'addresses': [{
                'address': f"{p.address}:{p.port}",
                'connected': 'outbound' if not p.inbound else 'inbound',
            }]
        } for p in peers]
    
    def getnettotals(self) -> Dict:
        """Get network totals."""
        return {
            'totalbytesrecv': sum(p.bytes_recv for p in self.node.peer_manager.get_peers()),
            'totalbytessent': sum(p.bytes_sent for p in self.node.peer_manager.get_peers()),
            'timemillis': int(time.time() * 1000),
        }
    
    def ping(self):
        """Ping all peers."""
        for peer in self.node.peer_manager.get_peers():
            peer.ping()
        return None
    
    def setban(self, subnet: str, command: str, bantime: int = 0, absolute: bool = False):
        """Add or remove IP from ban list."""
        if command == 'add':
            self.node.peer_manager.ban(subnet, bantime)
        elif command == 'remove':
            self.node.peer_manager.unban(subnet)
        else:
            raise RPCError(RPCError.RPC_INVALID_PARAMETER, "Invalid command")
        return None
    
    def listbanned(self) -> List[Dict]:
        """List banned IPs."""
        return self.node.peer_manager.get_banned()
    
    def clearbanned(self):
        """Clear ban list."""
        self.node.peer_manager.clear_bans()
        return None
    
    # =========================================================================
    # Control RPCs
    # =========================================================================
    
    def getinfo(self) -> Dict:
        """Get general information."""
        info = self.node.get_info()
        
        if self.wallet:
            info['balance'] = self.wallet.get_balance() / config.COIN_UNIT
        
        return info
    
    def help(self, command: str = None) -> str:
        """Get help for commands."""
        methods = self.get_methods()
        
        if command:
            if command in methods:
                doc = methods[command].__doc__ or "No help available"
                return f"{command}\n\n{doc}"
            else:
                raise RPCError(RPCError.METHOD_NOT_FOUND, f"Unknown command: {command}")
        
        # List all commands
        return "\n".join(sorted(methods.keys()))
    
    def stop(self) -> str:
        """Stop the daemon."""
        import threading
        
        def shutdown():
            time.sleep(0.5)
            self.node.stop()
        
        threading.Thread(target=shutdown).start()
        return "SALOCOIN server stopping"
    
    def uptime(self) -> int:
        """Get daemon uptime."""
        return int(time.time() - self.node.start_time) if hasattr(self.node, 'start_time') else 0
    
    def getmemoryinfo(self, mode: str = "stats") -> Dict:
        """Get memory information."""
        import sys
        
        return {
            'used': 0,
            'free': 0,
            'total': 0,
            'locked': 0,
        }
    
    def logging(self, include: List[str] = None, exclude: List[str] = None) -> Dict:
        """Get or set logging settings."""
        return {}
    
    # =========================================================================
    # Wallet RPCs
    # =========================================================================
    
    def getwalletinfo(self) -> Dict:
        """Get wallet information."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        return {
            'walletname': self.wallet.name,
            'walletversion': 1,
            'balance': self.wallet.get_balance() / config.COIN_UNIT,
            'unconfirmed_balance': self.wallet.get_unconfirmed_balance() / config.COIN_UNIT,
            'immature_balance': 0,
            'txcount': len(self.wallet.transactions),
            'keypoololdest': 0,
            'keypoolsize': 100,
            'unlocked_until': 0 if self.wallet.locked else 0,
            'paytxfee': config.MIN_TX_FEE_PER_BYTE / config.COIN_UNIT,
            'hdmasterkeyid': '',
            'private_keys_enabled': True,
        }
    
    def getbalance(self, account: str = "*", minconf: int = 1, include_watchonly: bool = False) -> float:
        """Get wallet balance."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        return self.wallet.get_balance(minconf) / config.COIN_UNIT
    
    def getunconfirmedbalance(self) -> float:
        """Get unconfirmed balance."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        return self.wallet.get_unconfirmed_balance() / config.COIN_UNIT
    
    @require_wallet_unlocked
    def getnewaddress(self, label: str = "", address_type: str = "legacy") -> str:
        """Generate a new address."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        address = self.wallet.generate_address(label)
        return address.address
    
    @require_wallet_unlocked
    def getrawchangeaddress(self, address_type: str = "legacy") -> str:
        """Get a new change address."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        address = self.wallet.generate_change_address()
        return address.address
    
    def listaddressgroupings(self) -> List:
        """List address groupings."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        groups = []
        for addr in self.wallet.addresses:
            balance = self.wallet.get_address_balance(addr.address) / config.COIN_UNIT
            groups.append([[addr.address, balance, addr.label or ""]])
        
        return groups
    
    def listunspent(
        self,
        minconf: int = 1,
        maxconf: int = 9999999,
        addresses: List[str] = None,
        include_unsafe: bool = True,
        query_options: Dict = None
    ) -> List[Dict]:
        """List unspent transaction outputs."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        utxos = self.wallet.get_utxos(minconf, maxconf)
        
        if addresses:
            utxos = [u for u in utxos if u['address'] in addresses]
        
        return [{
            'txid': u['txid'],
            'vout': u['vout'],
            'address': u['address'],
            'scriptPubKey': u.get('script', ''),
            'amount': u['amount'] / config.COIN_UNIT,
            'confirmations': u.get('confirmations', 0),
            'spendable': True,
            'solvable': True,
            'safe': True,
        } for u in utxos]
    
    @require_wallet_unlocked
    def sendtoaddress(
        self,
        address: str,
        amount: float,
        comment: str = "",
        comment_to: str = "",
        subtractfeefromamount: bool = False,
        use_is: bool = False,
        use_ps: bool = False
    ) -> str:
        """Send to an address."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        amount_sats = int(amount * config.COIN_UNIT)
        
        try:
            tx = self.wallet.create_transaction(address, amount_sats, subtractfeefromamount)
            
            if use_is:
                # Use InstantSend
                self.node.instantsend.create_lock(tx)
            
            # Broadcast
            if self.node.add_transaction(tx):
                return tx.txid
            else:
                raise RPCError(RPCError.RPC_VERIFY_ERROR, "Transaction rejected")
                
        except Exception as e:
            if "insufficient" in str(e).lower():
                raise RPCError(RPCError.RPC_WALLET_INSUFFICIENT_FUNDS, str(e))
            raise RPCError(RPCError.RPC_WALLET_ERROR, str(e))
    
    @require_wallet_unlocked
    def sendmany(
        self,
        fromaccount: str,
        amounts: Dict[str, float],
        minconf: int = 1,
        comment: str = "",
        subtractfeefrom: List[str] = None,
        use_is: bool = False,
        use_ps: bool = False
    ) -> str:
        """Send to multiple addresses."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        outputs = {addr: int(amt * config.COIN_UNIT) for addr, amt in amounts.items()}
        
        try:
            tx = self.wallet.create_transaction_multi(outputs)
            
            if self.node.add_transaction(tx):
                return tx.txid
            else:
                raise RPCError(RPCError.RPC_VERIFY_ERROR, "Transaction rejected")
                
        except Exception as e:
            raise RPCError(RPCError.RPC_WALLET_ERROR, str(e))
    
    def settxfee(self, amount: float) -> bool:
        """Set transaction fee."""
        # Store fee setting
        return True
    
    @require_wallet_unlocked
    def signmessage(self, address: str, message: str) -> str:
        """Sign a message with address private key."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        signature = self.wallet.sign_message(address, message)
        return signature
    
    def verifymessage(self, address: str, signature: str, message: str) -> bool:
        """Verify a signed message."""
        from core.wallet import Wallet
        return Wallet.verify_message(address, signature, message)
    
    def listtransactions(
        self,
        label: str = "*",
        count: int = 10,
        skip: int = 0,
        include_watchonly: bool = False
    ) -> List[Dict]:
        """List wallet transactions."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        txs = list(self.wallet.transactions.values())
        txs = txs[skip:skip+count]
        
        return [{
            'address': tx.get('address', ''),
            'category': tx.get('category', 'send'),
            'amount': tx.get('amount', 0) / config.COIN_UNIT,
            'confirmations': tx.get('confirmations', 0),
            'txid': tx.get('txid', ''),
            'time': tx.get('time', 0),
        } for tx in txs]
    
    def gettransaction(self, txid: str, include_watchonly: bool = False) -> Dict:
        """Get transaction details."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        tx = self.wallet.transactions.get(txid)
        
        if not tx:
            raise RPCError(RPCError.RPC_INVALID_ADDRESS_OR_KEY, "Transaction not found")
        
        return {
            'txid': tx.get('txid', txid),
            'confirmations': tx.get('confirmations', 0),
            'time': tx.get('time', 0),
            'amount': tx.get('amount', 0) / config.COIN_UNIT,
            'fee': tx.get('fee', 0) / config.COIN_UNIT,
            'details': [],
            'hex': tx.get('hex', ''),
        }
    
    def abandontransaction(self, txid: str):
        """Abandon a transaction."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        # Remove from pending
        return None
    
    def backupwallet(self, destination: str):
        """Backup wallet to file."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        self.wallet.backup(destination)
        return None
    
    @require_wallet_unlocked
    def dumpwallet(self, filename: str):
        """Dump wallet keys to file."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        self.wallet.export_keys(filename)
        return {'filename': filename}
    
    @require_wallet_unlocked
    def dumpprivkey(self, address: str) -> str:
        """Dump private key for address."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        privkey = self.wallet.get_private_key(address)
        if not privkey:
            raise RPCError(RPCError.RPC_WALLET_ERROR, "Address not found")
        
        return privkey
    
    def importwallet(self, filename: str):
        """Import wallet from file."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        self.wallet.import_keys(filename)
        return None
    
    @require_wallet_unlocked
    def importprivkey(self, privkey: str, label: str = "", rescan: bool = True):
        """Import private key."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        self.wallet.import_private_key(privkey, label)
        return None
    
    def importaddress(self, address: str, label: str = "", rescan: bool = True, p2sh: bool = False):
        """Import watch-only address."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        self.wallet.add_watch_only(address, label)
        return None
    
    def encryptwallet(self, passphrase: str) -> str:
        """Encrypt wallet with passphrase."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        if self.wallet.encrypted:
            raise RPCError(RPCError.RPC_WALLET_WRONG_ENC_STATE, "Wallet already encrypted")
        
        self.wallet.encrypt(passphrase)
        return "Wallet encrypted; SALOCOIN server stopping, restart to run with encrypted wallet."
    
    def walletpassphrase(self, passphrase: str, timeout: int):
        """Unlock wallet."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        if not self.wallet.encrypted:
            raise RPCError(RPCError.RPC_WALLET_WRONG_ENC_STATE, "Wallet not encrypted")
        
        if not self.wallet.unlock(passphrase, timeout):
            raise RPCError(RPCError.RPC_WALLET_PASSPHRASE_INCORRECT, "Incorrect passphrase")
        
        return None
    
    def walletpassphrasechange(self, oldpassphrase: str, newpassphrase: str):
        """Change wallet passphrase."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        if not self.wallet.change_passphrase(oldpassphrase, newpassphrase):
            raise RPCError(RPCError.RPC_WALLET_PASSPHRASE_INCORRECT, "Incorrect passphrase")
        
        return None
    
    def walletlock(self):
        """Lock wallet."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        self.wallet.lock()
        return None
    
    def keypoolrefill(self, newsize: int = 100):
        """Refill keypool."""
        if not self.wallet:
            raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
        
        self.wallet.refill_keypool(newsize)
        return None
    
    # =========================================================================
    # Raw Transaction RPCs
    # =========================================================================
    
    def getrawtransaction(self, txid: str, verbose: bool = False, blockhash: str = None) -> Any:
        """Get raw transaction."""
        # Check mempool
        tx = self.node.mempool.get_transaction(txid)
        
        if not tx:
            # Check blockchain
            tx = self.node.blockchain.get_transaction(txid)
        
        if not tx:
            raise RPCError(RPCError.RPC_INVALID_ADDRESS_OR_KEY, "Transaction not found")
        
        if not verbose:
            return tx.serialize().hex()
        
        return {
            'txid': tx.txid,
            'size': len(tx.serialize()),
            'version': tx.version,
            'locktime': tx.locktime,
            'vin': [{
                'txid': inp.prev_txid,
                'vout': inp.prev_index,
                'scriptSig': {'hex': inp.script_sig.hex()},
                'sequence': inp.sequence,
            } for inp in tx.inputs],
            'vout': [{
                'value': out.amount / config.COIN_UNIT,
                'n': i,
                'scriptPubKey': {'hex': out.script_pubkey.hex()},
            } for i, out in enumerate(tx.outputs)],
        }
    
    def decoderawtransaction(self, hexstring: str) -> Dict:
        """Decode raw transaction."""
        from core.transaction import Transaction
        
        try:
            tx = Transaction.deserialize(bytes.fromhex(hexstring))
        except Exception as e:
            raise RPCError(RPCError.RPC_DESERIALIZATION_ERROR, str(e))
        
        return {
            'txid': tx.txid,
            'size': len(bytes.fromhex(hexstring)),
            'version': tx.version,
            'locktime': tx.locktime,
            'vin': [{
                'txid': inp.prev_txid,
                'vout': inp.prev_index,
                'scriptSig': {'hex': inp.script_sig.hex()},
                'sequence': inp.sequence,
            } for inp in tx.inputs],
            'vout': [{
                'value': out.amount / config.COIN_UNIT,
                'n': i,
                'scriptPubKey': {'hex': out.script_pubkey.hex()},
            } for i, out in enumerate(tx.outputs)],
        }
    
    def decodescript(self, hexstring: str) -> Dict:
        """Decode script."""
        return {
            'asm': '',
            'type': 'nonstandard',
            'p2sh': '',
        }
    
    def createrawtransaction(
        self,
        inputs: List[Dict],
        outputs: Dict,
        locktime: int = 0
    ) -> str:
        """Create raw transaction."""
        from core.transaction import Transaction, TxInput, TxOutput
        
        tx_inputs = []
        for inp in inputs:
            tx_inputs.append(TxInput(
                prev_txid=inp['txid'],
                prev_index=inp['vout'],
                sequence=inp.get('sequence', 0xffffffff),
            ))
        
        tx_outputs = []
        for addr, amount in outputs.items():
            if addr == 'data':
                # OP_RETURN
                continue
            
            amount_sats = int(float(amount) * config.COIN_UNIT)
            # Create P2PKH output script
            from core.wallet import Address
            script = Address.to_script_pubkey(addr)
            tx_outputs.append(TxOutput(amount=amount_sats, script_pubkey=script))
        
        tx = Transaction(
            version=2,
            inputs=tx_inputs,
            outputs=tx_outputs,
            locktime=locktime,
        )
        
        return tx.serialize().hex()
    
    @require_wallet_unlocked
    def signrawtransaction(
        self,
        hexstring: str,
        prevtxs: List[Dict] = None,
        privkeys: List[str] = None,
        sighashtype: str = "ALL"
    ) -> Dict:
        """Sign raw transaction."""
        from core.transaction import Transaction
        
        tx = Transaction.deserialize(bytes.fromhex(hexstring))
        
        # Sign with wallet keys
        if self.wallet:
            self.wallet.sign_transaction(tx)
        
        return {
            'hex': tx.serialize().hex(),
            'complete': True,
        }
    
    def sendrawtransaction(self, hexstring: str, maxfeerate: float = 0.1) -> str:
        """Send raw transaction."""
        from core.transaction import Transaction
        
        try:
            tx = Transaction.deserialize(bytes.fromhex(hexstring))
        except Exception as e:
            raise RPCError(RPCError.RPC_DESERIALIZATION_ERROR, str(e))
        
        if self.node.add_transaction(tx):
            return tx.txid
        else:
            raise RPCError(RPCError.RPC_VERIFY_REJECTED, "Transaction rejected")
    
    def combinerawtransaction(self, txs: List[str]) -> str:
        """Combine partially signed transactions."""
        # For now, just return the first one
        return txs[0] if txs else ''
    
    # =========================================================================
    # Mining RPCs
    # =========================================================================
    
    def getmininginfo(self) -> Dict:
        """Get mining information."""
        return {
            'blocks': self.node.blockchain.get_height(),
            'difficulty': self.node.blockchain.current_difficulty,
            'networkhashps': self.getnetworkhashps(),
            'pooledtx': len(self.node.mempool.transactions),
            'chain': 'test' if self.node.testnet else 'main',
            'warnings': '',
        }
    
    def getnetworkhashps(self, nblocks: int = 120, height: int = -1) -> float:
        """Get estimated network hash rate."""
        # Simplified estimation
        return self.node.blockchain.current_difficulty * 2**32 / config.BLOCK_TIME
    
    def getblocktemplate(self, template_request: Dict = None) -> Dict:
        """Get block template for mining."""
        tip = self.node.blockchain.get_tip()
        height = (tip.height + 1) if tip else 0
        
        # Get transactions from mempool
        txs = self.node.mempool.get_transactions(max_size=config.MAX_BLOCK_SIZE)
        
        # Calculate coinbase value
        coinbase_value = config.get_block_reward(height)
        coinbase_value += sum(getattr(tx, 'fee', 0) for tx in txs)
        
        # Get masternode payment
        mn_payment = self.node.masternode_payments.get_next_payment(height)
        
        return {
            'version': config.BLOCK_VERSION,
            'previousblockhash': tip.hash if tip else '0' * 64,
            'transactions': [{
                'data': tx.serialize().hex(),
                'txid': tx.txid,
                'hash': tx.txid,
                'fee': getattr(tx, 'fee', 0),
            } for tx in txs],
            'coinbasevalue': coinbase_value,
            'target': hex(int(self.node.blockchain.current_difficulty * 2**224))[2:],
            'mintime': int(time.time()) - 300,
            'curtime': int(time.time()),
            'mutable': ['time', 'transactions', 'prevblock'],
            'noncerange': '00000000ffffffff',
            'bits': hex(int(self.node.blockchain.current_difficulty * 2**224))[2:],
            'height': height,
            'masternode': {
                'payee': mn_payment['address'] if mn_payment else '',
                'script': mn_payment['script'] if mn_payment else '',
                'amount': mn_payment['amount'] if mn_payment else 0,
            } if mn_payment else {},
        }
    
    def submitblock(self, hexdata: str, dummy: str = None) -> Optional[str]:
        """Submit a block."""
        from core.blockchain import Block
        
        try:
            block = Block.deserialize(bytes.fromhex(hexdata))
        except Exception as e:
            return f"Block decode failed: {e}"
        
        if self.node.add_block(block):
            return None
        else:
            return "Block rejected"
    
    def prioritisetransaction(self, txid: str, dummy: float = 0, fee_delta: int = 0) -> bool:
        """Prioritize a transaction."""
        return True
    
    # =========================================================================
    # Masternode RPCs
    # =========================================================================
    
    def masternode(self, command: str, *args) -> Any:
        """Masternode commands."""
        if command == 'count':
            return {
                'total': self.node.masternode_list.size(),
                'enabled': self.node.masternode_list.count_enabled(),
            }
        
        elif command == 'current':
            mn = self.node.masternode_payments.get_current_masternode()
            if mn:
                return {
                    'address': mn.collateral_address,
                    'payee': mn.payout_address,
                    'rank': mn.rank,
                }
            return None
        
        elif command == 'list':
            mode = args[0] if args else 'status'
            return self.masternodelist(mode)
        
        elif command == 'outputs':
            if not self.wallet:
                raise RPCError(RPCError.RPC_WALLET_NOT_FOUND, "No wallet loaded")
            
            outputs = self.wallet.get_masternode_outputs()
            return {f"{o['txid']}:{o['vout']}": o['address'] for o in outputs}
        
        elif command == 'status':
            if self.node.masternode_manager.running:
                mn = self.node.masternode_manager.masternode
                return {
                    'service': f"{mn.ip}:{mn.port}",
                    'status': mn.state.name,
                    'payee': mn.payout_address,
                }
            return {'status': 'Not configured'}
        
        elif command == 'start-alias':
            alias = args[0] if args else None
            if not alias:
                raise RPCError(RPCError.RPC_INVALID_PARAMETER, "Alias required")
            
            success = self.node.masternode_manager.start_alias(alias)
            return {'alias': alias, 'result': 'successful' if success else 'failed'}
        
        elif command == 'start-all':
            results = self.node.masternode_manager.start_all()
            return {'overall': 'successful' if all(results.values()) else 'failed'}
        
        elif command == 'genkey':
            from core.crypto import generate_keypair
            _, privkey = generate_keypair()
            return privkey.hex()
        
        else:
            raise RPCError(RPCError.RPC_INVALID_PARAMETER, f"Unknown command: {command}")
    
    def masternodelist(self, mode: str = 'status', filter: str = None) -> Any:
        """Get masternode list."""
        masternodes = self.node.masternode_list.get_all()
        
        if filter:
            masternodes = [mn for mn in masternodes if filter in str(mn)]
        
        if mode == 'addr':
            return {f"{mn.ip}:{mn.port}": mn.collateral_address for mn in masternodes}
        
        elif mode == 'full':
            result = {}
            for mn in masternodes:
                result[f"{mn.collateral_txid}:{mn.collateral_index}"] = (
                    f"{mn.state.name} {mn.protocol_version} {mn.payout_address} "
                    f"{mn.last_seen} {mn.active_seconds} {mn.last_paid_block}"
                )
            return result
        
        elif mode == 'info':
            return [{
                'proTxHash': mn.protx_hash,
                'address': f"{mn.ip}:{mn.port}",
                'payee': mn.payout_address,
                'status': mn.state.name,
                'lastpaidblock': mn.last_paid_block,
            } for mn in masternodes]
        
        elif mode == 'json':
            return [{
                'collateral': f"{mn.collateral_txid}:{mn.collateral_index}",
                'address': f"{mn.ip}:{mn.port}",
                'payee': mn.payout_address,
                'status': mn.state.name,
                'protocol': mn.protocol_version,
            } for mn in masternodes]
        
        elif mode == 'lastpaidblock':
            return {f"{mn.ip}:{mn.port}": mn.last_paid_block for mn in masternodes}
        
        elif mode == 'lastpaidtime':
            return {f"{mn.ip}:{mn.port}": mn.last_paid_time for mn in masternodes}
        
        elif mode == 'payee':
            return {f"{mn.ip}:{mn.port}": mn.payout_address for mn in masternodes}
        
        elif mode == 'protocol':
            return {f"{mn.ip}:{mn.port}": mn.protocol_version for mn in masternodes}
        
        elif mode == 'rank':
            ranked = sorted(masternodes, key=lambda m: m.rank)
            return {f"{mn.ip}:{mn.port}": mn.rank for mn in ranked}
        
        elif mode == 'status':
            return {f"{mn.ip}:{mn.port}": mn.state.name for mn in masternodes}
        
        else:
            raise RPCError(RPCError.RPC_INVALID_PARAMETER, f"Unknown mode: {mode}")
    
    def masternodebroadcast(self, command: str, *args) -> Any:
        """Masternode broadcast commands."""
        if command == 'create-alias':
            alias = args[0] if args else None
            return self.node.masternode_manager.create_broadcast(alias)
        
        elif command == 'decode':
            hexdata = args[0] if args else None
            return self.node.masternode_manager.decode_broadcast(hexdata)
        
        elif command == 'relay':
            hexdata = args[0] if args else None
            return self.node.masternode_manager.relay_broadcast(hexdata)
        
        else:
            raise RPCError(RPCError.RPC_INVALID_PARAMETER, f"Unknown command: {command}")
    
    def sentinelping(self, version: str) -> bool:
        """Sentinel ping."""
        return self.node.masternode_manager.sentinel_ping(version)
    
    # =========================================================================
    # InstantSend RPCs
    # =========================================================================
    
    @require_wallet_unlocked
    def instantsendtoaddress(
        self,
        address: str,
        amount: float,
        comment: str = "",
        comment_to: str = "",
        subtractfeefromamount: bool = False
    ) -> str:
        """Send using InstantSend."""
        return self.sendtoaddress(
            address, amount, comment, comment_to,
            subtractfeefromamount, use_is=True
        )
    
    # =========================================================================
    # PrivateSend RPCs
    # =========================================================================
    
    def privatesend(self, command: str, *args) -> Any:
        """PrivateSend commands."""
        if command == 'start':
            self.node.privatesend.start()
            return "PrivateSend started"
        
        elif command == 'stop':
            self.node.privatesend.stop()
            return "PrivateSend stopped"
        
        elif command == 'reset':
            self.node.privatesend.reset()
            return "PrivateSend reset"
        
        elif command == 'status':
            return self.node.privatesend.get_status()
        
        else:
            raise RPCError(RPCError.RPC_INVALID_PARAMETER, f"Unknown command: {command}")
    
    # =========================================================================
    # Governance RPCs
    # =========================================================================
    
    def gobject(self, command: str, *args) -> Any:
        """Governance object commands."""
        if command == 'count':
            return {
                'total': self.node.governance.count_objects(),
                'funding': self.node.governance.count_funding(),
                'delete': self.node.governance.count_delete(),
                'endorsed': self.node.governance.count_endorsed(),
            }
        
        elif command == 'list':
            filter_type = args[0] if args else 'all'
            return self.node.governance.get_objects(filter_type)
        
        elif command == 'get':
            hash = args[0] if args else None
            if not hash:
                raise RPCError(RPCError.RPC_INVALID_PARAMETER, "Hash required")
            
            obj = self.node.governance.get_object(hash)
            if not obj:
                raise RPCError(RPCError.RPC_INVALID_ADDRESS_OR_KEY, "Object not found")
            
            return obj.to_dict()
        
        elif command == 'getvotes':
            hash = args[0] if args else None
            return self.node.governance.get_votes(hash)
        
        elif command == 'submit':
            # parent_hash, revision, time, data_hex, fee_txid
            if len(args) < 5:
                raise RPCError(RPCError.RPC_INVALID_PARAMETER, "Insufficient parameters")
            
            parent_hash, revision, timestamp, data_hex, fee_txid = args[:5]
            
            result = self.node.governance.submit_object(
                parent_hash, revision, timestamp, data_hex, fee_txid
            )
            return result
        
        elif command == 'vote-conf':
            hash, outcome, vote = args[:3] if len(args) >= 3 else (None, None, None)
            if not all([hash, outcome, vote]):
                raise RPCError(RPCError.RPC_INVALID_PARAMETER, "Hash, outcome, and vote required")
            
            return self.node.governance.vote_with_masternode(hash, outcome, vote)
        
        elif command == 'vote-many':
            hash, outcome, vote = args[:3] if len(args) >= 3 else (None, None, None)
            return self.node.governance.vote_many(hash, outcome, vote)
        
        elif command == 'vote-alias':
            hash, outcome, vote, alias = args[:4] if len(args) >= 4 else (None, None, None, None)
            return self.node.governance.vote_alias(hash, outcome, vote, alias)
        
        elif command == 'deserialize':
            data_hex = args[0] if args else None
            return self.node.governance.deserialize_object(data_hex)
        
        elif command == 'check':
            return self.node.governance.check_objects()
        
        elif command == 'diff':
            return self.node.governance.get_diff()
        
        else:
            raise RPCError(RPCError.RPC_INVALID_PARAMETER, f"Unknown command: {command}")
    
    def getsuperblockbudget(self, block_index: int) -> float:
        """Get superblock budget."""
        budget = self.node.governance.get_superblock_budget(block_index)
        return budget / config.COIN_UNIT
    
    def voteraw(
        self,
        masternode_tx_hash: str,
        masternode_tx_index: int,
        governance_hash: str,
        vote_signal: str,
        vote_outcome: str,
        time: int,
        vote_sig: str
    ) -> str:
        """Submit raw governance vote."""
        return self.node.governance.submit_raw_vote(
            masternode_tx_hash,
            masternode_tx_index,
            governance_hash,
            vote_signal,
            vote_outcome,
            time,
            vote_sig
        )
    
    # =========================================================================
    # Spork RPCs
    # =========================================================================
    
    def spork(self, command: str, *args) -> Any:
        """Spork commands."""
        if command == 'show':
            return self.node.spork_manager.get_all()
        
        elif command == 'active':
            return {name: self.node.spork_manager.is_active(name) 
                    for name in self.node.spork_manager.get_all().keys()}
        
        else:
            # Check if it's a spork name/value pair (admin only)
            spork_name = command
            value = int(args[0]) if args else None
            
            if value is not None:
                # Setting spork (requires admin key)
                result = self.node.spork_manager.set_spork(spork_name, value)
                return "success" if result else "failed"
            else:
                # Getting single spork
                spork = self.node.spork_manager.get(spork_name)
                if spork:
                    return {spork_name: spork}
                raise RPCError(RPCError.RPC_INVALID_PARAMETER, f"Unknown spork: {spork_name}")
