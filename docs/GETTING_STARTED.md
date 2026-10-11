# Getting started

Start with the offline walkthrough, then choose whether you need a persistent wallet or a networked node. Use disposable keys and separate development data.

## 1. Install a minimal development environment

Install Git and Python 3.10+. Clone the repository and create a virtual environment as shown in the [README](../README.md). Run all commands from the repository root. Use the environment's Python directly; shell activation is optional.

| Platform | Python command after creating `.venv` |
| --- | --- |
| Linux/macOS | `.venv/bin/python` |
| Windows | `.\.venv\Scripts\python.exe` |

In examples below, `python` means that interpreter. Replace it with the command above, or activate the virtual environment first.

```sh
python -m pip install -r requirements-core.txt
python -m pip check
python examples/offline_walkthrough.py
python -m pytest -q
python scripts/check_docs.py
```

The walkthrough prints six checks, with signature verification, changed-message rejection and wallet reload set to `true`. It uses temporary storage and does not start a node or contact seeds. A block template is not a mined or accepted block.

`requirements-core.txt` contains the node/wallet/RPC libraries and pytest. Full `requirements.txt` includes optional GPU, GUI, web-server and documentation tooling. Avoid installing the full file for a first walkthrough. The repository is run from source; `setup.py` is a legacy helper, not a standard pip package installer. Do not use `pip install .` as the onboarding path.

## 2. Create a persistent experimental wallet

```sh
python wallet.py create --name demo
python wallet.py info --name demo
python wallet.py newaddress --name demo --label learning
```

The wallet is saved in `wallets/demo.json`. Creation prints a mnemonic, so use a private terminal and do not share its output. Record recovery material privately and verify a backup/restore workflow before keeping valuable keys. The offline example does not print a mnemonic and is preferable for screenshots or bug reports.

Files contain plaintext keys. The former encryption implementation has been disabled because it did not protect them. See [wallet limitations](../SECURITY.md). `wallet.py` and the daemon use different wallet directories/file conventions; do not assume a file created by one is automatically active in the other.

## 3. Inspect command-line options

```sh
python salocoind.py --help
python salocoin-cli.py --help
python exchange_node.py --help
```

Choose an entry point using the [component guide](COMPONENTS.md). The daemon and exchange node are separate applications; their flags and APIs differ.

## 4. Run a SALOCOIN-connected development node

Only after reviewing [security](../SECURITY.md):

```sh
python salocoind.py --datadir ./development-data --rpcbind 127.0.0.1
```

In a second terminal using the same environment:

```sh
python salocoin-cli.py getblockchaininfo
python salocoin-cli.py getpeerinfo
```

Stop the foreground daemon with Ctrl+C. Chain data stays in `development-data/` for the next start. This example leaves RPC unauthenticated on loopback, so use a trusted, isolated machine. P2P listens externally and discovery can contact SALOCOIN seeds. The data directory separates files, not network identity. Do not run multiple nodes with the same data directory.

A genesis mismatch warning is a documented upstream consensus issue, not an installation error. The code substitutes its configured genesis hash; review that limitation before network experiments. The offline walkthrough avoids loading that chain.

For explicit RPC credentials, the daemon accepts `--rpcuser` and `--rpcpassword`; the CLI must use the same values. CLI passwords may appear in process listings. Non-loopback RPC requires credentials and a protected transport/access boundary.

## 5. Choose your next step

- Study [architecture and request flow](ARCHITECTURE.md).
- Inspect [API access and authentication](API.md).
- Follow [create your own coin](CREATE_YOUR_OWN_COIN.md) before starting an independent network.
- Read [contribution instructions](../CONTRIBUTING.md) to propose an improvement.
