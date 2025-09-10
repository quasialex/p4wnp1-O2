#!/usr/bin/env python3
"""
ps_exec: Type a PowerShell command via HID.

Priority:
  1) CLI args after '--' (supports @file to read command text)
  2) $P4WN_PS (also supports @file)
  3) 'notepad' (fallback)
"""

import os
import sys
import time
from pathlib import Path

# Make sure we can import hid_type.py from project root (and legacy /tools)
for p in ("/opt/p4wnp1", "/opt/p4wnp1/tools"):
    if p not in sys.path:
        sys.path.insert(0, p)

from hid_type import hotkey_then_type, press_enter, MOD_GUI, KEY_R  # now resolvable

def _load_maybe_file(s: str) -> str:
    s = s.strip()
    if s.startswith("@"):
        path = Path(s[1:])
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return s
        # flatten to one line for the Run box
        return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").splitlines())
    return s

def _pick_command() -> str:
    if len(sys.argv) > 1:
        body = " ".join(sys.argv[1:]).strip()
        if body:
            return _load_maybe_file(body)
    env_body = os.environ.get("P4WN_PS", "").strip()
    if env_body:
        return _load_maybe_file(env_body)
    return "notepad"

def main() -> int:
    ps_body = _pick_command()
    full = f"powershell -NoProfile -WindowStyle Hidden -Command {ps_body}"

    # Open Run dialog, type, Enter
    hotkey_then_type(
        MOD_GUI, KEY_R, full,
        before_delay=0.80,   # more generous for first run on some hosts
        after_delay=0.30,
        cdelay=0.012,
        rdelay=0.015,
        dev=None,
    )
    press_enter()
    time.sleep(0.10)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

