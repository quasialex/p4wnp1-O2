#!/bin/bash
# Send keystrokes over USB HID using /dev/hidg0

HID_DEVICE="/dev/hidg0"
SCRIPT="$1"
DELAY=0.1

if [[ -z "$SCRIPT" || ! -f "$SCRIPT" ]]; then
  echo "Usage: $0 path/to/hid_script.txt"
  exit 1
fi

if [[ ! -e "$HID_DEVICE" ]]; then
  echo "[!] HID device $HID_DEVICE not found"
  exit 1
fi

while read -r line; do
  [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
  echo "[>] $line"
  python3 /opt/p4wnp1/tools/hid_type.py "$line" > "$HID_DEVICE"
  sleep $DELAY
done < "$SCRIPT"
