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
CCODE   = os.environ.get("AP_COUNTRY", "ES")  # Spain for you

HOSTAPD_CONF = Path("/etc/hostapd/hostapd.conf")
DNSMASQ_CONF = Path("/etc/dnsmasq.d/p4wnp1-ap.conf")

def sh(cmd, check=True):
    cp = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if check and cp.returncode != 0:
        sys.stdout.write(cp.stdout or "")
        sys.stderr.write(cp.stderr or "")
        raise SystemExit(cp.returncode)
    return cp

def have(cmd): return subprocess.run(f"command -v {shlex.quote(cmd)}", shell=True, text=True, capture_output=True).returncode == 0

def ensure_deps():
    os.environ.setdefault("DEBIAN_FRONTEND", "noninteractive")
    sh("apt-get update -y", check=False)
    sh("apt-get install -y --no-install-recommends hostapd dnsmasq iptables-nft wireless-tools", check=False)

def evict_only_wlan0():
    # Ask NM to stop managing wlan0 (USB stays intact)
    if have("nmcli"):
        sh(f"nmcli dev set {IFACE} managed no", check=False)
        # down any active connection on wlan0
        # shell gymnastics to not depend on awk
        sh(f"nmcli -t -f UUID,DEVICE c show --active | grep ':{IFACE}$' | cut -d: -f1 | "
           "xargs -r -I{} nmcli c down uuid {}", check=False)
        # also disconnect device
        sh(f"nmcli dev disconnect {IFACE}", check=False)

    # Try clean shutdown of wpa_supplicant on wlan0, then a precise kill
    if have("wpa_cli"):
        sh(f"wpa_cli -i {IFACE} terminate", check=False)
    sh(f"pkill -f 'wpa_supplicant.*-i *{IFACE}' || true", check=False)

def ensure_iface_ap_type():
    # Bring down, flush, set type __ap, then up
    sh(f"ip link set dev {IFACE} down || true", check=False)
    # switch type to AP explicitly (some brcmfmac builds need this)
    sh(f"iw dev {IFACE} set type __ap", check=False)
    # power save off helps stability
    sh(f"iw dev {IFACE} set power_save off", check=False)
    # assign our IP
    sh(f"ip addr flush dev {IFACE} || true", check=False)
    sh(f"ip addr add {CIDR} dev {IFACE}", check=True)
    sh(f"ip link set dev {IFACE} up", check=True)

def write_hostapd():
    HOSTAPD_CONF.parent.mkdir(parents=True, exist_ok=True)
    HOSTAPD_CONF.write_text(
        f"interface={IFACE}\n"
        "driver=nl80211\n"
        f"country_code={CCODE}\n"
        "ieee80211d=1\n"
        "ieee80211h=1\n"
        f"ssid={SSID}\n"
        "hw_mode=g\n"
        "channel=1\n"
        "ieee80211n=1\n"
        "wmm_enabled=1\n"
        "auth_algs=1\n"
        "wpa=2\n"
        f"wpa_passphrase={PSK}\n"
        "wpa_key_mgmt=WPA-PSK\n"
        "rsn_pairwise=CCMP\n",
        encoding="utf-8"
    )

def write_dnsmasq():
    DNSMASQ_CONF.parent.mkdir(parents=True, exist_ok=True)
    ip = CIDR.split("/")[0]
    DNSMASQ_CONF.write_text(
        f"interface={IFACE}\n"
        "bind-interfaces\n"
        f"dhcp-range={RANGE_S},{RANGE_E},255.255.255.0,12h\n"
        "domain-needed\n"
        "bogus-priv\n"
        f"listen-address=127.0.0.1,{ip}\n"
        f"address=/#/{ip}\n"
        f"dhcp-option=3,{ip}\n"
        f"dhcp-option=6,{ip}\n",
        encoding="utf-8"
    )
    try: Path("/etc/dnsmasq.d/README").unlink()
    except FileNotFoundError: pass

def iptables_captive():
    sh("iptables-nft -t nat -F || true", check=False)
    sh("iptables-nft -F || true", check=False)
    sh(f"iptables-nft -t nat -A PREROUTING -i {IFACE} -p tcp --dport 80 -j REDIRECT --to-ports 80", check=False)
    sh("sysctl -w net.ipv4.ip_forward=1", check=False)

def start_hostapd_dbg():
    # -dd for verbose; run in FG so logs stream to the unit
    return subprocess.Popen(["hostapd", "-dd", str(HOSTAPD_CONF)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

def start_dnsmasq_fg():
    return subprocess.Popen(["dnsmasq", "--no-daemon", f"--conf-file={DNSMASQ_CONF}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

def ensure_apache():
    sh("systemctl restart apache2", check=False)

def main():
    ensure_deps()
    # make sure RF/reg are correct for ES
    sh("rfkill unblock all", check=False)
    sh(f"iw reg set {CCODE}", check=False)

    evict_only_wlan0()
    ensure_iface_ap_type()
    write_hostapd()
    write_dnsmasq()
    iptables_captive()
    ensure_apache()

    print(f"[+] Starting AP on {IFACE} (country={CCODE}) SSID={SSID}. Clients captive to :80.")
    hp = start_hostapd_dbg(); time.sleep(1.0)
    if hp.poll() is not None:
        out = (hp.stdout.read() if hp.stdout else "").strip()
        print(f"[!] hostapd exited early:\n{out}", file=sys.stderr); return 3

    dp = start_dnsmasq_fg(); time.sleep(0.8)
    if dp.poll() is not None:
        out = (dp.stdout.read() if dp.stdout else "").strip()
        print(f"[!] dnsmasq exited early:\n{out}", file=sys.stderr); return 4

    try:
        while True:
            for p, tag in ((hp, "hostapd"), (dp, "dnsmasq")):
                if p.stdout:
                    line = p.stdout.readline()
                    if line:
                        sys.stdout.write(f"[{tag}] {line}")
                        sys.stdout.flush()
            if hp.poll() is not None and dp.poll() is not None:
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in (hp, dp):
            try: p.terminate()
            except Exception: pass
        print("[*] AP payload exiting.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
