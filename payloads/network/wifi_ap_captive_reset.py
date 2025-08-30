#!/usr/bin/env python3
import subprocess, os, sys, time

IFACE = os.environ.get("IFACE","wlan0")
CIDR  = os.environ.get("AP_CIDR","10.99.0.1/24")

def sh(cmd): return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def main():
    # Stop our AP payload if running
    sh("/opt/p4wnp1/p4wnctl.py payload stop wifi_ap_captive_apache || true")
    # Kill stray procs
    sh("pkill -f 'dnsmasq --no-daemon' || true")
    sh("pkill -f '^hostapd(\\s|$)' || true")
    # Flush iptables and reset IF
    sh("iptables-nft -t nat -F || true")
    sh("iptables-nft -F || true")
    sh(f"ip addr flush dev {IFACE} || true")
    sh(f"ip link set {IFACE} down || true")
    sh("rfkill unblock all || true")
    sh("iw reg set ES || true")
    sh(f"iw dev {IFACE} set type __ap || true")
    sh(f"ip addr add {CIDR} dev {IFACE}")
    sh(f"ip link set {IFACE} up")
    # Restart Apache (vhost uses /var/www/html)
    sh("systemctl restart apache2")
    # Start AP payload again
    rc = sh("/opt/p4wnp1/p4wnctl.py payload run wifi_ap_captive_apache").returncode
    print("[+] AP reset issued")
    return rc

if __name__ == "__main__":
    sys.exit(main())
