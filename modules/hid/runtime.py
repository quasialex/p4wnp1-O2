#!/usr/bin/env python3
"""
HID runtime with a tiny DSL:
  STRING <text>
  DELAY <ms>
  ENTER / ESC / TAB / UP / DOWN / LEFT / RIGHT / BACKSPACE
  CTRL|ALT|SHIFT|GUI + <keys...>     (e.g., CTRL ALT DEL, CTRL r)
  KEY <rawname>                      (e.g., KEY F5)
  MOUSEMOVE <dx> <dy>
  CLICK [LEFT|RIGHT|MIDDLE]          (default LEFT)
  SCROLL <steps>                     (positive=up, negative=down)
  WAITLED <caps|num|scroll> <0|1>    (wait for host LED state)
  LAYOUT <us|es|gb|de|fr>            (switch keymap)
  # comments
Reads OUT reports from /dev/hidg0 to detect LED state.
"""
import os, sys, time, threading, queue, json, fcntl, errno
from pathlib import Path
from typing import Dict, Optional

DEV = "/dev/hidg0"  # keyboard endpoint
MOUSE_DEV = "/dev/hidg1"  # if you add mouse HID function as 'hid.mouse' (optional)

P4WN_HOME = Path(os.environ.get("P4WN_HOME", "/opt/p4wnp1"))
LAYOUT_DIR = P4WN_HOME / "config" / "hid_layouts"

# --- minimal US keymap (extend later if needed) ---
DEFAULT_LAYOUT = {
  "a": (0x04, False),"b": (0x05, False),"c": (0x06, False),"d": (0x07, False),
  "e": (0x08, False),"f": (0x09, False),"g": (0x0A, False),"h": (0x0B, False),
  "i": (0x0C, False),"j": (0x0D, False),"k": (0x0E, False),"l": (0x0F, False),
  "m": (0x10, False),"n": (0x11, False),"o": (0x12, False),"p": (0x13, False),
  "q": (0x14, False),"r": (0x15, False),"s": (0x16, False),"t": (0x17, False),
  "u": (0x18, False),"v": (0x19, False),"w": (0x1A, False),"x": (0x1B, False),
  "y": (0x1C, False),"z": (0x1D, False),
  "1": (0x1E, False),"2": (0x1F, False),"3": (0x20, False),"4": (0x21, False),
  "5": (0x22, False),"6": (0x23, False),"7": (0x24, False),"8": (0x25, False),
  "9": (0x26, False),"0": (0x27, False),
  " ": (0x2C, False),"-": (0x2D, False),"=": (0x2E, False),"[": (0x2F, False),
  "]": (0x30, False),"\\":(0x31, False),";": (0x33, False),"'": (0x34, False),
  "`": (0x35, False),",": (0x36, False),".": (0x37, False),"/": (0x38, False),
  "!": (0x1E, True), "@": (0x1F, True), "#": (0x20, True), "$": (0x21, True),
  "%": (0x22, True), "^": (0x23, True), "&": (0x24, True), "*": (0x25, True),
  "(": (0x26, True), ")": (0x27, True), "_": (0x2D, True), "+": (0x2E, True),
  "{": (0x2F, True), "}": (0x30, True), "|": (0x31, True), ":": (0x33, True),
  "\"":(0x34, True), "~": (0x35, True), "<": (0x36, True), ">": (0x37, True),
  "?": (0x38, True),
}

MOD = {
  "CTRL": 0x01, "SHIFT": 0x02, "ALT": 0x04, "GUI": 0x08,
}

NAMED = {
  "ENTER": 0x28, "ESC": 0x29, "BACKSPACE": 0x2A, "TAB": 0x2B,
  "SPACE": 0x2C, "UP": 0x52, "DOWN": 0x51, "LEFT": 0x50, "RIGHT": 0x4F,
  "F1":0x3A,"F2":0x3B,"F3":0x3C,"F4":0x3D,"F5":0x3E,"F6":0x3F,"F7":0x40,
  "F8":0x41,"F9":0x42,"F10":0x43,"F11":0x44,"F12":0x45,
  "DEL":0x4C, "HOME":0x4A, "END":0x4D, "PGUP":0x4B, "PGDN":0x4E,
}

LED_MASKS = {"num":0x01, "caps":0x02, "scroll":0x04}

class HID:
    def __init__(self, dev=DEV, mouse_dev=MOUSE_DEV):
        self.dev = dev
        self.mouse_dev = mouse_dev
        self.kb = None
        self.mouse = None
        self.led_state = 0
        self.led_q = queue.Queue(maxsize=32)
        self._stop = threading.Event()
        self.layout_name = "us"
        self.layout = DEFAULT_LAYOUT
        self._load_layout("us")

    def _load_layout(self, name: str):
        p = LAYOUT_DIR / f"{name}.json"
        if p.exists():
            try:
                self.layout = json.loads(p.read_text())
                self.layout_name = name
                return
            except Exception:
                pass
        self.layout = DEFAULT_LAYOUT
        self.layout_name = "us"

    def open(self):
        self.kb = open(self.dev, "rb+", buffering=0)
        flags = fcntl.fcntl(self.kb.fileno(), fcntl.F_GETFL)
        fcntl.fcntl(self.kb.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)
        if os.path.exists(self.mouse_dev):
            try:
                self.mouse = open(self.mouse_dev, "rb+", buffering=0)
            except Exception:
                self.mouse = None
        t = threading.Thread(target=self._read_loop, daemon=True)
        t.start()

    def close(self):
        self._stop.set()
        try:
            if self.kb: self.kb.close()
        except Exception: pass
        try:
            if self.mouse: self.mouse.close()
        except Exception: pass

    def _read_loop(self):
        # Read OUT reports for LED state (1 byte payload from host)
        while not self._stop.is_set():
            try:
                data = self.kb.read(8)  # OUT report length often equals IN len
                if not data: 
                    time.sleep(0.01); continue
                # Many hosts send output report with LED bitmask in byte 0 or 1.
                # Linux HID gadget usually delivers 1st byte as LED mask.
                val = data[0]
                if val != self.led_state:
                    self.led_state = val
                    try: self.led_q.put_nowait(val)
                    except queue.Full: pass
            except Exception:
                time.sleep(0.02)

    # --- keyboard writers ---

    def _send(self, mod: int, keycodes: list[int], timeout=5.0):
    report = bytes([mod, 0] + keycodes[:6] + [0]*(6-len(keycodes[:6])))
    end = time.time() + timeout
    while True:
        try:
            os.write(self.kb.fileno(), report)  # non-blocking write
            break
        except BlockingIOError:
            if time.time() > end:
                raise TimeoutError("HID write timed out (host not polling)")
            time.sleep(0.02)

    def _release_all(self):
        self._send(0, [])

    def tap_keycode(self, kc: int, mod: int=0, ms: int=20):
        self._send(mod, [kc])
        time.sleep(ms/1000.0)
        self._release_all()

    def type_text(self, s: str, wpm: int = 600):
        # Convert characters using layout
        delay = max(1, int(60000/(wpm*5)))  # rough ms per char
        for ch in s:
            if ch == "\n":
                self.tap_keycode(NAMED["ENTER"])
                continue
            kc, need_shift = self.layout.get(ch, (None, False))
            if kc is None:
                # try lowercase mapping
                kc, need_shift = self.layout.get(ch.lower(), (None, False))
                if kc is None:
                    continue
                if ch.isupper():
                    need_shift = True
            mod = MOD["SHIFT"] if need_shift else 0
            self.tap_keycode(kc, mod=mod, ms=delay)

    def chord(self, names: list[str], ms: int=80):
        mod = 0; keys=[]
        for n in names:
            up = n.upper()
            if up in MOD: mod |= MOD[up]; continue
            if up in NAMED: keys.append(NAMED[up]); continue
            if len(up) == 1:
                kc, need_shift = self.layout.get(up.lower(), (None, False))
                if kc is not None:
                    if need_shift: mod |= MOD["SHIFT"]
                    keys.append(kc)
        self._send(mod, keys[:6])
        time.sleep(ms/1000.0)
        self._release_all()

    # --- mouse ---

    def mousemove(self, dx: int, dy: int):
        if not self.mouse: return
        # report: [buttons, dx, dy, wheel]
        dx = (dx + 256) % 256
        dy = (dy + 256) % 256
        self.mouse.write(bytes([0, dx, dy, 0])); self.mouse.flush()

    def click(self, btn="LEFT"):
        if not self.mouse: return
        btn = btn.upper()
        mask = 1 if btn=="LEFT" else 2 if btn=="RIGHT" else 4
        self.mouse.write(bytes([mask, 0, 0, 0])); self.mouse.flush()
        time.sleep(0.05)
        self.mouse.write(bytes([0, 0, 0, 0])); self.mouse.flush()

    def scroll(self, steps: int):
        if not self.mouse: return
        val = (steps + 256) % 256
        self.mouse.write(bytes([0, 0, 0, val])); self.mouse.flush()

    # --- LED wait ---

    def wait_led(self, which: str, state: int, timeout: float=10.0):
        mask = LED_MASKS[which]
        end = time.time() + timeout
        while time.time() < end:
            if bool(self.led_state & mask) == bool(state):
                return True
            try:
                v = self.led_q.get(timeout=0.2)
                if bool(v & mask) == bool(state):
                    return True
            except queue.Empty:
                pass
        return False

    # --- DSL interpreter ---

    def run_script(self, lines: list[str]):
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            cmd = parts[0].upper()
            args = parts[1:]

            if cmd == "STRING":
                text = raw.split(" ", 1)[1] if " " in raw else ""
                self.type_text(text)
            elif cmd == "DELAY":
                time.sleep(int(args[0])/1000.0)
            elif cmd in ("ENTER","ESC","TAB","UP","DOWN","LEFT","RIGHT","BACKSPACE","HOME","END","PGUP","PGDN","DEL"):
                self.tap_keycode(NAMED[cmd])
            elif cmd == "KEY":
                keyname = args[0].upper()
                self.tap_keycode(NAMED.get(keyname, NAMED["ENTER"]))  # fallback
            elif cmd in ("CTRL","ALT","SHIFT","GUI"):
                keys = [p for p in [cmd] + args if p]
                self.chord(keys)
            elif cmd == "MOUSEMOVE":
                self.mousemove(int(args[0]), int(args[1]))
            elif cmd == "CLICK":
                self.click(args[0] if args else "LEFT")
            elif cmd == "SCROLL":
                self.scroll(int(args[0]))
            elif cmd == "WAITLED":
                which, st = args[0].lower(), int(args[1])
                self.wait_led(which, st)
            elif cmd == "LAYOUT":
                self._load_layout(args[0].lower())
            else:
                # Try generic chord: e.g., "CTRL ALT DEL"
                self.chord([cmd] + args)

def run_file(path: str):
    with open(path, "r") as f:
        lines = f.read().splitlines()
    h = HID()
    h.open()
    try:
        h.run_script(lines)
    finally:
        h.close()

if __name__ == "__main__":
    run_file(sys.argv[1])

