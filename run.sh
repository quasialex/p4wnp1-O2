#!/bin/bash
/opt/p4wnp1/config/usb_gadget.sh
sleep 2
/opt/p4wnp1/config/setup_net.sh
sleep 2

# Read and run selected payload
PAYLOAD=$(cat /opt/p4wnp1/config/active_payload)
bash /opt/p4wnp1/payloads/$PAYLOAD
