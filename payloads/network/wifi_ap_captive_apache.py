#!/usr/bin/env python3
import os, sys, subprocess, time, shlex
from pathlib import Path

IFACE   = os.environ.get("IFACE", "wlan0")
SSID    = os.environ.get("AP_SSID", "P4wnP1_O2")
PSK     = os.environ.get("AP_PSK",  "P4wnIsHere!")
CIDR    = os.environ.get("AP_CIDR", "10.99.0.1/24")
SUBNET  = os.environ.get("AP_SUBNET", "10.99.0.0/24")
RANGE_S = os.environ.get("AP_RANGE_START", "10.99.0.50")
RANGE_E = os.environ.get("AP_RANGE_END",   "10.99.0.150")

def sh(cmd, check=True):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True, check=check)

def main():
    os.environ.setdefault("DEBIAN_FRONTEND", "noninteractive")
    sh("apt-get update -y", check=False)
    sh("apt-get install -y --no-install-recommends hostapd dnsmasq iptables-nft", check=False)

    # Unmask hostapd (Kali default is masked)
    sh("systemctl unmask hostapd", check=False)
    sh("systemctl stop hostapd dnsmasq", check=False)

    # Bring IFACE up with our IP
    sh(f"ip link set {IFACE} down || true", check=False)
    sh(f"ip addr flush dev {IFACE} || true", check=False)
    sh(f"ip addr add {CIDR} dev {IFACE}", check=False)
    sh(f"ip link set {IFACE} up", check=False)

    # hostapd.conf
    Path("/etc/hostapd").mkdir(parents=True, exist_ok=True)
    Path("/etc/hostapd/hostapd.conf").write_text(
        f"interface={IFACE}\n"
        "driver=nl80211\n"
        f"ssid={SSID}\n"
        "hw_mode=g\n"
        "channel=6\n"
        "wmm_enabled=0\n"
        "auth_algs=1\n"
        "wpa=2\n"
        f"wpa_passphrase={PSK}\n"
        "wpa_key_mgmt=WPA-PSK\n"
        "rsn_pairwise=CCMP\n",
        encoding="utf-8"
    )
    # ensure DAEMON_CONF points to our file
    sh("sed -i 's|^#\\?DAEMON_CONF=.*|DAEMON_CONF=\"/etc/hostapd/hostapd.conf\"|' /etc/default/hostapd", check=False)

    # dnsmasq captive config
    Path("/etc/dnsmasq.d").mkdir(parents=True, exist_ok=True)
    Path("/etc/dnsmasq.d/p4wnp1-ap.conf").write_text(
        f"interface={IFACE}\n"
        "bind-interfaces\n"
        f"dhcp-range={RANGE_S},{RANGE_E},12h\n"
        "domain-needed\n"
        "bogus-priv\n"
        f"listen-address=127.0.0.1,{CIDR.split('/')[0]}\n"
        f"address=/#/{CIDR.split('/')[0]}\n"
        f"dhcp-option=3,{CIDR.split('/')[0]}\n"
        f"dhcp-option=6,{CIDR.split('/')[0]}\n",
        encoding="utf-8"
    )
    # Clean any default dnsmasq snippets that conflict
    try: Path("/etc/dnsmasq.d/README").unlink()
    except FileNotFoundError: pass

    # Enable forwarding and captive redirect to local Apache
    sh("sysctl -w net.ipv4.ip_forward=1", check=False)
    sh("sed -i 's/^#\\?net.ipv4.ip_forward=.*/net.ipv4.ip_forward=1/' /etc/sysctl.conf", check=False)

    # nft-based iptables on Kali
    sh("iptables-nft -t nat -F || true", check=False)
    sh("iptables-nft -F || true", check=False)
    # redirect HTTP from clients to local 80
    sh(f"iptables-nft -t nat -A PREROUTING -i {IFACE} -p tcp --dport 80 -j REDIRECT --to-ports 80", check=False)
    # optional SNAT/MASQ if you later add upstream NAT
    sh(f"iptables-nft -t nat -A POSTROUTING -s {SUBNET} -j MASQUERADE || true", check=False)

    # restart services
    sh("systemctl restart dnsmasq", check=False)
    sh("systemctl restart hostapd", check=False)
    sh("systemctl restart apache2", check=False)

    print(f"[+] AP up on {IFACE}, SSID={SSID}. Clients see Apache captive portal.")
    # keep unit alive; `payload stop` will stop this process and systemd will clean up
    while True:
        time.sleep(60)

if __name__ == "__main__":
    sys.exit(main())
