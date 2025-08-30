#!/usr/bin/env python3
import os, sys, time, subprocess

P4WN = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
CTL  = os.path.join(P4WN, "p4wnctl.py")
UPLINK = os.environ.get("UPLINK", "wlan0")

def sh(cmd):
    return subprocess.call(cmd, shell=True)

def main():
    # Start DHCP on usb0 and NAT toward $UPLINK (uses your net helpers)
    sh(f"{CTL} net dhcp start")
    sh(f"{CTL} net share {UPLINK}")

    print(f"[relay_usb_to_wlan] running (usb0 -> {UPLINK}). Ctrl+C to exit.")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    sys.exit(main())
