#!/usr/bin/env python3
import os, sys, time, base64
P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from hid_type import win_r, type_string

def ps_b64(s: str) -> str:
    import base64
    return base64.b64encode(s.encode("utf-16le")).decode()

def main():
    # Friendly note; replace with your own flow if you have a pre-staged helper
    ps = r"[System.Windows.MessageBox]::Show('HID active. No SAS bypass (Ctrl+Alt+Del) via USB HID.','P4wnP1-O2')"
    b64 = ps_b64(ps)
    win_r(); time.sleep(0.35)
    type_string(f"powershell -NoP -W Hidden -Enc {b64}\n", rdelay=0.02)
    print("[*] Lockpicker placeholder executed.")

if __name__ == "__main__":
    main()

