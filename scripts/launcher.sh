#!/bin/bash
# Description: Interactive payload launcher

set -euo pipefail

PAYLOAD_DIR="/opt/p4wnp1/payloads/network"
LOG="/opt/p4wnp1/logs/launcher.log"

mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

echo "[*] P4wnP1 Payload Launcher"
echo "Select a payload to run:"
select opt in $(ls "$PAYLOAD_DIR"/*.sh | xargs -n1 basename); do
    echo "[*] Executing: $opt"
    "$PAYLOAD_DIR/$opt"
    break
done
