# Contributing

Use a branch and propose a pull request with a concrete problem, change and test result. Keep patches focused and explain consensus or wallet-file compatibility changes explicitly.

```sh
python -m pip install -r requirements-core.txt
python -m pytest -q
python examples/offline_walkthrough.py
python scripts/check_docs.py
python -m compileall -q core network rpc examples scripts exchange_node.py salocoind.py
```

Use temporary data directories and disposable keys. Never include mnemonics, private keys, wallet backups, RPC passwords, personal contact details, or production data in tests, logs or issues. Pseudonymous contributions are welcome; do not fabricate commits or change historical attribution.

Add behavior tests for security fixes and consensus changes. Document remaining limits. Do not advertise audits, production readiness, network availability or interoperability without reproducible evidence. For sensitive reports, see [SECURITY.md](SECURITY.md).

## Review workflow

1. Create a branch from the current main branch.
2. Reproduce the issue with disposable local data.
3. Make a focused change and update its guide or example.
4. Run the checks above and open a pull request using the template.

CI runs the core tests, offline example, link checks and compilation on the configured Linux, Windows and macOS Python matrix. A green check validates those steps; it is not a security audit or proof of network interoperability. Optional GPU/GUI/deployment paths are outside that matrix. Linux CLI packaging is available through the separate manual build workflow; its artifacts are experimental, and there is no automatic release/publishing step.

For documentation-only changes, run the link checker and affected examples. For behavioral changes, add a meaningful regression test under `tests/`; these files are allowed in source control.

Avoid broad formatting changes unrelated to your patch. Maintainers can assess a small, reproducible patch more easily. No signed-commit or real-name identity requirement is imposed by this guide.
