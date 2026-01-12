#!/usr/bin/env python3
"""
Auto Backup Script for SALOCOIN VPS
Backs up blockchain data periodically and manages old backups.

Usage:
    python3 auto_backup.py                    # Run backup once
    python3 auto_backup.py --install-cron     # Install hourly cron job
    python3 auto_backup.py --keep 24          # Keep only last 24 backups

Cron Examples:
    # Every hour
    0 * * * * cd /root/salocoin && python3 auto_backup.py >> /var/log/salocoin_backup.log 2>&1
    
    # Every 6 hours
    0 */6 * * * cd /root/salocoin && python3 auto_backup.py >> /var/log/salocoin_backup.log 2>&1
"""

import os
import sys
import json
import gzip
import shutil
import argparse
from datetime import datetime
from pathlib import Path

# Configuration
DATA_DIR = Path('/root/salocoin/data')
BACKUP_DIR = Path('/root/salocoin/backups')
BLOCKS_FILE = DATA_DIR / 'blocks.dat'
MEMPOOL_FILE = DATA_DIR / 'mempool.json'
MAX_BACKUPS = 48  # Keep last 48 backups (2 days if hourly)

def get_blockchain_height():
    """Get current blockchain height from blocks.dat"""
    try:
        if not BLOCKS_FILE.exists():
            return 0
        # Read the blocks file and count
        with open(BLOCKS_FILE, 'rb') as f:
            import struct
            height = 0
            while True:
                size_bytes = f.read(4)
                if len(size_bytes) < 4:
                    break
                size = struct.unpack('<I', size_bytes)[0]
                f.seek(size, 1)  # Skip block data
                height += 1
            return height - 1  # Height is 0-indexed
    except Exception as e:
        print(f"Warning: Could not read height: {e}")
        return 0

def backup_blocks():
    """Create a compressed backup of blocks.dat"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    if not BLOCKS_FILE.exists():
        print(f"Error: {BLOCKS_FILE} not found")
        return None
    
    height = get_blockchain_height()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f'blocks_h{height}_{timestamp}.dat.gz'
    backup_path = BACKUP_DIR / backup_name
    
    # Compress and save
    print(f"[{datetime.now().isoformat()}] Starting backup...")
    print(f"  Source: {BLOCKS_FILE}")
    print(f"  Height: {height}")
    
    original_size = BLOCKS_FILE.stat().st_size
    
    with open(BLOCKS_FILE, 'rb') as f_in:
        with gzip.open(backup_path, 'wb', compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    compressed_size = backup_path.stat().st_size
    ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
    
    print(f"  Backup: {backup_path}")
    print(f"  Original: {original_size / 1024 / 1024:.2f} MB")
    print(f"  Compressed: {compressed_size / 1024 / 1024:.2f} MB ({ratio:.1f}% reduction)")
    
    # Also backup mempool if exists
    if MEMPOOL_FILE.exists():
        mempool_backup = BACKUP_DIR / f'mempool_{timestamp}.json'
        shutil.copy2(MEMPOOL_FILE, mempool_backup)
        print(f"  Mempool: {mempool_backup}")
    
    return backup_path

def cleanup_old_backups(keep=MAX_BACKUPS):
    """Remove old backups, keeping only the most recent ones"""
    if not BACKUP_DIR.exists():
        return
    
    backups = sorted(BACKUP_DIR.glob('blocks_*.dat.gz'), reverse=True)
    
    if len(backups) <= keep:
        print(f"  Backups: {len(backups)} (keeping all)")
        return
    
    to_delete = backups[keep:]
    for backup in to_delete:
        backup.unlink()
        print(f"  Deleted old: {backup.name}")
    
    # Also clean old mempool backups
    mempool_backups = sorted(BACKUP_DIR.glob('mempool_*.json'), reverse=True)
    for mp in mempool_backups[keep:]:
        mp.unlink()
    
    print(f"  Kept {keep} recent backups, deleted {len(to_delete)}")

def list_backups():
    """List all available backups"""
    if not BACKUP_DIR.exists():
        print("No backups found")
        return
    
    backups = sorted(BACKUP_DIR.glob('blocks_*.dat.gz'), reverse=True)
    
    print(f"\n{'='*60}")
    print(f"SALOCOIN Backups ({BACKUP_DIR})")
    print(f"{'='*60}")
    
    total_size = 0
    for i, backup in enumerate(backups):
        size = backup.stat().st_size
        total_size += size
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"{i+1:3}. {backup.name:<40} {size/1024/1024:>6.2f} MB  {mtime.strftime('%Y-%m-%d %H:%M')}")
    
    print(f"{'='*60}")
    print(f"Total: {len(backups)} backups, {total_size/1024/1024:.2f} MB")

def install_cron():
    """Install cron job for automatic backups"""
    cron_line = "0 * * * * cd /root/salocoin && /usr/bin/python3 auto_backup.py --keep 48 >> /var/log/salocoin_backup.log 2>&1"
    
    print("Installing cron job for hourly backups...")
    print(f"Cron: {cron_line}")
    
    # Check if already installed
    import subprocess
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    current_cron = result.stdout if result.returncode == 0 else ""
    
    if 'auto_backup.py' in current_cron:
        print("Cron job already installed!")
        return
    
    # Add new cron job
    new_cron = current_cron.rstrip() + '\n' + cron_line + '\n'
    
    p = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
    p.communicate(input=new_cron)
    
    print("Cron job installed successfully!")
    print("Backups will run every hour and keep last 48 copies (2 days)")

def main():
    parser = argparse.ArgumentParser(description='SALOCOIN Auto Backup')
    parser.add_argument('--keep', type=int, default=MAX_BACKUPS, help='Number of backups to keep')
    parser.add_argument('--list', action='store_true', help='List all backups')
    parser.add_argument('--install-cron', action='store_true', help='Install hourly cron job')
    args = parser.parse_args()
    
    if args.list:
        list_backups()
        return
    
    if args.install_cron:
        install_cron()
        return
    
    # Run backup
    backup_path = backup_blocks()
    if backup_path:
        cleanup_old_backups(keep=args.keep)
        print(f"[{datetime.now().isoformat()}] Backup complete!")

if __name__ == '__main__':
    main()
