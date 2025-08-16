# File: payloads/network/wifi_ap.py
import subprocess

print("[*] Starting rogue WiFi access point...")
subprocess.run([
    "nmcli", "dev", "wifi", "hotspot",
    "ifname", "wlan0",
    "ssid", "Free_Public_WiFi",
    "password", ""
])

