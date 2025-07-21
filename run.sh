#!/bin/bash
set -euo pipefail

# === Config ===
# Allow overriding the project location via P4WN_HOME
P4WN_HOME="${P4WN_HOME:-/opt/p4wnp1}"
ACTIVE_FILE="$P4WN_HOME/config/active_payload"
PAYLOADS_JSON="$P4WN_HOME/config/payload.json"
LOG="$P4WN_HOME/logs/runner.log"

mkdir -p "$(dirname "$LOG")"

# === Logging ===
exec > >(tee -a "$LOG") 2>&1

echo "[*] Starting run.sh at $(date)"

# === Setup USB gadget and networking ===
echo "[*] Setting up USB gadget..."
bash "$P4WN_HOME/config/usb_gadget.sh"
sleep 1

echo "[*] Setting up networking..."
bash "$P4WN_HOME/config/setup_net.sh"
sleep 1

# Ensure jq is available for reading payload config
if ! command -v jq >/dev/null 2>&1; then
  echo "[!] jq command not found. Please install jq." >&2
  exit 1
fi

# === Read active payload ===
if [[ ! -f "$ACTIVE_FILE" ]]; then
  echo "[!] No active payload file found at $ACTIVE_FILE"
  exit 1
fi

PAYLOAD_ID=$(cat "$ACTIVE_FILE")
PAYLOAD_PATH=$(jq -r --arg id "$PAYLOAD_ID" '.[$id].path' "$PAYLOADS_JSON")

if [[ -z "$PAYLOAD_PATH" || "$PAYLOAD_PATH" == "null" ]]; then
  echo "[!] Payload '$PAYLOAD_ID' not found in config $PAYLOADS_JSON"
  exit 1
fi

FULL_PATH="$P4WN_HOME/$PAYLOAD_PATH"

# === Run payload ===
if [[ -x "$FULL_PATH" ]]; then
  echo "[+] Executing payload: $PAYLOAD_ID -> $FULL_PATH"
  "$FULL_PATH"
else
  echo "[!] Payload not found or not executable: $FULL_PATH"
  exit 1
fi
