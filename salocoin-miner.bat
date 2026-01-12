@echo off
REM SALOCOIN Miner CLI
setlocal
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%salocoin-miner.py" %*
