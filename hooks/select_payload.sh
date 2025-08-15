#!/bin/bash
set -euo pipefail
BASE=/opt/p4wnp1
CFG="$BASE/config/active_payload"

usage(){ echo "Usage: $0 <payload_name>"; exit 1; }
[[ $# -eq 1 ]] || usage
NAME="$1"

# Resolve payload path (supports nested categories like hid/<name>.sh)
CANDIDATES=(
  "$BASE/payloads/$NAME.sh"
  "$BASE/payloads/hid/$NAME.sh"
  "$BASE/payloads/net/$NAME.sh"
)
PAYLOAD=""
for p in "${CANDIDATES[@]}"; do
  if [[ -f "$p" ]]; then PAYLOAD="$p"; break; fi
done

if [[ -z "$PAYLOAD" ]]; then
  echo "✗ payload not found: $NAME"
  exit 2
fi

echo "$PAYLOAD" > "$CFG"
chmod 644 "$CFG"

echo "✓ active payload set:"
echo "  $(cat "$CFG")"
