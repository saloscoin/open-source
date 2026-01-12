#!/bin/bash
# Production setup script for SALOCOIN Seed Server
# Run this on your VPS: bash setup-production.sh

set -e

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     SALOCOIN Seed Server - Production Setup               ║"
echo "╚═══════════════════════════════════════════════════════════╝"

# Install dependencies
echo "[1/5] Installing system dependencies..."
apt-get update
apt-get install -y python3-pip nginx

# Install Python packages
echo "[2/5] Installing Python packages..."
pip3 install flask gunicorn gevent

# Stop old service
echo "[3/5] Stopping old service..."
systemctl stop salocoin-seed 2>/dev/null || true

# Create production systemd service
echo "[4/5] Creating production systemd service..."
cat > /etc/systemd/system/salocoin-seed.service << 'EOF'
[Unit]
Description=SALOCOIN Seed Server (Production)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/salocoin
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/local/bin/gunicorn -c gunicorn_config.py seed_server_production:app
Restart=always
RestartSec=5

# Performance tuning
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF

# Reload and start
echo "[5/5] Starting production server..."
systemctl daemon-reload
systemctl enable salocoin-seed
systemctl start salocoin-seed

sleep 3

# Verify
echo ""
echo "Checking service status..."
systemctl status salocoin-seed --no-pager

echo ""
echo "Testing endpoint..."
curl -s http://localhost:7339/status | python3 -m json.tool

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     ✓ PRODUCTION SETUP COMPLETE                           ║"
echo "║                                                           ║"
echo "║  Workers: $(nproc) CPUs × 2 + 1 = $(($(nproc) * 2 + 1)) workers               ║"
echo "║  Max concurrent connections: ~$(($(nproc) * 2 * 2000))            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
