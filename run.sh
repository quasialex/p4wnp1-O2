#!/bin/bash
set -euo pipefail

# === Config ===
# Allow overriding the project location via P4WN_HOME
P4WN_HOME="${P4WN_HOME:-/opt/p4wnp1}"
ACTIVE_PAYLOAD="$P4WN_HOME/config/active_payload"
PAYLOADS_DIR="$P4WN_HOME/payloads"
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

# === Read active payload ===
if [[ ! -f "$ACTIVE_PAYLOAD" ]]; then
  echo "[!] No active payload file found at $ACTIVE_PAYLOAD"
  exit 1
fi

PAYLOAD_ID=$(cat "$ACTIVE_PAYLOAD")
PAYLOAD_PATH="$PAYLOADS_DIR/$PAYLOAD_ID"

# === Run payload ===
if [[ -x "$PAYLOAD_PATH" ]]; then
  echo "[+] Executing payload: $PAYLOAD_ID"
  "$PAYLOAD_PATH"
else
  echo "[!] Payload not found or not executable: $PAYLOAD_PATH"
  exit 1
fi
