# Create your own coin and independent blockchain network

This is an engineering checklist for a new experimental cryptocurrency, not a one-command production launch. Start on isolated hosts with disposable keys.

1. Fork the MIT-licensed repository and choose a distinct name/ticker. Preserve license notices. Keep contributor identities private; do not add personal details or rewrite historical authorship.
2. Define consensus parameters using the [customization reference](CUSTOMIZATION.md). Specify issuance precisely, including the minimum reward floor and intended supply cap. Test monetary rules before publishing claims.
3. Create a distinct genesis block in your fork. Review `_create_genesis_block()` in `core/blockchain.py`: it contains a hardcoded coinbase address and substitutes the configured hash on mismatch. Replace that behavior with validation that rejects mismatches in your new network. Construct consistent coinbase, merkle root, timestamp, difficulty and nonce, compute the header hash and verify PoW. Freeze identical genesis fixtures across nodes; do not simply invent a `GENESIS_HASH` string.
4. Assign distinct P2P magic bytes, main/test ports, address/WIF prefixes and HD versions/coin type. Review collisions and all encoding paths. The upstream mainnet magic matches Bitcoin's; do not retain it for an independent network. `--testnet` changes some values but does not provide comprehensive wallet/genesis/discovery separation.
5. Remove upstream DNS/IP seeds and every public HTTP seed, bootstrap, wallet, miner and pool URL. Search all entry points, not just `config.py`. Configure only your own controlled peers. Block outbound traffic during initial checks to verify no upstream discovery occurs.
6. Use fresh data directories for every node; never reuse SALOCOIN chain files or bootstrap downloads. Start two nodes on a private network, keep RPC/REST local, and connect only your controlled peers. There is no verified isolated-network CLI preset here; complete the preceding source changes first.
7. Test mining, peer synchronization, spend/signature rejection, coinbase maturity, rewards, restore, restart and chain conflicts. Assert that foreign genesis/messages/addresses are rejected. Repeat on your private test network and reproduce the results from a clean checkout.
8. Review custody, consensus, denial-of-service resistance, dependencies, backups and API boundaries before involving real value. Publish limitations, versioned network parameters, and reproducible launch instructions. Obtain independent review before claiming secure production operation.

A coin is an independent chain here, not an Ethereum token. This implementation does not supply EVM smart contracts or ERC-20 compatibility.
