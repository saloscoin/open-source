#!/bin/bash
# Start SALOCOIN Mining Pool

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

# Check for required arguments
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: $0 <pool_address> <pool_privkey> [fee_percent]"
    echo "Example: $0 SaQqrhj6WZXS3MRqWFA4dLELAvdxRUh6wV L1osABQ... 1.0"
    exit 1
fi

POOL_ADDRESS="$1"
POOL_PRIVKEY="$2"
FEE="${3:-1.0}"

echo "Starting SALOCOIN Pool..."
echo "Address: $POOL_ADDRESS"
echo "Fee: $FEE%"

python3 -m pool.pool_server \
    --address "$POOL_ADDRESS" \
    --privkey "$POOL_PRIVKEY" \
    --fee "$FEE" \
    --port 7261 \
    --http 7262
