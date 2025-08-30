#!/usr/bin/env python3
"""
p4wnhid.py — compatibility + quality-of-life layer over hid_type.py

Exports:
  send_key(*keys)                # e.g. send_key("GUI","R"), send_key("CTRL","ALT","DEL")
  send_string(text)              # type text verbatim (US layout)
  enter()                        # press Enter
  sleep_ms(ms)                   # simple delay in milliseconds
  win_r(), alt_tab(), ctrl_alt_del(), win_l()
  paste(), copy(), cut(), select_all()
  backspace(n=1), delete(n=1)
  arrow_up(n=1), arrow_down(n=1), arrow_left(n=1), arrow_right(n=1)
  type_and_enter(text)
  run_cmd(cmd="cmd"), run_powershell()
  exec_cmdline(cmdline)          # Win+R → type cmdline → Enter
  exec_powershell(ps)            # Win+R → "powershell" → type ps → Enter
  set_device("/dev/hidg0"), set_delays(cdelay=..., rdelay=...)
"""

import time
from typing import Iterable, Tuple

# Reuse your robust HID driver
from hid_type import (
    type_string, send_combo, press_enter, win_r,
    MOD_NONE, MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI,
    KEY_ENTER, KEY_ESC, KEY_TAB, KEY_SPACE,  # base codes
)  # :contentReference[oaicite:2]{index=2}

# -----------------------
# Module-level defaults
# -----------------------
_DEV: str | None   = None       # autodetect by default (hid_type does it)
_CDELAY: float      = 0.01       # key press -> release delay
_RDELAY: float      = 0.01       # release -> next key delay
_STEP_DELAY: float  = 0.06       # between repeated nav keys (arrows, bksp, del)

# -----------------------
# Key name → HID usage
# (minimal set, extend if needed)
# -----------------------
NAME_TO_CODE = {
    "ENTER": KEY_ENTER,
    "ESC":   KEY_ESC,
    "TAB":   KEY_TAB,
    "SPACE": KEY_SPACE,

    # Arrows
    "UP":    0x52, "DOWN": 0x51, "LEFT": 0x50, "RIGHT": 0x4f,

    # Edit keys
    "BACKSPACE": 0x2a, "BKSP": 0x2a,
    "DELETE": 0x4c, "DEL": 0x4c,

    # Function keys (sample)
    "F1": 0x3a, "F2": 0x3b, "F3": 0x3c, "F4": 0x3d,

    # Letter shortcuts used in combos (Win+L, Ctrl+C/V/A/X, etc.)
    "A": 0x04, "C": 0x06, "D": 0x07, "E": 0x08, "L": 0x0f,
    "R": 0x15, "T": 0x17, "V": 0x19, "X": 0x1b,
}

MOD_NAME = {
    "CTRL": MOD_CTRL,
    "SHIFT": MOD_SHIFT,
    "ALT": MOD_ALT,
    "GUI": MOD_GUI, "WIN": MOD_GUI, "SUPER": MOD_GUI,
}

# -----------------------
# Internal helpers
# -----------------------
def _split_mods_and_key(parts: Iterable[str]) -> Tuple[int, int]:
    mods = 0
    keycode = None
    for p in parts:
        u = p.upper()
        if u in MOD_NAME:
            mods |= MOD_NAME[u]
        else:
            if u not in NAME_TO_CODE:
                raise ValueError(f"Unknown key name: {p}")
            if keycode is not None:
                raise ValueError(f"Multiple non-modifier keys given: {p}")
            keycode = NAME_TO_CODE[u]
    if keycode is None:
        raise ValueError("You must provide exactly one non-modifier key (e.g. 'TAB').")
    return mods, keycode

def _press_named(*keys: str):
    mods, keycode = _split_mods_and_key(keys)
    send_combo(mods, keycode, dev=_DEV, cdelay=_CDELAY, rdelay=_RDELAY)  # :contentReference[oaicite:3]{index=3}

# -----------------------
# Public API expected by payloads
# -----------------------
def set_device(dev: str | None):
    """Pin to a specific /dev/hidgN. None = auto-detect."""
    global _DEV
    _DEV = dev

def set_delays(cdelay: float | None = None, rdelay: float | None = None, step_delay: float | None = None):
    """Tune key timings."""
    global _CDELAY, _RDELAY, _STEP_DELAY
    if cdelay is not None: _CDELAY = max(0.001, cdelay)
    if rdelay is not None: _RDELAY = max(0.001, rdelay)
    if step_delay is not None: _STEP_DELAY = max(0.001, step_delay)

def sleep_ms(ms: int):
    time.sleep(max(0, ms) / 1000.0)

def send_key(*keys: str):
    """
    Press a combo, e.g. send_key("GUI","R"), send_key("CTRL","ALT","DEL"), send_key("TAB")
    """
    _press_named(*keys)

def send_string(text: str):
    # Uses hid_type's robust typer (auto-detects device if _DEV is None)  :contentReference[oaicite:4]{index=4}
    type_string(text, dev=_DEV, cdelay=_CDELAY, rdelay=_RDELAY)

def enter():
    send_combo(MOD_NONE, KEY_ENTER, dev=_DEV, cdelay=_CDELAY, rdelay=_RDELAY)  # :contentReference[oaicite:5]{index=5}

# -----------------------
# Quality-of-life combos
# -----------------------
def win_r():
    # direct helper already exists in hid_type, but we keep symmetry here  :contentReference[oaicite:6]{index=6}
    _press_named("GUI", "R")

def alt_tab():
    _press_named("ALT", "TAB")

def ctrl_alt_del():
    _press_named("CTRL", "ALT", "DEL")

def win_l():
    _press_named("GUI", "L")

def paste():
    _press_named("CTRL", "V")

def copy():
    _press_named("CTRL", "C")

def cut():
    _press_named("CTRL", "X")

def select_all():
    _press_named("CTRL", "A")

# -----------------------
# Repeating navigation / editing
# -----------------------
def _repeat(key: str, n: int, per_step: float | None = None):
    for _ in range(max(0, n)):
        _press_named(key)
        time.sleep(per_step if per_step is not None else _STEP_DELAY)

def backspace(n: int = 1): _repeat("BACKSPACE", n)
def delete(n: int = 1):    _repeat("DELETE", n)
def arrow_up(n: int = 1):  _repeat("UP", n)
def arrow_down(n: int = 1):_repeat("DOWN", n)
def arrow_left(n: int = 1):_repeat("LEFT", n)
def arrow_right(n: int = 1):_repeat("RIGHT", n)

# -----------------------
# Higher-level helpers you’ll use a lot
# -----------------------
def type_and_enter(text: str):
    send_string(text)
    enter()

def run_cmd(cmd: str = "cmd"):
    win_r()
    sleep_ms(300)
    type_and_enter(cmd)
    sleep_ms(900)

def run_powershell():
    run_cmd("powershell")

def exec_cmdline(cmdline: str):
    """Win+R → cmdline → Enter"""
    win_r()
    sleep_ms(300)
    type_and_enter(cmdline)
    sleep_ms(900)

def exec_powershell(ps: str):
    """Open PowerShell via Win+R and execute a command string."""
    win_r()
    sleep_ms(300)
    type_and_enter("powershell")
    sleep_ms(900)
    type_and_enter(ps)

__all__ = [
    "send_key", "send_string", "enter", "sleep_ms",
    "win_r", "alt_tab", "ctrl_alt_del", "win_l",
    "paste", "copy", "cut", "select_all",
    "backspace", "delete", "arrow_up", "arrow_down", "arrow_left", "arrow_right",
    "type_and_enter", "run_cmd", "run_powershell", "exec_cmdline", "exec_powershell",
    "set_device", "set_delays",
]
