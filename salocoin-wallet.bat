@echo off
REM SALOCOIN Wallet CLI
setlocal
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%salocoin-wallet.py" %*
