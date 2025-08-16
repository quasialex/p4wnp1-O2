#!/usr/bin/env python3
# OLED joystick-first menu for P4wnP1-O2
# - Up/Down: move
# - Left: back (or cycle selector left)
# - Right: enter submenu (or cycle selector right)
# - Select: run action/script OR confirm selector
#
# Supports items:
# { "name|title": "Text", "submenu": [...] }
# { "name|title": "Run Thing", "action": "sudo /path/cmd", "confirm": false }
# { "name|title": "Run Script", "script": "/path/to/script.sh", "confirm": true }
# { "name|title": "USB Mode", "selector": {
#      "choices": [{"label":"HID+NET","value":"hid_net_only"},
#                  {"label":"HID+NET+MSD","value":"hid_storage_net"},
#                  {"label":"Storage Only","value":"storage_only"}],
#      "action_template": "sudo {P4WN_HOME}/p4wnctl.py usb set {value}"
#   },
#   "status_cmd": "{P4WN_HOME}/p4wnctl.py usb status"
# }
# { "name|title": "Current USB", "status_cmd": "{P4WN_HOME}/p4wnctl.py usb status" }
#
# Upgrades in this version:
# - Selector choices can be dynamic with "value_cmd" and/or "label_cmd"
#   (e.g., compute host via p4wnctl: value_cmd="python3 /opt/p4wnp1/p4wnctl.py ip primary | xargs -I{} echo \"--host {} --port 8080\"")
# - Backward compatible with static "value" / "label".
# - Status rows still display the last non-empty line of the command output.

import json
import os
import subprocess
import time
from textwrap import wrap

import RPi.GPIO as GPIO
from luma.core.error import DeviceNotFoundError
from luma.core.interface.serial import i2c, spi
from luma.core.render import canvas
from luma.oled.device import sh1106, ssd1306
from PIL import ImageFont

# ========= Config =========
P4WN_HOME = os.getenv("P4WN_HOME", "/opt/p4wnp1")
MENU_CONFIG = os.path.join(P4WN_HOME, "oled/menu_config.json")
LOG_DIR = os.path.join(P4WN_HOME, "logs/")
FONT = ImageFont.load_default()

TOAST_TIME = 2.0  # seconds to show run result
DEBOUNCE = 0.12   # button debounce seconds
LINE_W = 20       # chars per line (approx, for default font)
STATUS_TIMEOUT = 2.0  # default timeout for status_cmd

# ========= GPIO pins (BCM) =========
UP_PIN = 6
DOWN_PIN = 19
LEFT_PIN = 5
RIGHT_PIN = 26
SELECT_PIN = 13
# EXIT_PIN acts as an extra "Back"
EXIT_PIN = 20

GPIO.setmode(GPIO.BCM)
for pin in (UP_PIN, DOWN_PIN, LEFT_PIN, RIGHT_PIN, SELECT_PIN, EXIT_PIN):
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ========= OLED init =========
try:
    serial = i2c(port=1, address=0x3C)
    device = sh1106(serial)
except DeviceNotFoundError:
    serial = spi(device=0, port=0)
    device = ssd1306(serial)

# ========= Helpers =========
def token(s: str) -> str:
    return s.replace("{P4WN_HOME}", P4WN_HOME)

def shell(cmd: str, timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(token(cmd), shell=True, capture_output=True, text=True, timeout=timeout)

def show_lines(lines, hold: float = 0.0):
    with canvas(device) as draw:
        y = 0
        for ln in lines[:5]:
            draw.text((0, y), ln, font=FONT, fill=255)
            y += 12
    if hold > 0:
        time.sleep(hold)

def show_title_status_item(title: str, status: str, item_label: str | None):
    lines = []
    for w in wrap(title, LINE_W):
        lines.append(w)
    if status:
        for w in wrap(status, LINE_W):
            lines.append("· " + w)
    if item_label:
        lines.append("> " + item_label)
    lines.append("↑↓ move ← back →/✓ select")
    show_lines(lines)

def read_status(cmd: str, timeout: float = STATUS_TIMEOUT) -> str:
    try:
        res = shell(cmd, timeout=timeout)
        text = (res.stdout + "\n" + res.stderr).strip()
        if not text:
            return ""
        for ln in reversed(text.splitlines()):
            ln = ln.strip()
            if ln:
                return ln
    except Exception:
        pass
    return ""

def run_cmd(cmd: str, label="action"):
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"{label}.log")
    try:
        res = shell(cmd)
        with open(log_file, "w") as f:
            f.write(res.stdout + "\n" + res.stderr)
        ok = (res.returncode == 0)
        out = (res.stdout + res.stderr).strip().splitlines()
        tail = "\n".join(out[-2:]) if out else ""
        msg = ("✓ OK" if ok else "✗ ERR") + (("\n" + tail) if tail else "")
        return ok, msg
    except Exception as e:
        return False, f"✗ ERR\n{e}"

def debounce_wait():
    time.sleep(DEBOUNCE)

def btn(name):
    if name == 'up' and GPIO.input(UP_PIN) == GPIO.LOW: return True
    if name == 'down' and GPIO.input(DOWN_PIN) == GPIO.LOW: return True
    if name == 'left' and GPIO.input(LEFT_PIN) == GPIO.LOW: return True
    if name == 'right' and GPIO.input(RIGHT_PIN) == GPIO.LOW: return True
    if name == 'select' and GPIO.input(SELECT_PIN) == GPIO.LOW: return True
    if name == 'exit' and GPIO.input(EXIT_PIN) == GPIO.LOW: return True
    return False

def wait_button():
    while True:
        for k in ('up','down','left','right','select','exit'):
            if btn(k):
                debounce_wait()
                return k
        time.sleep(0.03)

# ========= Dynamic choice resolvers (NEW) =========
def _strip_last(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    return text.splitlines()[-1].strip()

def compute_choice_value(choice: dict) -> str:
    """
    Returns the value to be inserted into action_template.
    Precedence:
      1) value_cmd  -> run and take the last non-empty line
      2) value      -> return as-is
      else: ""
    """
    if "value_cmd" in choice and isinstance(choice["value_cmd"], str):
        try:
            res = shell(choice["value_cmd"], timeout=STATUS_TIMEOUT)
            return _strip_last(res.stdout + "\n" + res.stderr)
        except Exception:
            return ""
    return str(choice.get("value", "")).strip()

def compute_choice_label(choice: dict) -> str:
    """
    Visible label for selector position.
    Precedence:
      1) label_cmd  -> run and take last non-empty line
      2) label
      3) value/value_cmd fallback (last line)
    """
    if "label_cmd" in choice and isinstance(choice["label_cmd"], str):
        try:
            res = shell(choice["label_cmd"], timeout=STATUS_TIMEOUT)
            lab = _strip_last(res.stdout + "\n" + res.stderr)
            if lab:
                return lab
        except Exception:
            pass
    if "label" in choice:
        return str(choice["label"])
    # fallback to value/value_cmd textual form
    v = compute_choice_value(choice)
    return v if v else "(empty)"

# ========= Menu loading / validation =========
def load_menu():
    with open(MENU_CONFIG, "r") as f:
        raw = json.load(f)
    return replace_tokens(validate_items(raw))

def replace_tokens(data):
    if isinstance(data, dict):
        return {k: replace_tokens(v) for k, v in data.items()}
    if isinstance(data, list):
        return [replace_tokens(v) for v in data]
    if isinstance(data, str):
        return token(data)
    return data

def title_of(item):
    return item.get("name") or item.get("title") or "Item"

def is_action(item):   return "action" in item or "script" in item
def is_submenu(item):  return "submenu" in item
def is_selector(item): return isinstance(item.get("selector"), dict)
def is_status(item):   return "status_cmd" in item

def _valid_selector(sel: dict) -> bool:
    # must have choices (list) and action_template
    ch = sel.get("choices")
    if not isinstance(ch, list) or not sel.get("action_template"):
        return False
    # each choice must provide either value or value_cmd; label/label_cmd optional
    for c in ch:
        if not isinstance(c, dict):
            return False
        if not ("value" in c or "value_cmd" in c):
            return False
    return True

def validate_items(items):
    valid = []
    for it in items:
        if "submenu" in it and isinstance(it["submenu"], list):
            valid.append(it); continue
        if "action" in it and isinstance(it["action"], str):
            valid.append(it); continue
        if "script" in it and isinstance(it["script"], str) and os.path.exists(it["script"]):
            valid.append(it); continue
        if "selector" in it and isinstance(it["selector"], dict) and _valid_selector(it["selector"]):
            valid.append(it); continue
        if "status_cmd" in it and isinstance(it["status_cmd"], str):
            valid.append(it); continue
        if title_of(it).lower().startswith("← back"):
            valid.append(it); continue
    return valid

# ========= Core UI =========
class MenuState:
    def __init__(self, items, header="Menu"):
        self.items = items
        self.header = header
        self.index = 0
        self.selector_cursor = {}  # per-item selector index

    def current(self):
        if not self.items: return None
        return self.items[self.index]

    def move_up(self):
        if self.items: self.index = (self.index - 1) % len(self.items)

    def move_down(self):
        if self.items: self.index = (self.index + 1) % len(self.items)

    def selector_left(self, item):
        sid = id(item)
        cur = self.selector_cursor.get(sid, 0)
        choices = item["selector"]["choices"]
        cur = (cur - 1) % len(choices)
        self.selector_cursor[sid] = cur

    def selector_right(self, item):
        sid = id(item)
        cur = self.selector_cursor.get(sid, 0)
        choices = item["selector"]["choices"]
        cur = (cur + 1) % len(choices)
        self.selector_cursor[sid] = cur

    def selector_choice(self, item):
        sid = id(item)
        cur = self.selector_cursor.get(sid, 0)
        return item["selector"]["choices"][cur]

def render(state, status_line=""):
    it = state.current()
    if not it:
        show_lines(["Empty menu"]); return
    name = title_of(it)
    # selector label (dynamic)
    if is_selector(it):
        sel = state.selector_choice(it)
        label = f"{name}: {compute_choice_label(sel)}"
    else:
        label = name
    show_title_status_item(state.header, status_line, label)

def confirm_prompt(text="Confirm?"):
    show_lines([text, "", "← No ✓ Yes"])
    while True:
        k = wait_button()
        if k == 'left': return False
        if k in ('select','right'): return True

def exec_item(item):
    # status-only rows: just refresh
    if is_status(item):
        return True, read_status(item["status_cmd"]) or "OK"

    # selector: exec handled in main loop (we need current choice)
    if is_selector(item):
        return False, "selector"

    # action/script
    cmd = item.get("action") or ("bash " + item.get("script"))
    if item.get("confirm", False):
        if not confirm_prompt("Run?\n" + title_of(item)):
            return False, "Cancelled"
    ok, msg = run_cmd(cmd, label=title_of(item).replace(" ", "_"))
    return ok, msg

def menu_loop(root_items):
    stack = [MenuState(root_items, header="P4wnP1-O2")]
    last_mtime = os.path.getmtime(MENU_CONFIG)

    while True:
        # Hot reload
        try:
            mtime = os.path.getmtime(MENU_CONFIG)
            if mtime != last_mtime:
                last_mtime = mtime
                stack = [MenuState(load_menu(), header="P4wnP1-O2")]
        except Exception:
            pass

        state = stack[-1]
        cur = state.current()

        # compute a status line if item has one
        status_line = ""
        if cur and is_status(cur):
            status_line = read_status(cur["status_cmd"])
        elif cur and is_selector(cur) and cur.get("status_cmd"):
            status_line = read_status(cur["status_cmd"])

        render(state, status_line=status_line)
        k = wait_button()

        # EXIT or Left (back)
        if k == 'exit' or (k == 'left' and not is_selector(cur)):
            if len(stack) > 1:
                stack.pop()
            continue

        if k == 'up':
            state.move_up(); continue
        if k == 'down':
            state.move_down(); continue
        if cur is None:
            continue

        if is_selector(cur):
            if k == 'left':
                state.selector_left(cur); continue
            if k == 'right':
                state.selector_right(cur); continue
            if k == 'select':
                choice = state.selector_choice(cur)
                # compute dynamic value & label (NEW)
                value = compute_choice_value(choice)
                disp_label = compute_choice_label(choice)
                tmpl = cur["selector"]["action_template"]
                cmd = tmpl.replace("{value}", str(value)).replace("{P4WN_HOME}", P4WN_HOME)
                label = f"{title_of(cur)}: {disp_label}"
                ok, msg = run_cmd(cmd, label=label.replace(" ", "_"))
                show_lines([label] + wrap(msg, LINE_W)[:4], hold=TOAST_TIME)
                continue

        if is_submenu(cur):
            header = title_of(cur)
            items = validate_items(cur["submenu"])
            stack.append(MenuState(items, header=header))
            continue

        if is_action(cur):
            ok, msg = exec_item(cur)
            label = title_of(cur)
            show_lines([label] + wrap(msg, LINE_W)[:4], hold=TOAST_TIME)
            continue

        if is_status(cur) and k in ('select','right'):
            status_line = read_status(cur["status_cmd"])
            show_lines([title_of(cur)] + wrap(status_line or "OK", LINE_W)[:4], hold=TOAST_TIME)
            continue

# ========= main =========
def main():
    try:
        root = load_menu()
        menu_loop(root)
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
