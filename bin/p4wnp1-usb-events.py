#!/usr/bin/env python3
# /opt/p4wnp1/bin/p4wnp1-usb-events.py
# USB attach/detach watcher with repo-path bootstrap.
import argparse
import sys
from pathlib import Path

# --- repo path bootstrap ---
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.usb.events import watch  # noqa: E402

def main():
    ap = argparse.ArgumentParser(description="P4wnP1-O2 USB attach/detach watcher")
    ap.add_argument("--gadget", default="p4wnp1", help="Gadget name (default: p4wnp1)")
    ap.add_argument("--interval", type=float, default=0.5, help="Poll interval seconds")
    args = ap.parse_args()
    watch(gadget_name=args.gadget, poll_interval=args.interval)

if __name__ == "__main__":
    main()

