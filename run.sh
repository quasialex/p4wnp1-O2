#!/bin/bash

# Set up USB gadgets and networking
/opt/p4wnp1/config/usb_gadget.sh
sleep 2
/opt/p4wnp1/config/setup_net.sh
sleep 2

# Load active payload path
PAYLOAD_PATH=$(cat /opt/p4wnp1/config/active_payload)

# Execute if it exists
if [[ -x /opt/p4wnp1/payloads/$PAYLOAD_PATH ]]; then
    echo "Executing: $PAYLOAD_PATH"
    /opt/p4wnp1/payloads/$PAYLOAD_PATH
else
    echo "No valid payload: $PAYLOAD_PATH"
fi
