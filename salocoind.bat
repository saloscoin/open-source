@echo off
REM SALOCOIN Daemon CLI
setlocal
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%salocoind-cli.py" %*
