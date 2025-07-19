#!/bin/bash

# List enabled payloads from payload.json
jq -r 'to_entries[] | select(.value.enabled == true) | "\(.key): \(.value.name)"' /opt/p4wnp1/config/payload.json

echo ""
echo "Enter the payload path to activate (e.g., hid/test_typing.sh):"
read NEW

# Validate
if [[ -x /opt/p4wnp1/payloads/$NEW ]]; then
  echo "$NEW" > /opt/p4wnp1/config/active_payload
  echo "Active payload updated to: $NEW"
else
  echo "Invalid selection. No changes made."
fi
