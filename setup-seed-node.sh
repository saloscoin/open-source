#!/bin/bash
# SALOCOIN Seed Node Quick Setup Script
# Run: bash setup-seed-node.sh

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║            SALOCOIN Seed Node Setup Script               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Please run as non-root user (will use sudo when needed)"
    exit 1
fi

# Update system
echo "[1/6] Updating system..."
sudo apt update && sudo apt upgrade -y

# Install Python
echo "[2/6] Installing Python 3.11..."
sudo apt install -y python3.11 python3.11-pip python3.11-venv git curl

# Install dependencies
echo "[3/6] Installing Python dependencies..."
pip3 install --user -r requirements.txt

# Configure firewall
echo "[4/6] Configuring firewall..."
sudo ufw allow 7339/tcp comment "SALOCOIN P2P"
sudo ufw allow 7340/tcp comment "SALOCOIN RPC"
sudo ufw --force enable

# Create systemd service
echo "[5/6] Creating systemd service..."
WORKDIR=$(pwd)
PYTHON=$(which python3.11)

sudo tee /etc/systemd/system/salocoind.service > /dev/null << EOF
[Unit]
Description=SALOCOIN Daemon
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORKDIR
ExecStart=$PYTHON salocoind.py --rpcbind=0.0.0.0 --printtoconsole
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable salocoind

# Start the node
echo "[6/6] Starting SALOCOIN node..."
sudo systemctl start salocoind

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                    Setup Complete!                        ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Node Status: sudo systemctl status salocoind            ║"
echo "║  View Logs:   journalctl -u salocoind -f                 ║"
echo "║  Stop Node:   sudo systemctl stop salocoind              ║"
echo "║  Start Node:  sudo systemctl start salocoind             ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  P2P Port: 7339  |  RPC Port: 7340                       ║"
echo "║  API: http://$(curl -s ifconfig.me):7340/status              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Genesis Hash: c52fd198c676978ce4d71d325b2e7703dc302e13621efb7efefe527a04793c0b"
echo ""
