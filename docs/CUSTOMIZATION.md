# Cryptocurrency customization reference

| Goal | Inspect/change | Validation needed |
| --- | --- | --- |
| Name, ticker, units | `config.py` and UI/CLI strings | Formatting, amounts, no remaining SALO branding in your fork |
| Rewards and supply | `config.py`, coinbase and validation in `core/` | Halving boundaries, reward floor, cap enforcement |
| Timing and difficulty | `config.py`, `core/blockchain.py` | Retarget, stalled-chain recovery, hostile timestamps |
| Genesis identity | `GENESIS_BLOCK`, `GENESIS_HASH`, `_create_genesis_block()` | Header hash, merkle root, genesis PoW and same identity on all nodes |
| Address/key encoding | Prefixes, BIP32 versions, BIP44 coin type in `config.py`; wallet paths | Import/export, restore and address separation |
| Peer isolation | Magic bytes, ports, seeds; `network/protocol.py`, `network/discovery.py` | Reject foreign messages and cross-network peers |
| HTTP isolation | URLs in miners, wallets, node scripts and seed servers | No requests to upstream services or bootstrap data |

Some values are duplicated or hardcoded outside `config.py`. Search the entire tree and trace the running entry point. A configuration change is not evidence every component uses it. Consensus changes on an existing chain require a coordinated migration; use fresh data for a new coin.
