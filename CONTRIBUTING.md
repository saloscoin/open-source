# Contributing

Use a branch and propose a pull request with a concrete problem, change and test result. Keep patches focused and explain consensus or wallet-file compatibility changes explicitly.

```sh
python -m pip install -r requirements-core.txt
python -m pytest -q
python -m compileall -q core network rpc exchange_node.py salocoind.py
```

Use temporary data directories and disposable keys. Never include mnemonics, private keys, wallet backups, RPC passwords, personal contact details, or production data in tests, logs or issues. Pseudonymous contributions are welcome; do not fabricate commits or change historical attribution.

Add behavior tests for security fixes and consensus changes. Document remaining limits. Do not advertise audits, production readiness, network availability or interoperability without reproducible evidence. For sensitive reports, see [SECURITY.md](SECURITY.md).
