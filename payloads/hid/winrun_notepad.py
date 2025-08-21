#!/usr/bin/env python3
import os, sys, time
P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))

from hid_type import win_r, type_string

print("[*] Launching Notepad via Win+R ...")
win_r()
time.sleep(0.35)  # time to open Run dialog
type_string("notepad\n", rdelay=0.02)

# Give Notepad time to start and take focus
time.sleep(0.9)   # adjust to 1.2–1.5s for slower VMs

print("[*] Typing into Notepad ...")
type_string("Hello from P4wnP1!\n", rdelay=0.02)
type_string("If you can read this, HID is working.\n", rdelay=0.02)
print("[*] Done.")
