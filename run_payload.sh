#!/bin/bash
# Executes the payload selected in active_payload file

P4WN_HOME="${P4WN_HOME:-/opt/p4wnp1}"
CONFIG="$P4WN_HOME/config/payload.json"
ACTIVE="$P4WN_HOME/config/active_payload"

if [ ! -f "$ACTIVE" ]; then
  echo "[!] No active payload set."
  exit 1
fi

PAYLOAD_ID=$(cat "$ACTIVE")
PAYLOAD_PATH=$(jq -r --arg id "$PAYLOAD_ID" '.[$id].path' "$CONFIG")

if [ -z "$PAYLOAD_PATH" ] || [ "$PAYLOAD_PATH" == "null" ]; then
  echo "[!] Payload '$PAYLOAD_ID' not found in config."
  exit 1
fi

FULL_PATH="$P4WN_HOME/$PAYLOAD_PATH"
echo "[+] Running payload: $PAYLOAD_ID -> $FULL_PATH"
chmod +x "$FULL_PATH"
"$FULL_PATH"
