# SALOCOIN — Open-Source Bitcoin-Like Cryptocurrency in Python

Study and customize a Python blockchain implementation to develop your own coin and independent Proof-of-Work network.

SALOCOIN is MIT-licensed cryptocurrency source code with Bitcoin-inspired UTXO transactions, SHA-256d mining, wallet key derivation, peer-to-peer networking, and JSON-RPC interfaces. It provides code to explore how a blockchain node, wallet, miner, and mining pool fit together. Building an independent cryptocurrency requires coordinated consensus changes, network isolation, testing, and security review; a fork alone does not provide a secure currency.

This is an experimental implementation. It is not audited for production custody. It does not implement Ethereum's EVM or promise Bitcoin wire, wallet, or ASIC interoperability. A shared mining hash algorithm is not proof of interoperability.

## Start here

- [Local quickstart](#local-quickstart)
- [Architecture and request flow](docs/ARCHITECTURE.md)
- [Create your own coin and network](docs/CREATE_YOUR_OWN_COIN.md)
- [Customization reference](docs/CUSTOMIZATION.md)
- [Contributing](CONTRIBUTING.md)
- [Security limitations](SECURITY.md)

## Components

| Source | Purpose |
| --- | --- |
| `core/blockchain.py`, `core/transaction.py` | Blocks, UTXOs, transaction validation, chain storage |
| `core/crypto.py`, `core/wallet.py` | Keys, signatures, mnemonic/HD derivation, wallet files |
| `network/` | Binary P2P messages, peers, discovery |
| `rpc/`, `salocoind.py`, `salocoin-cli.py` | Node/wallet JSON-RPC and command-line client |
| `exchange_node.py`, `run_node.py`, `seed_server*.py` | Separate HTTP API/node entry points |
| `miner.py`, `gpu_miner.py`, `pool/` | Mining and pool implementations |
| `masternode/` | Additional governance and masternode code requiring separate review |

Parameters in `config.py` include a 150-second target block time, 100-coin initial reward, and 210,000-block halving interval. The minimum reward floor and supply-cap enforcement must be reviewed together before advertising a fixed supply. Source parameters do not establish current network status.

## Local quickstart

Use Python 3.10+ and a disposable development environment. These offline steps do not start peer discovery or contact public seeds:

```sh
git clone https://github.com/saloscoin/open-source.git
cd open-source
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-core.txt
python -m pytest -q
python salocoind.py --help
python salocoin-cli.py --help
```

Create an experimental wallet locally:

```sh
python wallet.py create --name demo
python wallet.py info --name demo
```

The creation command prints the recovery mnemonic. Wallet files contain **plaintext private keys**; use disposable keys, encrypted storage, and private backups. Do not paste output into issues or commit wallet files. Encryption RPC operations are disabled because the old implementation did not encrypt keys or verify passwords.

For a node connected to SALOCOIN peers, after reviewing [security](SECURITY.md):

```sh
python salocoind.py --datadir ./development-data --rpcbind 127.0.0.1
# In another terminal, with the same virtual environment:
python salocoin-cli.py getblockchaininfo
```

This loopback-only RPC example has no authentication and is suitable only for a trusted, isolated machine. P2P listens externally and peer discovery can contact SALOCOIN seeds. Stop with Ctrl+C. For an independent network, follow the [new coin guide](docs/CREATE_YOUR_OWN_COIN.md) first. `--testnet` is not a substitute for that work.

`requirements.txt` additionally lists desktop, GPU, server, and tooling dependencies. Install optional packages only for the components you use.

## Existing operational references

[Exchange integration](EXCHANGE_INTEGRATION.md), [community seeds](COMMUNITY_SEED_NODE.md), [seed setup](SEED_NODE_SETUP.md), and [whitepaper](WHITEPAPER.md) describe earlier deployment plans. Their security, availability, compatibility, and readiness claims are not independently verified. In particular, old exchange examples using default credentials or public API bindings no longer describe safe defaults. Prefer the security guidance here.

## License and project scope

See [MIT License](LICENSE). Keep required copyright notices when distributing a fork. Contributions can use a pseudonym; no real-name biography is required.

For developers searching for open-source cryptocurrency code, a Bitcoin-like Python blockchain, UTXO wallet source code, Proof-of-Work mining, or how to create a cryptocurrency network, begin with the architecture and customization guides above.
