#!/usr/bin/env python3
"""OLED “SHOW IP” menu item for P4wnP1 O2

Displays the current Wi‑Fi and/or USB (RNDIS/ECM) IPv4 address on the 128 × 64 OLED.
Dependencies: ``pip3 install netifaces luma.oled`` (already present on most images).

"""
import netifaces
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106   # same driver used by existing menu
from luma.core.render import canvas
from textwrap import shorten


INTERFACES = {
    "Wi‑Fi": ["wlan0", "wlan1"],
    "USB/Victim": ["usb0", "eth0", "eth1", "enx"],  # enx* covers random‑MAC gadget names
}


def first_ip(iface_patterns):
    """Return the first IPv4 address found for any interface matching patterns."""
    for pattern in iface_patterns:
        # prefix match if pattern ends with * or looks like 'enx'
        if pattern.endswith("*") or len(pattern) == 3:
            candidates = [i for i in netifaces.interfaces() if i.startswith(pattern.rstrip("*"))]
        else:
            candidates = [pattern]
        for iface in candidates:
            try:
                return netifaces.ifaddresses(iface)[netifaces.AF_INET][0]["addr"]
            except (KeyError, ValueError):
                continue
    return None


def build_lines(max_chars=16):
    lines = []
    wifi_ip = first_ip(INTERFACES["Wi‑Fi"])
    usb_ip = first_ip(INTERFACES["USB/Victim"])

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
