#!/usr/bin/env python3
"""OLED “SHOW IP” menu item for P4wnP1 O2

Displays the current Wi‑Fi and/or USB (RNDIS/ECM) IPv4 address on the 128 × 64 OLED.
Dependencies: ``pip3 install netifaces luma.oled`` (already present on most images).

"""
import json
import os
import time
from textwrap import shorten

import netifaces
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106  # same driver used by existing menu

P4WN_HOME = os.getenv("P4WN_HOME", "/opt/p4wnp1")
CFG_FILE = os.path.join(P4WN_HOME, "config/ip_interfaces.json")

_cached_ifaces = None
_cache_time = 0

def load_interfaces():
    global _cached_ifaces, _cache_time
    now = time.time()
    if _cached_ifaces is None or now - _cache_time > 1:
        try:
            with open(CFG_FILE) as f:
                _cached_ifaces = json.load(f)
        except Exception:
            _cached_ifaces = {
                "Wi-Fi": ["wlan*"],
                "USB/Victim": ["usb*", "eth*", "enx*"]
            }
        _cache_time = now
    return _cached_ifaces


_ip_cache = {}
_ip_time = 0

def first_ip(iface_patterns):
    """Return the first IPv4 address found for any interface matching patterns."""
    global _ip_cache, _ip_time
    now = time.time()
    key = tuple(iface_patterns)
    if key in _ip_cache and now - _ip_time < 1:
        return _ip_cache[key]
    for pattern in iface_patterns:
        if pattern.endswith("*") or len(pattern) == 3:
            candidates = [i for i in netifaces.interfaces() if i.startswith(pattern.rstrip("*"))]
        else:
            candidates = [pattern]
        for iface in candidates:
            try:
                ip = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]["addr"]
                _ip_cache[key] = ip
                _ip_time = now
                return ip
            except (KeyError, ValueError):
                continue
    _ip_cache[key] = None
    _ip_time = now
    return None


def build_lines(max_chars=16):
    lines = []
    ifaces = load_interfaces()
    wifi_ip = first_ip(ifaces.get("Wi-Fi", []))
    usb_ip = first_ip(ifaces.get("USB/Victim", []))

    if wifi_ip:
        lines.append(f"WiFi IP: {wifi_ip}")
    if usb_ip and usb_ip != wifi_ip:
        lines.append(f"USB IP: {usb_ip}")
    if not lines:
        lines.append("No IP addr")

    return [shorten(l, max_chars, placeholder="…") for l in lines]


def main():
    serial = i2c(port=1, address=0x3C)
    device = sh1106(serial, width=128, height=64)

    with canvas(device) as draw:
        y = 0
        for line in build_lines():
            draw.text((0, y), line, fill=255)
            y += 10  # 10‑pixel line height matches default 6×8 font


if __name__ == "__main__":
    main()
