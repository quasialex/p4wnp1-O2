#!/usr/bin/env python3
import os, subprocess, sys, time, shlex

P4WNCTL = "/opt/p4wnp1/p4wnctl.py"
UPLINK = os.environ.get("UPLINK", "wlan0")

def sh(cmd):
    print(f"[pivot] $ {cmd}", flush=True)
    return subprocess.run(cmd, shell=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

def main():
    # Start DHCP on usb0
    out = sh(f"{P4WNCTL} net dhcp start usb0")
    sys.stdout.write(out.stdout)

    # Enable NAT usb0 -> uplink
    out = sh(f"{P4WNCTL} net share {shlex.quote(UPLINK)}")
    sys.stdout.write(out.stdout)

    # Print quick status
    sh(f"{P4WNCTL} net status")
    print(f"[pivot] usb0 is shared via uplink '{UPLINK}'. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(300)
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    sys.exit(main())
