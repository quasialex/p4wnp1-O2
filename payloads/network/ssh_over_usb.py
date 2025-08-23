#!/usr/bin/env python3
import os, sys, subprocess, time

def sh(cmd): return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def main():
    # allow sshd to start; most distros already have it
    sh("systemctl enable --now ssh || systemctl enable --now sshd || true")
    # ensure usb0 has IP (your p4wnctl does this too)
    sh("ip -4 addr show usb0 | grep -q 'inet ' || ip addr add 10.13.37.1/24 dev usb0 || true")
    sh("ip link set usb0 up || true")
    print("[+] SSH reachable on usb0 if host sets 10.13.37.x or via DHCP when RNDIS/ECM up.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
