#!/usr/bin/env python3
"""
Tiny DuckyScript runner using existing tools/hid_type.py

Supports:
  STRING <text>
  DELAY <ms>
  GUI|WINDOWS, ALT, CTRL, SHIFT + KEY
  ENTER, TAB, ESC, BACKSPACE, SPACE
  REM comments
"""

import time, sys
from pathlib import Path

# reuse your existing HID sender
# expects /opt/p4wnp1/tools/hid_type.py with send_keys(), send_combo(), key constants
from tools.hid_type import send_text, send_combo, \
    MOD_GUI, MOD_ALT, MOD_CTRL, MOD_SHIFT, \
    KEY_ENTER, KEY_TAB, KEY_ESC, KEY_BACKSPACE, KEY_SPACE, \
    KEY_R, KEY_D

SPECIAL_KEYS = {
    "ENTER": KEY_ENTER,
    "TAB": KEY_TAB,
    "ESC": KEY_ESC,
    "BACKSPACE": KEY_BACKSPACE,
    "SPACE": KEY_SPACE,
    "R": KEY_R,
    "D": KEY_D,
}

MODS = {
    "GUI": MOD_GUI, "WINDOWS": MOD_GUI,
    "ALT": MOD_ALT,
    "CTRL": MOD_CTRL, "CONTROL": MOD_CTRL,
    "SHIFT": MOD_SHIFT,
}

def parse_and_run(lines):
    for raw in lines:
        line = raw.strip()
        if not line or line.upper().startswith("REM"):
            continue
        parts = line.split()
        cmd = parts[0].upper()
        args = parts[1:]

        if cmd == "DELAY" and args:
            ms = int(args[0])
            time.sleep(ms / 1000.0)
            continue

        if cmd == "STRING":
            txt = line.partition(" ")[2]
            send_text(txt)
            continue

        # Modifiers like CTRL ALT DEL or GUI R
        if cmd in MODS:
            if not args:
                continue
            mod_mask = MODS[cmd]
            # single-key combos: e.g., GUI r / CTRL d
            keytok = args[0].upper()
            keycode = SPECIAL_KEYS.get(keytok)
            if not keycode:
                # try single character (letters/numbers)
                ch = keytok
                if len(ch) == 1:
                    from tools.hid_type import keycode_for_char
                    keycode = keycode_for_char(ch)
            if keycode:
                send_combo(mod_mask, keycode)
            continue

        # Single special key
        if cmd in SPECIAL_KEYS:
            from tools.hid_type import send_keys
            send_keys([SPECIAL_KEYS[cmd]])
            continue

        # FALLBACK: treat as text
        send_text(line)

def main():
    if len(sys.argv) < 2:
        print("usage: ducky.py <script.duck>", file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"not found: {path}", file=sys.stderr)
        return 2
    parse_and_run(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    return 0

if __name__ == "__main__":
    sys.exit(main())
