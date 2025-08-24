#!/usr/bin/env python3
import os, subprocess, sys

IFACE = os.environ.get("IFACE", "wlan0")

def sh(cmd): return subprocess.run(cmd, shell=True, text=True, capture_output=True)
def have(cmd): return subprocess.run(f"command -v {cmd}", shell=True, text=True, capture_output=True).returncode == 0

def main():
    sh("pkill -f 'dnsmasq --no-daemon' || true")
    sh("pkill -f 'hostapd' || true")
    sh("iptables-nft -t nat -F || true")
    sh("iptables-nft -F || true")
    sh(f"ip addr flush dev {IFACE} || true")
    sh(f"ip link set {IFACE} down || true")
    if have("nmcli"):
        sh(f"nmcli dev set {IFACE} managed yes")
    sh("systemctl restart NetworkManager 2>/dev/null || true")
    print("[+] AP stopped; wlan0 returned to NetworkManager.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
