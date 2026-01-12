#!/bin/bash
# SALOCOIN Node Startup Script for Linux/Mac

echo "Starting SALOCOIN Node..."
echo

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 is not installed!"
    echo "Install with: sudo apt install python3 python3-pip"
    exit 1
fi

# Install dependencies
pip3 install requests 2>/dev/null

# Run node
python3 run_node.py "$@"
