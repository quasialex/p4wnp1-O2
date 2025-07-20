#!/bin/bash
# Description: Packages the full payload directory, excluding logs and backups

set -euo pipefail

DATE=$(date +%Y%m%d_%H%M)
OUT="/opt/p4wnp1/builds/p4wnp1_payloads_$DATE.tar.gz"

mkdir -p /opt/p4wnp1/builds

echo "[*] Archiving payloads to $OUT"
tar --exclude='*.log' --exclude='*.bak' -czf "$OUT" /opt/p4wnp1/

echo "[✓] Archive complete."
