# Choosing an entry point

The repository has several applications developed for different workflows. Start with the smallest one that matches your task.

| Entry point | Use | Dependencies and cautions |
| --- | --- | --- |
| `examples/offline_walkthrough.py` | Learn keys, signatures, wallet reload and block headers | Core requirements; temporary data; no network |
| `wallet.py` | Simple local wallet management | Core; stores files under repository `wallets/` |
| `salocoind.py` + `salocoin-cli.py` | Binary P2P node with wallet/node JSON-RPC | Core; discovery contacts seeds; RPC local by default |
| `salocoin-wallet.py` | HTTP-seed-oriented wallet CLI | Core; remote HTTP services and separate file handling |
| `exchange_node.py` | Combined P2P, REST and RPC exchange-oriented node | Core; explicit credentials; local REST/RPC; integration completeness needs review |
| `run_node.py` | HTTP node/relay workflow | Separate HTTP routes; review seed configuration and public exposure |
| `miner.py` | CPU mining client | Review `--help` and seed endpoints before running |
| `gpu_miner.py`, `pool_worker.py` | GPU or pool worker workflows | Optional OpenCL/numpy and platform drivers |
| `pool/pool_server.py`, `asic_solo_proxy.py` | Pool server or solo mining proxy | Review payout keys, network endpoints and protocol compatibility |
| `seed_server*.py`, `bootstrap_server.py` | HTTP seed/bootstrap services | Some require Flask/Gunicorn/gevent; deployment scripts need independent review |

These entry points do not share a universal CLI, wallet location or authentication policy. Core setup is intended for learning and local tests; it does not certify every optional deployment path.

## Finding options

For a chosen Python entry point, read its source and run `--help` before starting it. Treat older batch/shell launchers as examples: inspect embedded URLs, directories, credentials and public bindings first.

Start with [getting started](GETTING_STARTED.md), then use [architecture](ARCHITECTURE.md) to trace ownership. For independent coin development, all entry points you retain must use your own network and service identifiers.
