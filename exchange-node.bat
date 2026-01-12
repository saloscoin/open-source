@echo off
REM SALOCOIN Exchange Node
REM Full node with P2P, RPC, and REST API

echo.
echo ========================================
echo   SALOCOIN Exchange Node
echo ========================================
echo.

REM Default settings
set P2P_PORT=9339
set RPC_PORT=7340
set API_PORT=7339
set RPC_USER=rpcuser
set RPC_PASSWORD=rpcpassword

REM Parse arguments
:parse_args
if "%~1"=="" goto start_node
if "%~1"=="--testnet" set TESTNET=--testnet
if "%~1"=="--p2p-port" set P2P_PORT=%~2 & shift
if "%~1"=="--rpc-port" set RPC_PORT=%~2 & shift
if "%~1"=="--api-port" set API_PORT=%~2 & shift
if "%~1"=="--rpcuser" set RPC_USER=%~2 & shift
if "%~1"=="--rpcpassword" set RPC_PASSWORD=%~2 & shift
shift
goto parse_args

:start_node
echo Starting with:
echo   P2P Port: %P2P_PORT%
echo   RPC Port: %RPC_PORT%
echo   API Port: %API_PORT%
echo   RPC User: %RPC_USER%
echo.

python exchange_node.py --p2p-port %P2P_PORT% --rpc-port %RPC_PORT% --api-port %API_PORT% --rpcuser %RPC_USER% --rpcpassword %RPC_PASSWORD% %TESTNET%

pause
