#!/bin/bash
set -euo pipefail

LOG="/opt/p4wnp1/logs/http_server.log"
cd /opt/p4wnp1/www
exec > >(tee -a "$LOG") 2>&1

echo "[*] Starting HTTP server at $(date)"
python3 -m http.server 80
