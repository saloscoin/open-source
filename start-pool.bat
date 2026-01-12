@echo off
REM Start SALOCOIN Mining Pool Server (Windows)
REM Usage: start-pool.bat <pool_address> <pool_privkey> [fee_percent]

setlocal

if "%~1"=="" (
    echo Usage: start-pool.bat ^<pool_address^> ^<pool_privkey^> [fee_percent]
    echo Example: start-pool.bat SN1qdiiNCaNjzs2mMV7Gg5jHWabdYX193q YOUR_PRIVATE_KEY 1.0
    exit /b 1
)

if "%~2"=="" (
    echo Error: Pool private key is required
    echo Usage: start-pool.bat ^<pool_address^> ^<pool_privkey^> [fee_percent]
    exit /b 1
)

set POOL_ADDRESS=%~1
set POOL_PRIVKEY=%~2
set FEE=%~3
if "%FEE%"=="" set FEE=1.0

echo.
echo ========================================
echo    SALOCOIN Mining Pool Server
echo ========================================
echo.
echo Pool Address: %POOL_ADDRESS%
echo Pool Fee: %FEE%%%
echo Stratum Port: 7261
echo HTTP API Port: 7262
echo.
echo Starting pool server...
echo.

python -m pool.pool_server --address %POOL_ADDRESS% --privkey %POOL_PRIVKEY% --fee %FEE% --port 7261 --http 7262

endlocal
