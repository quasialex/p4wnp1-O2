#!/bin/bash

P4WN_HOME="${P4WN_HOME:-/opt/p4wnp1}"
CONFIG="$P4WN_HOME/config/reverse_shell.conf"
[ -f "$CONFIG" ] && source "$CONFIG"

PORT="${RS_PORT:-4444}"
echo "[*] Listening on TCP port $PORT..."
nc -lvnp "$PORT"
