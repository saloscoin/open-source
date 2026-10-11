# Security limitations and reporting

This repository has no demonstrated independent security audit. Use it for study and controlled experiments; production custody requires further review.

## Wallets and keys

Wallet JSON contains plaintext private keys and recovery mnemonics. The old encryption flag did not protect them and unlock did not verify passwords. New encryption requests and legacy flagged unlocks now fail explicitly; flagged files cannot be overwritten by `save()`. Preserve a private copy before offline recovery. Existing flagged files may lack a mnemonic, but their address keys remain sensitive. Do not delete them or treat them as securely encrypted.

Wallet saves now atomically replace files using owner-only temporary files on POSIX. Windows ACLs, directory permissions, existing files, exports and backups still need attention. Use encrypted storage, restricted access and offline backups. File permissions do not protect against malware or a compromised account. New HD creation with an extra passphrase is disabled because its restore path did not preserve it correctly. Existing passphrase-derived wallets need careful recovery testing with the original passphrase; mnemonic-only reload may derive a different branch.

## RPC and REST

RPC uses HTTP Basic authentication, with strict header decoding and constant-time credential comparisons. Incomplete or empty credentials are rejected. Unauthenticated RPC is allowed only on a literal loopback address; local processes may still call it. Non-loopback RPC requires credentials but has no built-in TLS, rate limiting or comprehensive request-size defenses. Protect it with a tunnel or TLS gateway, firewall and access controls.

The exchange node now requires explicit credentials, binds RPC and REST to `127.0.0.1`, and no longer prints passwords. Set `SALO_RPC_USER` and `SALO_RPC_PASSWORD` in its process environment (or pass CLI options, which may appear in process listings). REST remains unauthenticated. Exposing it through a proxy requires endpoint-specific authorization, limits and TLS. RPC credentials do not authenticate REST. Other HTTP entry points, especially `run_node.py --public` and seed servers, retain their own exposure behavior.

## Consensus and deployment

Genesis construction substitutes the configured hash on mismatch rather than rejecting it. Testnet isolation, supply-cap enforcement, retargeting, signature handling, reorgs and cross-network behavior require further validation. These hardening changes are not a complete security repair. Optional dependency versions are not locked, and public deployment scripts or earlier integration docs must be reviewed before execution.

## Reporting

Do not post keys, credentials, personal details, or live exploit instructions in public issues. Use the repository's private vulnerability reporting feature if enabled. No dedicated private reporting address or guaranteed response time is documented. If private reporting is unavailable, ask maintainers for a private channel using a nonsensitive issue before sharing details. Remove secrets from ordinary bug reports and provide a disposable local reproduction.
