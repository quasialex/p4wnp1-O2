# File: payloads/network/mass_storage.py
import subprocess

print("[*] Mounting mass storage gadget with loot.img...")
subprocess.run([
    "modprobe", "g_mass_storage",
    "file=/opt/p4wnp1/loot/loot.img",
    "removable=1",
    "ro=0"
])
