#!/bin/bash
PAYLOAD="$1"

if [ -z "$PAYLOAD" ]; then
  echo "Usage: $0 /path/to/payload"
  exit 1
fi

echo "[*] Running payload: $PAYLOAD"

# Optional: kill existing gadgets
if [ -f /usr/bin/gadget-cleanup ]; then
  /usr/bin/gadget-cleanup
fi

# Execute the payload
chmod +x "$PAYLOAD"
"$PAYLOAD"
