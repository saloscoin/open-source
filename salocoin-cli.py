#!/usr/bin/env python3
"""
SALOCOIN CLI
Command-line interface for interacting with SALOCOIN daemon.

Usage:
    python salocoin-cli.py [options] <command> [params...]

Options:
    --rpcconnect=<ip>   RPC server IP (default: 127.0.0.1)
    --rpcport=<port>    RPC port (default: 7340)
    --rpcuser=<user>    RPC username
    --rpcpassword=<pw>  RPC password
    --testnet           Use testnet
    --help              Show help for a command

Commands:
    getinfo             Get node information
    getblockchaininfo   Get blockchain information
    getnetworkinfo      Get network information
    getpeerinfo         Get peer information
    getbalance          Get wallet balance
    getnewaddress       Generate new address
    sendtoaddress       Send to address
    masternode          Masternode commands
    gobject             Governance commands
    help                List all commands
"""

import sys
import os
import argparse
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from rpc import RPCClient, RPCResponseError, RPCClientError


def format_output(result, pretty=True):
    """Format output for display."""
    if result is None:
        return ""
    
    if isinstance(result, (dict, list)):
        if pretty:
            return json.dumps(result, indent=2, default=str)
        return json.dumps(result, default=str)
    
    return str(result)


def print_help(command=None):
    """Print help for commands."""
    if command:
        help_text = {
            'getinfo': """
getinfo
Returns general information about the node.
""",
            'getblockchaininfo': """
getblockchaininfo
Returns information about the blockchain.
""",
            'getnetworkinfo': """
getnetworkinfo
Returns information about the network.
""",
            'getpeerinfo': """
getpeerinfo
Returns information about connected peers.
""",
            'getbalance': """
getbalance [minconf] [include_watchonly]
Returns the wallet balance.

Arguments:
    minconf             Minimum confirmations (default: 1)
    include_watchonly   Include watch-only addresses (default: false)
""",
            'getnewaddress': """
getnewaddress [label] [address_type]
Returns a new SALOCOIN address.

Arguments:
    label               Label for the address
    address_type        Address type (legacy)
""",
            'sendtoaddress': """
sendtoaddress <address> <amount> [comment] [comment_to] [subtractfeefromamount]
Send to an address.

Arguments:
    address             Destination address
    amount              Amount in SALO
    comment             Comment (optional)
    comment_to          Comment for recipient (optional)
    subtractfeefromamount  Subtract fee from amount (default: false)
""",
            'masternode': """
masternode <command> [params...]
Masternode commands.

Commands:
    count               Get masternode count
    current             Get current masternode winner
    list                List masternodes
    outputs             List masternode collateral outputs
    status              Get masternode status
    start-alias <alias> Start masternode by alias
    start-all           Start all masternodes
    genkey              Generate masternode private key
""",
            'gobject': """
gobject <command> [params...]
Governance object commands.

Commands:
    count               Get governance object count
    list [type]         List governance objects
    get <hash>          Get governance object
    getvotes <hash>     Get governance object votes
    submit              Submit governance object
    vote-conf           Vote with current masternode
    vote-many           Vote with all masternodes
""",
            'instantsendtoaddress': """
instantsendtoaddress <address> <amount>
Send using InstantSend.

Arguments:
    address             Destination address
    amount              Amount in SALO
""",
            'privatesend': """
privatesend <command>
PrivateSend commands.

Commands:
    start               Start PrivateSend mixing
    stop                Stop PrivateSend mixing
    reset               Reset PrivateSend
    status              Get PrivateSend status
""",
        }
        
        if command in help_text:
            print(help_text[command])
        else:
            print(f"No help available for '{command}'")
    else:
        print("""
SALOCOIN CLI Commands:

=== Blockchain ===
getblockchaininfo       Get blockchain info
getblockcount           Get current block height
getbestblockhash        Get best block hash
getblock <hash>         Get block by hash
getblockhash <height>   Get block hash by height
getdifficulty           Get current difficulty

=== Network ===
getnetworkinfo          Get network info
getpeerinfo             Get peer info
getconnectioncount      Get connection count
addnode <ip> <cmd>      Add/remove node
ping                    Ping all peers

=== Wallet ===
getwalletinfo           Get wallet info
getbalance              Get balance
getnewaddress           Generate new address
listunspent             List unspent outputs
sendtoaddress           Send to address
sendmany                Send to multiple addresses
signmessage             Sign message
verifymessage           Verify signed message
dumpprivkey             Dump private key
importprivkey           Import private key
encryptwallet           Encrypt wallet
walletpassphrase        Unlock wallet
walletlock              Lock wallet

=== Masternode ===
masternode count        Get masternode count
masternode list         List masternodes
masternode status       Get masternode status
masternode outputs      List collateral outputs
masternode genkey       Generate masternode key

=== Governance ===
gobject count           Get governance object count
gobject list            List governance objects
gobject get <hash>      Get governance object
gobject submit          Submit governance object
gobject vote-conf       Vote with masternode
getsuperblockbudget     Get superblock budget

=== InstantSend ===
instantsendtoaddress    Send with InstantSend

=== PrivateSend ===
privatesend start       Start mixing
privatesend stop        Stop mixing
privatesend status      Get mixing status

=== Mining ===
getmininginfo           Get mining info
getblocktemplate        Get block template
submitblock             Submit mined block

=== Control ===
getinfo                 Get node info
help [command]          Show help
stop                    Stop daemon
""")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SALOCOIN CLI",
        add_help=False,
    )
    
    parser.add_argument('--rpcconnect', type=str, default='127.0.0.1',
                       help='RPC server IP')
    parser.add_argument('--rpcport', type=int,
                       help='RPC port')
    parser.add_argument('--rpcuser', type=str,
                       help='RPC username')
    parser.add_argument('--rpcpassword', type=str,
                       help='RPC password')
    parser.add_argument('--testnet', action='store_true',
                       help='Use testnet')
    parser.add_argument('--help', '-h', action='store_true',
                       help='Show help')
    parser.add_argument('command', nargs='?',
                       help='Command to execute')
    parser.add_argument('params', nargs='*',
                       help='Command parameters')
    
    args = parser.parse_args()
    
    # Show help
    if args.help and not args.command:
        print_help()
        return
    
    if args.help and args.command:
        print_help(args.command)
        return
    
    if not args.command:
        print("Error: No command specified. Use --help for usage.")
        sys.exit(1)
    
    # Help command
    if args.command == 'help':
        if args.params:
            print_help(args.params[0])
        else:
            print_help()
        return
    
    # RPC configuration
    rpc_port = args.rpcport or (config.RPC_TESTNET_PORT if args.testnet else config.RPC_PORT)
    
    # Try to read from config file
    rpcuser = args.rpcuser
    rpcpassword = args.rpcpassword
    
    if not rpcuser or not rpcpassword:
        config_file = config.get_config_file(args.testnet)
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            if key.strip() == 'rpcuser' and not rpcuser:
                                rpcuser = value.strip()
                            elif key.strip() == 'rpcpassword' and not rpcpassword:
                                rpcpassword = value.strip()
            except Exception:
                pass
    
    # Create RPC client
    client = RPCClient(
        host=args.rpcconnect,
        port=rpc_port,
        username=rpcuser,
        password=rpcpassword,
    )
    
    # Execute command
    try:
        # Parse parameters
        params = []
        for p in args.params:
            # Try to parse as JSON
            try:
                params.append(json.loads(p))
            except json.JSONDecodeError:
                # Try to parse as number
                try:
                    if '.' in p:
                        params.append(float(p))
                    else:
                        params.append(int(p))
                except ValueError:
                    # Keep as string
                    params.append(p)
        
        # Call RPC method
        result = client.call(args.command, *params)
        
        # Print result
        output = format_output(result)
        if output:
            print(output)
        
    except RPCResponseError as e:
        print(f"error: {e.message}", file=sys.stderr)
        sys.exit(1)
        
    except RPCClientError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
        
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
