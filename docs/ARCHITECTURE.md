# Python cryptocurrency architecture

`salocoind.py` constructs a `network.node.Node`, a wallet manager and RPC methods. The node owns blockchain/mempool state and starts peer discovery. `core/transaction.py` models inputs and outputs; `core/blockchain.py` handles block acceptance and indexes. Inspect validation code rather than assuming Bitcoin consensus equivalence.

## RPC request flow

```text
CLI / RPC client → HTTP POST → RPCHandler._authenticate()
  → JSON parsing → RPCServer.execute_method() → RPCMethods
  → node / blockchain / wallet → JSON-RPC result or error
```

`rpc/client.py` sends HTTP Basic credentials. `rpc/server.py` checks authentication before reading and dispatching a request. No session, JWT, refresh-token, or OAuth system exists. Basic authentication encodes credentials; it does not encrypt transport. Credentials are held in process memory. Remote use needs TLS or a protected tunnel and restricted access.

`exchange_node.py` has a separate REST handler and RPC instance. Its REST routes do not share RPC authentication. `run_node.py` and seed servers are further HTTP surfaces; securing one server does not secure the others. Exchange RPC method registration should be verified for each required integration; construction of an RPC server alone does not establish a working wallet API.

## Wallet persistence

`core/wallet.py` derives keys and stores address private keys and mnemonic in JSON. Saves use an owner-only temporary file and atomic replacement on POSIX. This reduces exposure and interrupted-write risk, but provides no cryptographic encryption or guaranteed secure erasure. Other wallet/export paths and backups need separate review.

The former `encrypt()` only set flags and still serialized private keys; `unlock()` accepted any password. These operations now fail explicitly. Legacy flagged files are retained for offline recovery, cannot be unlocked by this API, and cannot be overwritten through `save()`. HD wallets created with an extra BIP39 passphrase previously reloaded from the mnemonic without that passphrase; new creation with that option is rejected pending correct persistence.
