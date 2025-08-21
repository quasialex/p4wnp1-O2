#!/usr/bin/env python3
"""
P4wnP1-O2 HID typing helper

- Auto-detects /dev/hidgN and writes boot-keyboard reports there
- Import-safe: provides type_string(), win_r(), press_enter(), send_combo()
- CLI usage:
    python3 hid_type.py "Hello world"
    python3 hid_type.py --device /dev/hidg0 "Hello"
    python3 hid_type.py --dry-run "Hello!"
"""
import os, sys, time, argparse, stat
from typing import Optional, Tuple

DEFAULT_DEV_CANDIDATES = [f"/dev/hidg{i}" for i in range(0, 8)]
MOD_NONE   = 0x00
MOD_CTRL   = 0x01
MOD_SHIFT  = 0x02
MOD_ALT    = 0x04
MOD_GUI    = 0x08  # Windows / Super

KEY_ENTER  = 0x28
KEY_ESC    = 0x29
KEY_TAB    = 0x2b
KEY_SPACE  = 0x2c
KEY_R      = 0x15  # 'r'

# Minimal US layout; extend if you need more
KEYMAP = {
    **{chr(ord('a')+i):(MOD_NONE, 0x04+i) for i in range(26)},
    **{chr(ord('A')+i):(MOD_SHIFT, 0x04+i) for i in range(26)},
    '1': (MOD_NONE, 0x1e), '2': (MOD_NONE, 0x1f), '3': (MOD_NONE, 0x20),
    '4': (MOD_NONE, 0x21), '5': (MOD_NONE, 0x22), '6': (MOD_NONE, 0x23),
    '7': (MOD_NONE, 0x24), '8': (MOD_NONE, 0x25), '9': (MOD_NONE, 0x26),
    '0': (MOD_NONE, 0x27),
    ' ': (MOD_NONE, 0x2c), '\t': (MOD_NONE, 0x2b), '\n': (MOD_NONE, 0x28),
    '-': (MOD_NONE, 0x2d), '=': (MOD_NONE, 0x2e), '[': (MOD_NONE, 0x2f),
    ']': (MOD_NONE, 0x30), '\\': (MOD_NONE, 0x31), ';': (MOD_NONE, 0x33),
    "'": (MOD_NONE, 0x34), '`': (MOD_NONE, 0x35), ',': (MOD_NONE, 0x36),
    '.': (MOD_NONE, 0x37), '/': (MOD_NONE, 0x38),
    '_': (MOD_SHIFT, 0x2d), '+': (MOD_SHIFT, 0x2e), '{': (MOD_SHIFT, 0x2f),
    '}': (MOD_SHIFT, 0x30), '|': (MOD_SHIFT, 0x31), ':': (MOD_SHIFT, 0x33),
    '"': (MOD_SHIFT, 0x34), '~': (MOD_SHIFT, 0x35), '<': (MOD_SHIFT, 0x36),
    '>': (MOD_SHIFT, 0x37), '?': (MOD_SHIFT, 0x38),
    '!': (MOD_SHIFT, 0x1e), '@': (MOD_SHIFT, 0x1f), '#': (MOD_SHIFT, 0x20),
    '$': (MOD_SHIFT, 0x21), '%': (MOD_SHIFT, 0x22), '^': (MOD_SHIFT, 0x23),
    '&': (MOD_SHIFT, 0x24), '*': (MOD_SHIFT, 0x25), '(': (MOD_SHIFT, 0x26),
    ')': (MOD_SHIFT, 0x27),
}

def _is_writable_chardev(path: str) -> bool:
    try:
        st = os.stat(path)
        return stat.S_ISCHR(st.st_mode) and os.access(path, os.W_OK)
    except FileNotFoundError:
        return False

def find_hid_device(explicit: Optional[str] = None) -> str:
    if explicit:
        if _is_writable_chardev(explicit):
            return explicit
        raise FileNotFoundError(f"HID device not writable or not present: {explicit}")
    for p in DEFAULT_DEV_CANDIDATES:
        if _is_writable_chardev(p):
            return p
    tried = ", ".join(DEFAULT_DEV_CANDIDATES)
    raise FileNotFoundError(f"No writable HID gadget found (tried: {tried}). "
                            "Enable HID (e.g. `p4wnctl.py usb set hid_net_only`).")

def _report(mod: int, code: int) -> bytes:
    return bytes([mod & 0xff, 0x00, code & 0xff, 0, 0, 0, 0, 0])

def _send(devf, mod: int, code: int, cdelay=0.01, rdelay=0.01):
    devf.write(_report(mod, code)); devf.flush()
    time.sleep(cdelay)
    devf.write(b"\x00\x00\x00\x00\x00\x00\x00\x00"); devf.flush()
    time.sleep(rdelay)

def _type_char(devf, ch: str, cdelay: float, rdelay: float):
    mod, code = KEYMAP.get(ch, (MOD_NONE, KEY_SPACE))
    _send(devf, mod, code, cdelay, rdelay)

def type_string(text: str, dev: Optional[str] = None,
                cdelay: float = 0.01, rdelay: float = 0.01, dry_run: bool = False):
    """Type an entire string to the HID gadget (\\n sends Enter)."""
    if dry_run:
        out = []
        for ch in text:
            mod, code = KEYMAP.get(ch, (MOD_NONE, KEY_SPACE))
            tag = ("S+" if (mod & MOD_SHIFT) else "") + f"{code:02x}"
            out.append(f"{repr(ch)}->{tag}")
        print("DRY:", " ".join(out)); return

    path = find_hid_device(dev)
    with open(path, "wb", buffering=0) as f:
        for ch in text:
            _type_char(f, ch, cdelay, rdelay)

# Convenience combos
def send_combo(mod: int, code: int, dev: Optional[str] = None,
               cdelay: float = 0.01, rdelay: float = 0.01):
    path = find_hid_device(dev)
    with open(path, "wb", buffering=0) as f:
        _send(f, mod, code, cdelay, rdelay)

def press_enter(dev: Optional[str] = None):
    send_combo(MOD_NONE, KEY_ENTER, dev)

def win_r(dev: Optional[str] = None):
    send_combo(MOD_GUI, KEY_R, dev)

# CLI
def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Type a string via /dev/hidgN (USB HID keyboard).")
    ap.add_argument("--device", "-d", help="HID gadget device (default: auto)")
    ap.add_argument("--cdelay", type=float, default=0.01)
    ap.add_argument("--rdelay", type=float, default=0.01)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("text", nargs='?', help="text to type")
    args = ap.parse_args(argv)
    if args.text is None:
        ap.print_help(); return 1
    try:
        type_string(args.text, dev=args.device, cdelay=args.cdelay, rdelay=args.rdelay, dry_run=args.dry_run)
    except Exception as e:
        print(f"[!] {e}", file=sys.stderr); return 1
    return 0

def hotkey_then_type(mod: int, keycode: int, text: str,
                     before_delay=0.3, after_delay=0.9,
                     cdelay=0.01, rdelay=0.02, dev: str | None = None):
    """Press a hotkey (e.g. Win+R), wait, then type text."""
    send_combo(mod, keycode, dev, cdelay, rdelay)
    time.sleep(before_delay)
    type_string(text, dev, cdelay, rdelay)
    time.sleep(after_delay)

if __name__ == "__main__":
    sys.exit(_main())

