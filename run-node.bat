@echo off
title SALOCOIN Node
echo Starting SALOCOIN Node...
echo.

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

:: Install dependencies if needed
pip show requests >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install requests
)

:: Run the node
python run_node.py %*

pause
