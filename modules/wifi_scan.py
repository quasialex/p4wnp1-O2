# wifi_scan.py
import subprocess, sys
from pathlib import Path

def register(subparsers):
    p = subparsers.add_parser("wifi", help="Wi‑Fi helpers")
    ss = p.add_subparsers(dest="wifi_cmd")
    scan = ss.add_parser("scan", help="Quick scan on wlan0 (nmcli)")
    scan.add_argument("--iface", default="wlan0")

def handle(args):
    if args.wifi_cmd == "scan":
        iface = getattr(args, "iface", "wlan0")
        cmd = ["nmcli", "-t", "-f", "ssid,bssid,chan,rate,signal,security", "device", "wifi", "list", "ifname", iface]
        cp = subprocess.run(cmd, text=True)
        return cp.returncode
    return 1
