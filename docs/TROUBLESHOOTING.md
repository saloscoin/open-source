# Troubleshooting

Run checks with the same virtual-environment interpreter used to install dependencies. Use disposable data and sanitize output before opening an issue.

| Symptom | What to check |
| --- | --- |
| `python` or `py` is unavailable | Install Python 3.10+; on macOS/Linux try `python3`, on Windows try `py -3`. Check the version before creating `.venv`. |
| `ModuleNotFoundError` | Run the environment's Python with `-m pip install -r requirements-core.txt`. Installing packages with a different interpreter will not fix this environment. |
| PowerShell blocks activation | Use `.\.venv\Scripts\python.exe` directly. Activation is unnecessary. |
| GPU or desktop package fails to build | Start with core requirements. GPU mining additionally needs compatible OpenCL drivers; desktop operation needs GUI support. |
| `Address already in use` | Stop the earlier node or select distinct P2P/RPC ports. Separate processes also need separate data directories. |
| RPC connection refused | Confirm the daemon is running and the CLI port matches. Daemon defaults are loopback port 7340; testnet uses 17340. |
| RPC HTTP 401 | Match both username and password. Authentication must be configured as a complete, nonempty pair. |
| Exchange node refuses startup | Set explicit `SALO_RPC_USER` and `SALO_RPC_PASSWORD` or pass its credential flags. Defaults were removed. |
| Remote exchange REST/RPC cannot connect | Hardened exchange services listen on `127.0.0.1`; use a restricted, authenticated proxy or tunnel. REST has no built-in authentication. |
| Encryption or unlock raises an error | This is intentional. The former implementation was insecure; preserve legacy files privately and follow the security guidance. |
| Genesis hash mismatch warning | Review the known genesis behavior in [SECURITY.md](../SECURITY.md). It does not mean a dependency is missing. |
| Tests are not added to Git | Tests under `tests/` are now explicitly allowed by `.gitignore`; keep regression tests there. |

## Useful diagnostics

```sh
python --version
python -m pip check
python -m pytest -q
python examples/offline_walkthrough.py
```

Include OS, Python version, repository commit, entry point and a minimal reproduction in a bug report. Never upload wallets, recovery phrases, RPC passwords or private keys. See [contributing](../CONTRIBUTING.md) and [security reporting](../SECURITY.md).
