#!/usr/bin/env python3
"""
SALOCOIN Bootstrap Node Server

Serves bootstrap.dat file for fast initial blockchain sync.
New nodes can download pre-packaged blockchain instead of syncing block-by-block.

Usage:
    python bootstrap_server.py --port 7340

Endpoints:
    /bootstrap.dat     - Download full bootstrap file
    /bootstrap.json    - Download as JSON
    /bootstrap/info    - Bootstrap file info
    /bootstrap/latest  - Latest blocks for quick update
"""

import os
import sys
import json
import time
import gzip
import struct
import hashlib
import threading
from datetime import datetime
from flask import Flask, Response, jsonify, request, send_file
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.blockchain import Blockchain, Block
import config

app = Flask(__name__)

# Configuration
DATA_DIR = os.environ.get('SALOCOIN_DATA', './data')
BOOTSTRAP_DIR = os.path.join(DATA_DIR, 'bootstrap')
BOOTSTRAP_FILE = os.path.join(BOOTSTRAP_DIR, 'bootstrap.dat')
BOOTSTRAP_JSON = os.path.join(BOOTSTRAP_DIR, 'bootstrap.json')
BOOTSTRAP_GZIP = os.path.join(BOOTSTRAP_DIR, 'bootstrap.dat.gz')

# Global blockchain instance
blockchain = None
last_export_height = 0
last_export_time = 0


def init_blockchain():
    """Initialize blockchain."""
    global blockchain
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BOOTSTRAP_DIR, exist_ok=True)
    blockchain = Blockchain(data_dir=DATA_DIR)
    blockchain.load()
    print(f"Blockchain loaded: {blockchain.get_height()} blocks")


def export_bootstrap_dat():
    """Export blockchain to bootstrap.dat file."""
    global last_export_height, last_export_time
    
    if not blockchain:
        return False
    
    height = blockchain.get_height()
    
    # Only re-export if new blocks
    if height <= last_export_height and os.path.exists(BOOTSTRAP_FILE):
        return True
    
    print(f"Exporting bootstrap.dat ({height} blocks)...")
    start_time = time.time()
    
    try:
        # Export as binary format
        with open(BOOTSTRAP_FILE, 'wb') as f:
            # Header: magic + version + block count
            f.write(config.MAINNET_MAGIC)  # 4 bytes magic
            f.write(struct.pack('<I', 1))   # 4 bytes version
            f.write(struct.pack('<I', height + 1))  # 4 bytes block count
            
            # Write each block
            for i in range(height + 1):
                block = blockchain.chain[i]
                block_data = json.dumps(block.to_dict()).encode('utf-8')
                
                # Block size + block data
                f.write(struct.pack('<I', len(block_data)))
                f.write(block_data)
        
        # Create gzipped version
        with open(BOOTSTRAP_FILE, 'rb') as f_in:
            with gzip.open(BOOTSTRAP_GZIP, 'wb') as f_out:
                f_out.writelines(f_in)
        
        # Export JSON version too
        blocks_json = [block.to_dict() for block in blockchain.chain]
        with open(BOOTSTRAP_JSON, 'w') as f:
            json.dump({
                'version': 1,
                'height': height,
                'blocks': blocks_json,
                'exported_at': int(time.time()),
                'genesis_hash': blockchain.chain[0].hash if blockchain.chain else None
            }, f)
        
        # Create gzipped JSON
        with open(BOOTSTRAP_JSON, 'rb') as f_in:
            with gzip.open(BOOTSTRAP_JSON + '.gz', 'wb') as f_out:
                f_out.writelines(f_in)
        
        last_export_height = height
        last_export_time = time.time()
        
        elapsed = time.time() - start_time
        file_size = os.path.getsize(BOOTSTRAP_FILE)
        gzip_size = os.path.getsize(BOOTSTRAP_GZIP)
        
        print(f"✓ Exported bootstrap.dat: {file_size/1024:.1f} KB ({gzip_size/1024:.1f} KB gzipped) in {elapsed:.1f}s")
        
        return True
        
    except Exception as e:
        print(f"Export error: {e}")
        return False


def export_loop():
    """Background thread to periodically export bootstrap."""
    while True:
        try:
            # Reload blockchain to get latest blocks
            blockchain.load()
            export_bootstrap_dat()
        except Exception as e:
            print(f"Export loop error: {e}")
        
        time.sleep(300)  # Export every 5 minutes


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    """Bootstrap node info."""
    height = blockchain.get_height() if blockchain else 0
    
    return jsonify({
        'service': 'SALOCOIN Bootstrap Node',
        'version': '1.0.0',
        'height': height,
        'endpoints': {
            'bootstrap.dat': '/bootstrap.dat',
            'bootstrap.dat.gz': '/bootstrap.dat.gz',
            'bootstrap.json': '/bootstrap.json',
            'bootstrap.json.gz': '/bootstrap.json.gz',
            'info': '/bootstrap/info',
            'latest': '/bootstrap/latest/<from_height>'
        },
        'last_export': last_export_time,
        'genesis_hash': config.GENESIS_HASH
    })


@app.route('/bootstrap.dat')
def download_bootstrap_dat():
    """Download bootstrap.dat file."""
    if not os.path.exists(BOOTSTRAP_FILE):
        export_bootstrap_dat()
    
    if os.path.exists(BOOTSTRAP_FILE):
        return send_file(
            BOOTSTRAP_FILE,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name='bootstrap.dat'
        )
    
    return jsonify({'error': 'Bootstrap file not available'}), 503


@app.route('/bootstrap.dat.gz')
def download_bootstrap_gzip():
    """Download gzipped bootstrap file."""
    if not os.path.exists(BOOTSTRAP_GZIP):
        export_bootstrap_dat()
    
    if os.path.exists(BOOTSTRAP_GZIP):
        return send_file(
            BOOTSTRAP_GZIP,
            mimetype='application/gzip',
            as_attachment=True,
            download_name='bootstrap.dat.gz'
        )
    
    return jsonify({'error': 'Bootstrap file not available'}), 503


@app.route('/bootstrap.json')
def download_bootstrap_json():
    """Download bootstrap as JSON."""
    if not os.path.exists(BOOTSTRAP_JSON):
        export_bootstrap_dat()
    
    if os.path.exists(BOOTSTRAP_JSON):
        return send_file(
            BOOTSTRAP_JSON,
            mimetype='application/json',
            as_attachment=True,
            download_name='bootstrap.json'
        )
    
    return jsonify({'error': 'Bootstrap file not available'}), 503


@app.route('/bootstrap.json.gz')
def download_bootstrap_json_gzip():
    """Download gzipped JSON bootstrap."""
    json_gz = BOOTSTRAP_JSON + '.gz'
    if not os.path.exists(json_gz):
        export_bootstrap_dat()
    
    if os.path.exists(json_gz):
        return send_file(
            json_gz,
            mimetype='application/gzip',
            as_attachment=True,
            download_name='bootstrap.json.gz'
        )
    
    return jsonify({'error': 'Bootstrap file not available'}), 503


@app.route('/bootstrap/info')
def bootstrap_info():
    """Get bootstrap file info."""
    info = {
        'height': blockchain.get_height() if blockchain else 0,
        'genesis_hash': config.GENESIS_HASH,
        'last_export': last_export_time,
        'last_export_height': last_export_height,
        'files': {}
    }
    
    for name, path in [
        ('bootstrap.dat', BOOTSTRAP_FILE),
        ('bootstrap.dat.gz', BOOTSTRAP_GZIP),
        ('bootstrap.json', BOOTSTRAP_JSON),
        ('bootstrap.json.gz', BOOTSTRAP_JSON + '.gz')
    ]:
        if os.path.exists(path):
            stat = os.stat(path)
            info['files'][name] = {
                'size': stat.st_size,
                'size_human': f"{stat.st_size/1024:.1f} KB" if stat.st_size < 1024*1024 else f"{stat.st_size/1024/1024:.1f} MB",
                'modified': int(stat.st_mtime),
                'url': f"https://bootstrap.salocoin.org/{name}"
            }
    
    return jsonify(info)


@app.route('/bootstrap/latest/<int:from_height>')
def get_latest_blocks(from_height: int):
    """Get blocks from a specific height (for incremental sync)."""
    if not blockchain:
        return jsonify({'error': 'Blockchain not loaded'}), 503
    
    height = blockchain.get_height()
    
    if from_height > height:
        return jsonify({
            'height': height,
            'blocks': []
        })
    
    # Limit to 1000 blocks per request
    to_height = min(from_height + 1000, height + 1)
    
    blocks = []
    for i in range(from_height, to_height):
        if i < len(blockchain.chain):
            blocks.append(blockchain.chain[i].to_dict())
    
    return jsonify({
        'height': height,
        'from': from_height,
        'to': to_height - 1,
        'count': len(blocks),
        'blocks': blocks
    })


@app.route('/status')
def status():
    """Node status."""
    return jsonify({
        'height': blockchain.get_height() if blockchain else 0,
        'service': 'bootstrap',
        'uptime': int(time.time() - app.start_time) if hasattr(app, 'start_time') else 0
    })


@app.route('/health')
def health():
    """Health check."""
    return jsonify({'status': 'ok', 'height': blockchain.get_height() if blockchain else 0})


# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='SALOCOIN Bootstrap Node')
    parser.add_argument('--port', '-p', type=int, default=7340, help='Port (default: 7340)')
    parser.add_argument('--host', default='0.0.0.0', help='Host (default: 0.0.0.0)')
    parser.add_argument('--data-dir', '-d', default='./data', help='Data directory')
    
    args = parser.parse_args()
    
    global DATA_DIR, BOOTSTRAP_DIR, BOOTSTRAP_FILE, BOOTSTRAP_JSON, BOOTSTRAP_GZIP
    DATA_DIR = args.data_dir
    BOOTSTRAP_DIR = os.path.join(DATA_DIR, 'bootstrap')
    BOOTSTRAP_FILE = os.path.join(BOOTSTRAP_DIR, 'bootstrap.dat')
    BOOTSTRAP_JSON = os.path.join(BOOTSTRAP_DIR, 'bootstrap.json')
    BOOTSTRAP_GZIP = os.path.join(BOOTSTRAP_DIR, 'bootstrap.dat.gz')
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║             SALOCOIN Bootstrap Node                      ║
╚══════════════════════════════════════════════════════════╝

Port:      {args.port}
Data Dir:  {DATA_DIR}

Endpoints:
  /bootstrap.dat       - Full bootstrap file
  /bootstrap.dat.gz    - Gzipped bootstrap
  /bootstrap.json      - JSON format
  /bootstrap/info      - File info
  /bootstrap/latest/N  - Blocks from height N

Starting...
""")
    
    # Initialize
    init_blockchain()
    
    # Initial export
    export_bootstrap_dat()
    
    # Start export thread
    export_thread = threading.Thread(target=export_loop, daemon=True)
    export_thread.start()
    
    # Track start time
    app.start_time = time.time()
    
    # Run server
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == '__main__':
    main()
