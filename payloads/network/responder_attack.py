#!/usr/bin/env python3
import os, sys, subprocess
from pathlib import Path

def sh(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def detect_iface():
    # let p4wnctl export P4WN_NET_IFACE; fallback try usb0->wlan0->eth0
    env = os.environ.get("P4WN_NET_IFACE")
    if env: return env
    for c in ("usb0","wlan0","eth0"):
        out = sh(f"ip -4 addr show {c}").stdout
        if "inet " in out: return c
    return "usb0"

def main():
    iface = detect_iface()
    # prefer installed responder; if not, try python -m Responder
    if Path("/usr/bin/responder").exists():
        cmd = f"/usr/bin/responder -I {iface} -wd"
    else:
        cmd = f"/usr/bin/env python3 -m Responder -I {iface} -wd"
    print(f"[+] Starting Responder on {iface}")
    # Run in foreground (systemd-run already wraps us)
    p = subprocess.Popen(cmd, shell=True)
    p.wait()
    return p.returncode

if __name__ == "__main__":
    sys.exit(main())
