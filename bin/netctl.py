#!/usr/bin/env python3
import sys, subprocess, os
from pathlib import Path

def sh(cmd): return subprocess.run(["bash","-lc",cmd], check=False)

def set_static_usb0():
    sh("ip link add usb0 type dummy 2>/dev/null || true")  # in case not present yet
    sh("ip addr flush dev usb0 || true")
    sh("ip addr add 10.99.0.1/24 dev usb0 || true")
    sh("ip link set usb0 up || true")

def set_nat(out_iface="wlan0"):
    # enable forwarding
    Path("/proc/sys/net/ipv4/ip_forward").write_text("1")
    # nft rules via service
    sh("systemctl enable --now p4wnp1-nft.service")

def dnsmasq_start(iface="usb0"):
    sh(f"systemctl enable --now p4wnp1-dnsmasq@{iface}.service")

def dnsmasq_stop(iface="usb0"):
    sh(f"systemctl disable --now p4wnp1-dnsmasq@{iface}.service")

def main():
    if len(sys.argv)<2:
        print("Usage: netctl.py [usb0-static|dnsmasq-start|dnsmasq-stop|nat-on]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd=="usb0-static": set_static_usb0()
    elif cmd=="dnsmasq-start": dnsmasq_start()
    elif cmd=="dnsmasq-stop": dnsmasq_stop()
    elif cmd=="nat-on": set_nat()
    else: print("unknown")

if __name__=="__main__":
    main()

