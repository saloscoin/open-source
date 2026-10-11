# API access and authentication

## Daemon JSON-RPC

`salocoind.py` exposes JSON-RPC over HTTP, defaulting to `127.0.0.1:7340` (testnet: `17340`). The CLI wraps RPC calls:

```sh
python salocoin-cli.py getblockchaininfo
python salocoin-cli.py getpeerinfo
python salocoin-cli.py help
```

With the local unauthenticated development daemon, the equivalent request is:

```sh
curl -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"getblockchaininfo","params":[],"id":1}' \
  http://127.0.0.1:7340/
```

Use `curl.exe` explicitly on Windows when PowerShell resolves `curl` to another command. The Python CLI is the cross-platform starting point.

When configured, RPC authenticates with HTTP Basic before dispatch. Both username and password must be provided and nonempty. Non-loopback RPC cannot run without credentials. Basic authentication does not encrypt traffic; use a protected tunnel or TLS gateway with restricted access. There are no JWTs, sessions or OAuth tokens in this implementation.

Wallet methods can sign, spend or export keys. Do not expose wallet RPC to untrusted clients. Encryption-related methods remain listed in older help, but now fail explicitly rather than pretending to encrypt or verify passwords.

## Exchange node

`exchange_node.py` exposes a separate REST server and RPC instance. Both bind to loopback after hardening. Supply credentials in its process environment:

- `SALO_RPC_USER`: chosen RPC username
- `SALO_RPC_PASSWORD`: a private, strong password

Its CLI also accepts `--rpcuser` and `--rpcpassword`, which may expose values in process listings. REST has no built-in authentication, and RPC credentials do not secure it. If remote access is necessary, place access controls, TLS and request limits at a protected gateway. Verify every required RPC method before integrating: this entry point does not establish a complete wallet API simply by constructing an RPC server.

## Other HTTP nodes

`run_node.py`, seed servers and bootstrap services have their own handlers. Their authentication and binding behavior must be reviewed separately. Do not infer REST ports or access rules from the binary P2P daemon. See the [component guide](COMPONENTS.md) and [security limitations](../SECURITY.md).
