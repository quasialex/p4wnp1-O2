#!/usr/bin/env python3
"""
OLED Menu UI (stub): Navigate payloads using joystick
- Up/Down = scroll
- Press = run payload
"""

import os
import time

# Placeholder for OLED and joystick logic (to be added when hardware arrives)
PAYLOADS = [
    ("Rogue DHCP + DNS", "/opt/p4wnp1/payloads/network/rogue_dhcp_dns.sh"),
    ("Evil AP Stealer", "/opt/p4wnp1/payloads/network/wifi_ap_stealer.sh"),
    ("Responder Attack", "/opt/p4wnp1/payloads/network/responder_attack.sh"),
    ("Reverse Shell", "/opt/p4wnp1/payloads/network/reverse_shell_tunnel.sh"),
    ("LockPicker (HID)", "/opt/p4wnp1/payloads/windows/lockpicker.sh"),
    ("SSLStrip Phishing", "/opt/p4wnp1/payloads/network/sslstrip_phishing.sh"),
]

cursor = 0

def display_menu():
    os.system("clear")
    print("=== P4wnP1 Payload Menu ===\n")
    for i, (name, _) in enumerate(PAYLOADS):
        if i == cursor:
            print(f"> {name}")
        else:
            print(f"  {name}")
    print("\n[UP/DOWN = Navigate | ENTER = Run | Q = Quit]")

def run_payload(index):
    name, path = PAYLOADS[index]
    print(f"\n[*] Running: {name}")
    os.system(f"bash {path}")
    input("\n[✓] Press Enter to return to menu...")

# TEMP: keyboard interface while OLED+joystick is not wired
while True:
    display_menu()
    key = input().lower()
    if key == "q":
        break
    elif key == "":
        run_payload(cursor)
    elif key == "w":
        cursor = (cursor - 1) % len(PAYLOADS)
    elif key == "s":
        cursor = (cursor + 1) % len(PAYLOADS)
