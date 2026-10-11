# Changelog

Changes below are proposed in the current pull request. They are not a tagged release.

## Unreleased

### Developer experience

- Present the project as a Bitcoin-like Python cryptocurrency implementation.
- Add an offline keys/signatures/wallet/block-template walkthrough.
- Add installation, troubleshooting, architecture and coin-customization guides.
- Add a documentation index, issue/PR templates, and cross-platform CI.
- Focus required CI on core dependencies and reproducible checks; move Linux executable builds to manual dispatch. Earlier nonblocking audit/type-check commands are not presented as passing quality gates.

### Security behavior changes

- Disable the former flag-only wallet encryption and password-free unlock behavior.
- Preserve legacy flagged wallet files by refusing saves through the wallet API.
- Use owner-only atomic wallet writes on POSIX; keys still remain plaintext.
- Reject new HD wallets with unsupported extra-passphrase persistence.
- Reject incomplete/empty RPC credentials and unauthenticated non-loopback RPC.
- Strictly decode Basic authentication and compare credentials in constant time.
- Require explicit exchange RPC credentials, bind RPC/REST to loopback and remove password logging.
- Correct RPC server shutdown to use the matching serving loop.

Existing exchange deployments need a protected proxy or tunnel for remote API access. See [security limitations](SECURITY.md) before upgrading. No consensus parameters or historical attribution are changed.
