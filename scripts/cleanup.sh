#!/bin/bash
# Description: Stops all rogue payload services (hostapd, dnsmasq, sslstrip, etc.)

set -euo pipefail

echo "[*] Cleaning up rogue services..."

# === Kill known rogue processes ===
for PROC in hostapd dnsmasq sslstrip Responder.py "python3 -m http.server" socat ettercap; do
  pkill -f "$PROC" || true
done

# === Restore iptables and sysctl (for sslstrip payload) ===
iptables -t nat -F
echo 0 > /proc/sys/net/ipv4/ip_forward

echo "[✓] All rogue payload services stopped."
