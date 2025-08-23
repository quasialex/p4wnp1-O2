#!/usr/bin/env python3
import subprocess, time, os, textwrap

IFACE = os.getenv("IFACE","wlan0")
GW    = os.getenv("GW","10.20.0.1/24")
SSID  = os.getenv("SSID","FreeWifi")
CHAN  = os.getenv("CHAN","6")

HOSTAPD = f"""\
interface={IFACE}
ssid={SSID}
hw_mode=g
channel={CHAN}
auth_algs=1
wmm_enabled=0
"""

DNSMASQ = f"""\
interface={IFACE}
bind-interfaces
dhcp-range=10.20.0.10,10.20.0.100,12h
dhcp-option=3,10.20.0.1
dhcp-option=6,10.20.0.1
address=/#/10.20.0.1
log-queries
"""

def main():
    subprocess.run(["pkill","-f","hostapd"], check=False)
    subprocess.run(["pkill","-f","dnsmasq"], check=False)

    subprocess.run(["ip","link","set",IFACE,"up"], check=True)
    subprocess.run(["ip","addr","flush","dev",IFACE], check=False)
    subprocess.run(["ip","addr","add",GW,"dev",IFACE], check=True)

    open("/run/p4w-hostapd.conf","w").write(HOSTAPD)
    open("/run/p4w-dnsmasq.conf","w").write(DNSMASQ)

    subprocess.Popen(["hostapd","/run/p4w-hostapd.conf"])
    time.sleep(1.5)
    subprocess.Popen(["dnsmasq","--keep-in-foreground","--conf-file=/run/p4w-dnsmasq.conf"])
    print(f"[+] AP up on {IFACE} SSID={SSID} captive DNS={GW.split('/')[0]}")

if __name__=="__main__":
    main()
