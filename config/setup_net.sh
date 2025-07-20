#!/bin/bash
set -euo pipefail

echo "[*] Configuring usb0 static IP..."

IFACE="usb0"
IP="10.0.0.1/24"

ip link set "$IFACE" up
ip addr flush dev "$IFACE" || true
ip addr add "$IP" dev "$IFACE"

echo "[+] usb0 now has IP $IP"
