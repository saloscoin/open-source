@echo off
REM SALOCOIN Pool Mining Worker (Windows)
REM Usage: pool-worker.bat <your_address> [worker_name] [--gpu]

setlocal

if "%~1"=="" (
    echo Usage: pool-worker.bat ^<your_address^> [worker_name] [--gpu]
    echo.
    echo Examples:
    echo   pool-worker.bat SYmqMwa8mJqDCo99nzxEL41cYkqEgDuXfY
    echo   pool-worker.bat SYmqMwa8mJqDCo99nzxEL41cYkqEgDuXfY MyRig --gpu
    exit /b 1
)

set ADDRESS=%~1
set WORKER=%~2
set GPU_FLAG=%~3

if "%WORKER%"=="" set WORKER=worker1

echo.
echo ========================================
echo    SALOCOIN Pool Mining Worker
echo ========================================
echo.
echo Pool: pool.salocoin.org:7261
echo Address: %ADDRESS%
echo Worker: %WORKER%

if "%GPU_FLAG%"=="--gpu" (
    echo Mode: GPU Mining (OpenCL)
    echo.
    python pool_worker.py --pool pool.salocoin.org:7261 --address %ADDRESS% --worker %WORKER% --gpu
) else (
    echo Mode: CPU Mining
    echo.
    python pool_worker.py --pool pool.salocoin.org:7261 --address %ADDRESS% --worker %WORKER% --threads 4
)

endlocal
