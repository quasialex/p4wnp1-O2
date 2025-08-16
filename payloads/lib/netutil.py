# payloads/lib/netutil.py
import json
import os
import socket
import subprocess
from typing import Dict, List, Optional

def _ip_json():
    try:
        out = subprocess.check_output(["/sbin/ip", "-json", "addr", "show"]).decode()
        return json.loads(out)
    except Exception:
        return []

def ips_by_iface() -> Dict[str, List[str]]:
    data = _ip_json()
    ips: Dict[str, List[str]] = {}
    for link in data:
        ifname = link.get("ifname")
        for a in link.get("addr_info", []):
            if a.get("family") == "inet":
                ips.setdefault(ifname, []).append(a.get("local"))
    return ips

def primary_ip(order=("usb0","eth0","wlan0")) -> str:
    ips = ips_by_iface()
    for want in order:
        if want in ips and ips[want]:
            return ips[want][0]
    for k, v in ips.items():
        if k.startswith("enx") and v:
            return v[0]
    for v in ips.values():
        if v:
            return v[0]
    # default-route trick
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass
    # last-resort env
    return os.environ.get("P4WN_LHOST", "10.13.37.1")

def primary_iface(order=("usb0","eth0","wlan0")) -> Optional[str]:
    ips = ips_by_iface()
    for want in order:
        if want in ips and ips[want]:
            return want
    for k, v in ips.items():
        if k.startswith("enx") and v:
            return k
    for k, v in ips.items():
        if v:
            return k
    return None
