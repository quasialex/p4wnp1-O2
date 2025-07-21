#!/bin/bash

P4WN_HOME="${P4WN_HOME:-/opt/p4wnp1}"
CFG="$P4WN_HOME/config/payload.json"

# List enabled payload IDs from payload.json
PAYLOADS=$(jq -r 'keys[] as $k | select(.[$k].enabled == true) | $k' "$CFG")

echo "Available payloads:"
printf '%s\n' "$PAYLOADS"
echo
read -p "Enter the payload ID to activate: " NEW

# Validate that the ID exists
if jq -e --arg id "$NEW" '.[$id]?' "$CFG" >/dev/null; then
  echo "$NEW" > "$P4WN_HOME/config/active_payload"
  echo "Active payload updated to: $NEW"
else
  echo "Invalid selection. No changes made."
fi
