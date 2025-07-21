#!/bin/bash

CONFIG="/opt/p4wnp1-o2/config/reverse_shell.conf"
[ -f "$CONFIG" ] && source "$CONFIG"

PORT="${RS_PORT:-4444}"
echo "[*] Listening on TCP port $PORT..."
nc -lvnp "$PORT"
