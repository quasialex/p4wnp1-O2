#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P4wnP1-O2 OLED Menu (robust, header-aware, rotation & GPIO)

Highlights
----------
- Menu-level header: "header_cmd" (+ optional "header_prefix")
  • Shown as non-selectable header line(s) above items
- Item-level header compatibility: items with "header": true are
  removed from selectable list & rendered in header
- status_cmd runs ONLY on select, opening a separate scrollable viewer
- Small font, dense layout (no "•" dots). Only ">" on selected row
- Joystick: up/down navigation; left/right ONLY for selectors
- Buttons (3): rotation-aware mapping, with rotate on long-press (≥2.5s)
  * ROT=2: BTN3=select, BTN2=back, BTN1=rotate (hold)
  * ROT=0: BTN1=select, BTN2=back, BTN3=rotate (hold)
- Rotate toggles between 0 and 2, and joystick directions are inverted accordingly
- Screensaver: blanks display after OLED_SAVER_SECS (default 12). Any input wakes
- Graceful "no OLED" exit (exit code 0)

Environment (you already export these via systemctl set-environment)
-------------------------------------------------------------------
OLED_IFACE=spi|i2c
OLED_CTRL=sh1106|ssd1306|...
OLED_ROT=0|2
OLED_SPI_PORT=0
OLED_SPI_DEV=0
OLED_SPI_DC=24
OLED_SPI_RST=25
OLED_SAVER_SECS=12

Optional GPIO pin envs (BCM numbers; defaults are common for Waveshare 1.3"):
---------------------------------------------------------------------------
JOY_UP_PIN=6
JOY_DOWN_PIN=19
JOY_LEFT_PIN=5
JOY_RIGHT_PIN=26
JOY_BTN_PIN=13         # joystick center press (unused by default)
BTN1_PIN=21            # K1 (left)  - rotate (long press) or select (ROT=0)
BTN2_PIN=20            # K2 (middle)- back
BTN3_PIN=16            # K3 (right) - select (ROT=2) or rotate (long press)
"""

import os, sys, time, json, shlex, subprocess, traceback
from pathlib import Path
from typing import List, Dict, Any, Optional

# ---- Core paths ----
P4WN_HOME = Path(os.environ.get("P4WN_HOME", "/opt/p4wnp1"))
OLED_DIR   = P4WN_HOME / "oled"
MENU_CFG   = OLED_DIR / "menu_config.json"

# ---- OLED env ----
OLED_IFACE = os.environ.get("OLED_IFACE", "spi").lower()
OLED_CTRL  = os.environ.get("OLED_CTRL", "sh1106").lower()
OLED_ROT   = int(os.environ.get("OLED_ROT", "2"))
OLED_SAVER_SECS = float(os.environ.get("OLED_SAVER_SECS", "12"))

# ---- Font/layout ----
from PIL import Image, ImageDraw, ImageFont

def _load_font():
    # Try bundled small bitmap font, else DejaVu, else default
    for cand in [OLED_DIR / "fonts" / "ProggyTiny.ttf",
                 Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]:
        try:
            if Path(cand).exists():
                return ImageFont.truetype(str(cand), 10)
        except Exception:
            pass
    return ImageFont.load_default()

FONT = _load_font()
LINE_H = 12
PAD = 2

# ---- Device init ----
def _init_device_or_exit():
    try:
        from luma.core.interface.serial import i2c, spi
        from luma.oled.device import sh1106, ssd1306, ssd1322, ssd1325, ssd1331
    except Exception as e:
        print(f"[!] OLED not available: {e}. Exiting without error.")
        sys.exit(0)

    try:
        if OLED_IFACE == "i2c":
            serial = i2c(port=1, address=0x3C)
        else:
            port = int(os.environ.get("OLED_SPI_PORT", "0"))
            devn = int(os.environ.get("OLED_SPI_DEV", "0"))
            dc   = int(os.environ.get("OLED_SPI_DC", "24"))
            rst  = int(os.environ.get("OLED_SPI_RST", "25"))
            serial = spi(port=port, device=devn, gpio_DC=dc, gpio_RST=rst)

        ctrl = OLED_CTRL
        if   ctrl == "sh1106":  dev = sh1106(serial, rotate=OLED_ROT)
        elif ctrl == "ssd1306": dev = ssd1306(serial, rotate=OLED_ROT)
        elif ctrl == "ssd1331": dev = ssd1331(serial, rotate=OLED_ROT)
        elif ctrl == "ssd1322": dev = ssd1322(serial, rotate=OLED_ROT)
        elif ctrl == "ssd1325": dev = ssd1325(serial, rotate=OLED_ROT)
        else:                   dev = sh1106(serial, rotate=OLED_ROT)
        # Keep a reference so we can recreate on rotate
        return dev
    except Exception as e:
        print(f"[!] OLED device not found: {e}. Exiting without error.")
        sys.exit(0)

# device (global; we recreate on rotate)
DEVICE = _init_device_or_exit()

# ---- Utility ----
def expand_vars(s: str) -> str:
    return (s or "").replace("{P4WN_HOME}", str(P4WN_HOME))

def run_shell_one_liner(cmd: str, timeout: float = 1.2) -> str:
    cmd = expand_vars(cmd)
    try:
        cp = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        combo = (cp.stdout or "") + (("\n" + cp.stderr) if cp.returncode not in (0, None) else "")
        for ln in combo.splitlines():
            ln = ln.strip()
            if ln:
                return ln
    except Exception:
        return ""
    return ""

def run_shell_capture(cmd: str, timeout: float = 2.5) -> str:
    cmd = expand_vars(cmd)
    try:
        cp = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (cp.stdout or "") if cp.returncode in (0, None) else ((cp.stdout or "") + (cp.stderr or ""))
    except Exception as e:
        return f"(error: {e})"

# ---- Header cache ----
_HEADER_CACHE: Dict[str, Any] = {}
_HEADER_TTL = 1.5

def cached_header(key: str, resolver) -> str:
    now = time.time()
    ent = _HEADER_CACHE.get(key)
    if ent and now - ent[0] < _HEADER_TTL:
        return ent[1]
    try:
        val = resolver() or ""
    except Exception:
        val = ""
    _HEADER_CACHE[key] = (now, val)
    return val

# ---- Menu model ----
class MenuState:
    def __init__(self, node: Dict[str, Any], parent: Optional["MenuState"] = None):
        self.node = node
        self.parent = parent
        self.items = node.get("submenu", [])
        self.cursor = 0
        self._last_activity = time.time()

    def visible_items(self) -> List[Dict[str, Any]]:
        return [it for it in self.items if not it.get("header")]

    def header_lines(self) -> List[str]:
        lines = []
        # menu-level header
        hcmd = self.node.get("header_cmd")
        if hcmd:
            prefix = self.node.get("header_prefix", "")
            val = cached_header(f"menu:{id(self.node)}", lambda: run_shell_one_liner(hcmd))
            if val:
                lines.append((prefix + val).strip())
        # item-level header (compat)
        for it in self.items:
            if not it.get("header"): continue
            base = it.get("name", "").strip()
            s    = it.get("status_cmd")
            val  = cached_header(f"item:{id(it)}", lambda: run_shell_one_liner(s)) if s else ""
            line = ""
            if base and base.endswith(":") and val:
                line = f"{base} {val}"
            elif base and val:
                line = f"{base} {val}"
            else:
                line = base or val
            if line: lines.append(line.strip())
        return lines[:2]

    def mark_activity(self):
        self._last_activity = time.time()

    def idle_secs(self) -> float:
        return time.time() - self._last_activity

# ---- Drawing ----
def draw_menu(device, state: MenuState, toast: str = ""):
    W, H = device.width, device.height
    img = Image.new("1", (W, H))
    d   = ImageDraw.Draw(img)
    y = PAD

    # Title
    title = state.node.get("name", "Menu")
    d.text((PAD, y), title, font=FONT, fill=255)
    y += LINE_H

    # Header lines
    for hl in state.header_lines():
        d.text((PAD, y), hl, font=FONT, fill=255)
        y += LINE_H

    vis = state.visible_items()
    if vis:
        state.cursor = max(0, min(state.cursor, len(vis)-1))

    avail = (H - y) // LINE_H
    top = 0
    if vis and state.cursor >= avail:
        top = state.cursor - avail + 1

    for i in range(top, min(len(vis), top + avail)):
        it = vis[i]
        prefix = "> " if i == state.cursor else "  "
        label  = it.get("name", "")
        # no dot for unselected
        d.text((PAD, y), prefix + label, font=FONT, fill=255)
        y += LINE_H

    # Toast at bottom
    if toast:
        d.rectangle([(0, H - LINE_H), (W, H)], outline=0, fill=0)
        d.text((PAD, H - LINE_H), toast[:24], font=FONT, fill=255)

    device.display(img)

def draw_viewer(device, title: str, content: str, scroll: int):
    W, H = device.width, device.height
    lines = [ln.rstrip() for ln in (content or "").splitlines()]
    img = Image.new("1", (W, H))
    d   = ImageDraw.Draw(img)
    y = PAD
    d.text((PAD, y), title, font=FONT, fill=255)
    y += LINE_H
    avail = (H - y) // LINE_H
    # clamp
    scroll = max(0, min(max(0, len(lines) - avail), scroll))
    for ln in lines[scroll: scroll + avail]:
        d.text((PAD, y), ln, font=FONT, fill=255)
        y += LINE_H
    device.display(img)
    return scroll, len(lines), avail

# ---- Execute actions ----
def _apply_selector(it: Dict[str, Any]) -> str:
    sel = it.get("selector", {})
    choices = sel.get("choices", [])
    pos = it.setdefault("_sel_idx", 0)
    if not choices: return "(no choices)"
    value = choices[pos].get("value")
    tmpl  = sel.get("action_template")
    if tmpl and value is not None:
        cmd = expand_vars(tmpl.replace("{value}", str(value)))
        try:
            subprocess.Popen(cmd, shell=True)
            return "✓"
        except Exception as e:
            return f"ERR: {e}"
    return "(no template)"

def handle_select(state: MenuState):
    vis = state.visible_items()
    if not vis: return None, ""
    it = vis[state.cursor]

    # status_cmd → open viewer screen (scrollable)
    if it.get("status_cmd"):
        cmd = it["status_cmd"]
        content = run_shell_capture(cmd, timeout=3.0)
        return {"viewer": True, "title": it.get("name", "Output"), "content": content}, ""

    # action
    if it.get("action"):
        try:
            subprocess.Popen(expand_vars(it["action"]), shell=True)
            return None, "✓"
        except Exception as e:
            return None, f"ERR: {e}"

    # script
    if it.get("script"):
        try:
            subprocess.Popen(expand_vars(it["script"]), shell=True)
            return None, "✓"
        except Exception as e:
            return None, f"ERR: {e}"

    # selector apply (pressing select applies current selection)
    if it.get("selector"):
        return None, _apply_selector(it)

    # submenu
    if it.get("submenu"):
        node = {"name": it.get("name",""), "submenu": it["submenu"]}
        # pass through optional header settings if present at item-level
        if "header_cmd" in it: node["header_cmd"] = it["header_cmd"]
        if "header_prefix" in it: node["header_prefix"] = it["header_prefix"]
        return MenuState(node, parent=state), ""

    return None, ""

def selector_move(state: MenuState, delta: int):
    vis = state.visible_items()
    if not vis: return
    it = vis[state.cursor]
    sel = it.get("selector")
    if not sel: return
    choices = sel.get("choices", [])
    if not choices: return
    pos = it.setdefault("_sel_idx", 0)
    it["_sel_idx"] = (pos + delta) % len(choices)

# ---- Input handling (GPIO + keyboard fallback) ----
class Input:
    def __init__(self):
        self.use_gpio = False
        self._gpio = None
        # Pin config (BCM)
        self.JOY_UP    = int(os.environ.get("JOY_UP_PIN", "6"))
        self.JOY_DOWN  = int(os.environ.get("JOY_DOWN_PIN", "19"))
        self.JOY_LEFT  = int(os.environ.get("JOY_LEFT_PIN", "5"))
        self.JOY_RIGHT = int(os.environ.get("JOY_RIGHT_PIN", "26"))
        self.JOY_BTN   = int(os.environ.get("JOY_BTN_PIN", "13"))

        self.BTN1 = int(os.environ.get("BTN1_PIN", "21"))
        self.BTN2 = int(os.environ.get("BTN2_PIN", "20"))
        self.BTN3 = int(os.environ.get("BTN3_PIN", "16"))

        # Debounce
        self._last_evt = 0.0
        self._min_gap = 0.08  # joystick sens guard

        # Button long-press (rotate)
        self._press_start = {}

        # Try GPIO
        try:
            import RPi.GPIO as GPIO
            self._gpio = GPIO
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            for pin in [self.JOY_UP, self.JOY_DOWN, self.JOY_LEFT, self.JOY_RIGHT, self.JOY_BTN, self.BTN1, self.BTN2, self.BTN3]:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.use_gpio = True
        except Exception:
            self.use_gpio = False

    def _edge(self, pin) -> bool:
        # simple polling edge detect with debounce
        g = self._gpio
        if g is None: return False
        now = time.time()
        if now - self._last_evt < self._min_gap:
            return False
        if g.input(pin) == 0:
            self._last_evt = now
            return True
        return False

    def poll(self) -> Optional[str]:
        """
        Return one of: 'UP','DOWN','LEFT','RIGHT','SELECT','BACK','ROTATE','ENTER','ESC'
        """
        if self.use_gpio:
            # Rotation-aware joystick (invert up/down when ROT=2 so "up" is always up)
            up_pin, down_pin = (self.JOY_DOWN, self.JOY_UP) if OLED_ROT == 2 else (self.JOY_UP, self.JOY_DOWN)

            if self._edge(up_pin):    return "UP"
            if self._edge(down_pin):  return "DOWN"
            if self._edge(self.JOY_LEFT):  return "LEFT"
            if self._edge(self.JOY_RIGHT): return "RIGHT"

            # Buttons (mapping depends on rotation)
            # ROT=2: BTN3=select, BTN2=back, BTN1=rotate
            # ROT=0: BTN1=select, BTN2=back, BTN3=rotate
            if OLED_ROT == 2:
                sel_pin, back_pin, rot_pin = self.BTN3, self.BTN2, self.BTN1
            else:
                sel_pin, back_pin, rot_pin = self.BTN1, self.BTN2, self.BTN3

            # Back (short press)
            if self._edge(back_pin): return "BACK"

            # Select (short)
            if self._edge(sel_pin): return "SELECT"

            # Rotate requires long-press
            r = self._gpio
            for name, pin in (("ROTATE", rot_pin),):
                lvl = r.input(pin)
                tnow = time.time()
                if lvl == 0:  # pressed
                    if pin not in self._press_start:
                        self._press_start[pin] = tnow
                    elif tnow - self._press_start[pin] >= 2.5:
                        # consume event
                        self._press_start.pop(pin, None)
                        return "ROTATE"
                else:
                    self._press_start.pop(pin, None)

            return None

        # Keyboard fallback (SSH testing)
        import select, termios, tty
        fd = sys.stdin.fileno()
        dr,_,_ = select.select([sys.stdin], [], [], 0.15)
        if not dr: return None
        ch = sys.stdin.read(1)
        if ch in ("\x03","\x04","q"): sys.exit(0)  # Ctrl-C/D
        if ch in ("\x1b","b"):  return "BACK"
        if ch in ("k",):        return "UP"
        if ch in ("j",):        return "DOWN"
        if ch in ("h",):        return "LEFT"
        if ch in ("l",):        return "RIGHT"
        if ch in ("\r","\n"):   return "SELECT"
        if ch in ("R","r"):     return "ROTATE"
        return None

# ---- loop states ----
def recreate_device(new_rot: int):
    global DEVICE, OLED_ROT
    OLED_ROT = new_rot
    os.environ["OLED_ROT"] = str(new_rot)
    try:
        DEVICE = _init_device_or_exit()
    except SystemExit:
        # If device fails after rotate, just exit gracefully
        sys.exit(0)

def menu_loop():
    inp = Input()
    root = {"name": "P4wnP1-O2", "submenu": _load_menu()}
    state = MenuState(root, None)
    toast = ""

    # viewer mode state
    in_viewer = False
    view_title = ""
    view_body  = ""
    view_scroll = 0

    # Keyboard raw mode for fallback
    kb_fd = None
    old_kb = None
    if not inp.use_gpio:
        import termios, tty
        kb_fd = sys.stdin.fileno()
        old_kb = termios.tcgetattr(kb_fd)
        tty.setcbreak(kb_fd)

    try:
        while True:
            # Screensaver
            if OLED_SAVER_SECS > 0 and state.idle_secs() > OLED_SAVER_SECS:
                # blank
                W,H = DEVICE.width, DEVICE.height
                img = Image.new("1", (W,H))
                DEVICE.display(img)
                # poll until event
                while True:
                    ev = inp.poll()
                    if ev:
                        state.mark_activity()
                        break
                    time.sleep(0.05)
                # after wake, force redraw fresh next loop

            # Draw
            if in_viewer:
                view_scroll, _, _ = draw_viewer(DEVICE, view_title, view_body, view_scroll)
            else:
                draw_menu(DEVICE, state, toast)
            toast = ""

            # Input
            ev = inp.poll()
            if not ev:
                continue
            state.mark_activity()

            if in_viewer:
                if ev == "BACK":
                    in_viewer = False
                    continue
                if ev == "UP":
                    view_scroll = max(0, view_scroll - 1)
                    continue
                if ev == "DOWN":
                    view_scroll += 1
                    continue
                # ignore other keys in viewer
                continue

            # Normal menu mode
            if ev == "ROTATE":
                new_rot = 0 if OLED_ROT == 2 else 2
                recreate_device(new_rot)
                continue

            if ev == "BACK":
                if state.parent:
                    state = state.parent
                continue

            if ev == "UP":
                vis = state.visible_items()
                if vis:
                    state.cursor = (state.cursor - 1) % len(vis)
                continue

            if ev == "DOWN":
                vis = state.visible_items()
                if vis:
                    state.cursor = (state.cursor + 1) % len(vis)
                continue

            if ev == "LEFT":
                selector_move(state, -1)
                continue

            if ev == "RIGHT":
                selector_move(state, +1)
                continue

            if ev == "SELECT":
                nxt, t = handle_select(state)
                if isinstance(nxt, dict) and nxt.get("viewer"):
                    in_viewer = True
                    view_title = nxt.get("title","Output")
                    view_body  = nxt.get("content","")
                    view_scroll = 0
                    continue
                if isinstance(nxt, MenuState):
                    nxt.parent = state
                    state = nxt
                    continue
                toast = t or ""
                continue

    finally:
        if old_kb:
            import termios
            termios.tcsetattr(kb_fd, termios.TCSADRAIN, old_kb)

# ---- menu load ----
def _load_menu() -> List[Dict[str, Any]]:
    try:
        return json.loads(MENU_CFG.read_text())
    except Exception:
        print("[!] Failed to load menu_config.json", file=sys.stderr)
        traceback.print_exc()
        return [{"name": "Error", "submenu":[{"name":"Could not read menu_config.json"}]}]

# ---- main ----
def main():
    try:
        menu_loop()
    except KeyboardInterrupt:
        pass
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    main()
