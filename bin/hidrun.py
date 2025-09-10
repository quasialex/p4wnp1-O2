#!/usr/bin/env python3
import sys, os, time
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from modules.hid.runtime import run_file  # noqa

def wait_for(path, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        if Path(path).exists():
            return True
        time.sleep(0.2)
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: hidrun.py <script.hid>")
        sys.exit(1)
    if not wait_for("/dev/hidg0", 15.0):
        print("HID device /dev/hidg0 not present. Apply a HID template and plug into a host first.")
        sys.exit(2)
    run_file(sys.argv[1])

