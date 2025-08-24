#!/usr/bin/env python3
import os, sys, subprocess
from pathlib import Path

IFACE = os.environ.get("RESP_IFACE", "wlan0")

def main():
    cmd = "/usr/bin/responder" if Path("/usr/bin/responder").exists() else None
    if not cmd:
        # try module
        cmd = "python3 -m Responder"
    args = f"{cmd} -I {IFACE} -wd"
    print(f"[+] Starting Responder on {IFACE}")
    p = subprocess.Popen(args, shell=True)
    p.wait()
    return p.returncode

if __name__ == "__main__":
    sys.exit(main())
