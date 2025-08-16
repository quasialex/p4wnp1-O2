#!/usr/bin/env python3

import subprocess
import time

def start_revshell_listener(port=4444):
    try:
        print(f"[+] Starting reverse shell listener on port {port} (CTRL+C to stop)...")
        subprocess.run(["nc", "-nlvp", str(port)])
    except KeyboardInterrupt:
        print("\n[!] Listener stopped.")

if __name__ == "__main__":
    start_revshell_listener()
