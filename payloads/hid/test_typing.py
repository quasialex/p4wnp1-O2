#!/usr/bin/env python3
import os, sys, time
P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))

from hid_type import type_string

print("[*] Typing test payload...")
type_string("Hello from P4wnP1!\n", rdelay=0.02)
time.sleep(0.2)
type_string("This is a test typing payload.\n", rdelay=0.02)
print("[*] Done.")
