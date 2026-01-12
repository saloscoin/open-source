#!/usr/bin/env python3
"""Backup blocks from SALOCOIN network"""

import requests
import json
import os
from datetime import datetime

SEED = 'https://api.salocoin.org'
BACKUP_DIR = 'backups'

os.makedirs(BACKUP_DIR, exist_ok=True)

print('Fetching blocks from network...')
resp = requests.get(f'{SEED}/blocks', timeout=60)
blocks = resp.json()
print(f'Got {len(blocks)} blocks')

# Save to backup file with timestamp
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
filename = f'{BACKUP_DIR}/blocks_{ts}.json'

with open(filename, 'w') as f:
    json.dump(blocks, f, indent=2)

height = blocks[-1].get('height', 0) if blocks else 0
size_kb = os.path.getsize(filename) / 1024

print(f'Saved: {filename}')
print(f'Latest height: {height}')
print(f'File size: {size_kb:.1f} KB')
