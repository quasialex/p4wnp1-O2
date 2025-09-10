#!/usr/bin/env python3
import sys, os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from modules.usb import templates as tmpl  # noqa: E402

def main():
    if len(sys.argv) < 2:
        print("Usage: p4wnp1-apply-template.py <template_name>")
        sys.exit(1)
    name = sys.argv[1]
    state = tmpl.apply(name, auto_bind=True)
    print(f"Applied '{name}'. State: {state}")

if __name__ == "__main__":
    main()

