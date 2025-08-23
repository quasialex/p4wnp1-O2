#!/usr/bin/env python3
# P4wnP1-O2 OLED menu — Waveshare 1.3" SPI SH1106 (hard-coded)
# Rotation-aware controls:
#   ROT=2 (180°):  KEY3=Select, KEY2=Back, KEY1=Rotate(long), KEY1 short = selector cycle
#   ROT=0 (0°):    KEY1=Select, KEY2=Back, KEY3=Rotate(long), KEY3 short = selector cycle
# Joystick: up/down only. **Flipped when ROT=0** so UP always feels like UP.

import json, subprocess, os, sys, time, traceback, shutil
import shlex, signal
from pathlib import Path
from textwrap import wrap

import RPi.GPIO as GPIO
from PIL import Image, ImageFont
from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.oled.device import sh1106, ssd1306

# ---------- Paths / constants ----------
P4WN_HOME    = os.getenv("P4WN_HOME", "/opt/p4wnp1")
MENU_CONFIG  = Path(P4WN_HOME) / "oled" / "menu_config.json"
ROT_FILE     = Path(P4WN_HOME) / "oled" / "rotation.json"
SAVER_IMAGE  = Path(P4WN_HOME) / "oled" / "saver.png"   # <- place your logo here
LOG_DIR      = Path(P4WN_HOME) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Idle behavior
SAVER_SHOW_AFTER_S = 8.0   # show logo after this much idle
SAVER_POWER_OFF_S  = 25.0   # turn screen fully off after this much idle
SAVER_PEEK_S       = 0.5    # how long to show logo when pressing Back at top

TOAST_TIME       = 2.0
DEBOUNCE         = 0.12
RELEASE_WAIT     = 0.40
STATUS_TIMEOUT   = 2.0
LONG_PRESS_S     = 2.0

# ---------- Waveshare 1.3" OLED (SPI, SH1106) ----------
OLED_SPI_PORT = 0
OLED_SPI_DEV  = 0
OLED_SPI_DC   = 24
OLED_SPI_RST  = 25
OLED_CTRL     = "sh1106"    # sh1106 | ssd1306

# ---------- Buttons (BCM) ----------
# Joystick (5-way) — use only UP/DOWN
JOY_UP, JOY_DOWN, JOY_LEFT, JOY_RIGHT, JOY_CENTER = 6, 19, 5, 26, 13
# Right-side keys (adjust if your HAT revision differs)
KEY1, KEY2, KEY3 = 21, 20, 16

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
for p in (JOY_UP, JOY_DOWN, JOY_LEFT, JOY_RIGHT, JOY_CENTER, KEY1, KEY2, KEY3):
    GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ---------- OLED init / rotation ----------
def _load_rotation():
    try:
        if ROT_FILE.exists():
            return int(json.loads(ROT_FILE.read_text()).get("rotate", 2)) % 4
    except Exception:
        pass
    return 2  # default 180°

def _save_rotation(rot):
    try:
        ROT_FILE.parent.mkdir(parents=True, exist_ok=True)
        ROT_FILE.write_text(json.dumps({"rotate": int(rot) % 4}))
    except Exception:
        pass

def _make_device(rot):
    serial = spi(port=OLED_SPI_PORT, device=OLED_SPI_DEV, gpio_DC=OLED_SPI_DC, gpio_RST=OLED_SPI_RST)
    return (ssd1306 if OLED_CTRL == "ssd1306" else sh1106)(serial, rotate=rot)

def _init_device():
    try:
        return _make_device(_load_rotation())
    except Exception as e:
        print(f"[!] OLED not available: {e}. Exiting without error.")
        sys.exit(0)

DEVICE = _init_device()

# ---------- Font / layout ----------
def _load_font():
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 9),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 8),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9),
    ]
    for path, sz in candidates:
        try:
            f = ImageFont.truetype(path, sz)
            try:
                lh = f.getbbox("Ag")[3] - f.getbbox("Ag")[1]
                cw = f.getbbox("M")[2] - f.getbbox("M")[0]
            except Exception:
                lh = f.getsize("Ag")[1]; cw = max(f.getsize("M")[0], 6)
            return f, max(lh, 8), max(cw, 5)
        except Exception:
            pass
    f = ImageFont.load_default()
    try:
        lh = f.getbbox("Ag")[3] - f.getbbox("Ag")[1]
        cw = f.getbbox("M")[2] - f.getbbox("M")[0]
    except Exception:
        lh = f.getsize("Ag")[1]; cw = max(f.getsize("M")[0], 6)
    return f, max(lh, 8), max(cw, 6)

FONT, LINE_H, CHAR_W = _load_font()
def screen_cols(): return max(12, DEVICE.width // CHAR_W)
def screen_rows(): return max(3,  DEVICE.height // LINE_H)

# ---------- Shell helpers ----------
def token(s: str) -> str: return s.replace("{P4WN_HOME}", P4WN_HOME)

def shell(cmd: str, timeout: float|None=None):
    env = os.environ.copy(); env["P4WN_HOME"]=P4WN_HOME
    return subprocess.run(token(cmd), shell=True, capture_output=True, text=True,
                          timeout=timeout, cwd=P4WN_HOME, env=env)

def read_status_lines(cmd: str, timeout: float = STATUS_TIMEOUT) -> list[str]:
    try:
        r = shell(cmd, timeout=timeout)
        text = (r.stdout + "\n" + r.stderr).strip("\n")
        lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
        return lines if lines else ["(no output)"]
    except Exception:
        return ["(error)"]

def run_cmd_like(script_or_action: str, label="action"):
    raw = token(script_or_action)
    if os.path.isfile(raw):
        if   raw.endswith(".py"): cmd = f"python3 {raw}"
        elif raw.endswith(".sh"): cmd = f"bash {raw}"
        else:                     cmd = raw
    else:
        cmd = raw
    try:
        r = shell(cmd)
        out = (r.stdout + r.stderr).strip().splitlines()
        tail = "\n".join(out[-2:]) if out else ""
        ok = (r.returncode == 0)
        (LOG_DIR / f"{label}.log").write_text(r.stdout + "\n" + r.stderr)
        msg = ("✓ OK" if ok else "✗ ERR") + (("\n" + tail) if tail else "")
        return ok, msg
    except Exception as e:
        return False, f"✗ ERR\n{e}"

def run_cmd_bg(cmd: str, label: str = "bg"):
    raw = token(cmd)
    logf = (LOG_DIR / f"{label}.log").open("ab", buffering=0)
    try:
        if shutil.which("systemd-run"):
            unit = f"p4wnp1-{label}".replace("/", "_")
            scmd = (
                f'systemd-run --unit={unit} --collect '
                f'--property=StandardOutput=append:{logf.name} '
                f'--property=StandardError=append:{logf.name} -- {raw}'
            )
            subprocess.Popen(scmd, shell=True, cwd=P4WN_HOME)
        else:
            subprocess.Popen(raw, shell=True, cwd=P4WN_HOME,
                             stdout=logf, stderr=logf,
                             preexec_fn=os.setsid, start_new_session=True)
        return True, f"Started in background: {raw}"
    except Exception as e:
        return False, f"✗ BG start failed: {e}"

# ---------- Menu data helpers ----------
def replace_tokens(obj):
    if isinstance(obj, dict):  return {k: replace_tokens(v) for k,v in obj.items()}
    if isinstance(obj, list):  return [replace_tokens(v) for v in obj]
    if isinstance(obj, str):   return token(obj)
    return obj

def title_of(it):   return it.get("name") or it.get("title") or "Item"
def is_action(it):  return isinstance(it.get("action"), str)
def is_script(it):  return isinstance(it.get("script"), str)
def is_submenu(it): return isinstance(it.get("submenu"), list)
def is_selector(it):return isinstance(it.get("selector"), dict)
def is_status(it):  return isinstance(it.get("status_cmd"), str)

def _valid_selector(sel: dict) -> bool:
    ch = sel.get("choices")
    if not isinstance(ch, list) or not sel.get("action_template"): return False
    for c in ch:
        if not isinstance(c, dict): return False
        if not ("value" in c or "value_cmd" in c): return False
    return True

def validate_items(items):
    v=[]
    for it in items:
        if title_of(it).strip().startswith("←"): continue
        if is_submenu(it) or is_action(it) or is_script(it) or is_status(it):
            v.append(it); continue
        if is_selector(it) and _valid_selector(it["selector"]):
            v.append(it); continue
    return v

def load_menu_items():
    try:
        data = json.loads(MENU_CONFIG.read_text())
    except Exception:
        print("[!] Failed to load menu_config.json", file=sys.stderr)
        traceback.print_exc(); sys.exit(1)
    if isinstance(data, list): items = data
    elif isinstance(data, dict):
        if   isinstance(data.get("menu"), list):    items = data["menu"]
        elif isinstance(data.get("submenu"), list): items = data["submenu"]
        else:
            print("[!] menu_config.json must be list or dict with 'menu'/'submenu'", file=sys.stderr); sys.exit(1)
    else:
        print("[!] menu_config.json must be a list or dict", file=sys.stderr); sys.exit(1)
    return validate_items(replace_tokens(items))

# ---------- Choice helpers ----------
def _last(text: str) -> str:
    text = (text or "").strip()
    return text.splitlines()[-1].strip() if text else ""

def choice_value(c: dict) -> str:
    if "value_cmd" in c:
        try:
            r = shell(c["value_cmd"], timeout=STATUS_TIMEOUT)
            return _last(r.stdout + "\n" + r.stderr)
        except Exception:
            return ""
    return str(c.get("value","")).strip()

def choice_label(c: dict) -> str:
    if "label_cmd" in c:
        try:
            r = shell(c["label_cmd"], timeout=STATUS_TIMEOUT)
            lab = _last(r.stdout + "\n" + r.stderr)
            if lab: return lab
        except Exception:
            pass
    if "label" in c: return str(c["label"])
    v = choice_value(c)
    return v if v else "(empty)"

# ---------- UI state ----------
class MenuState:
    def __init__(self, items):
        self.items = items
        self.index = 0
        self.offset = 0
        self.sel_cursor = {}

    def rows(self): return screen_rows()
    def current(self): return self.items[self.index] if self.items else None

    def visible_slice(self, usable_rows=None):
        rows = self.rows() if usable_rows is None else usable_rows
        if self.index < self.offset: self.offset = self.index
        if self.index >= self.offset + rows: self.offset = self.index - rows + 1
        return self.items[self.offset:self.offset + rows]

    def up(self):
        if self.items:
            self.index = (self.index - 1) % len(self.items)

    def down(self):
        if self.items:
            self.index = (self.index + 1) % len(self.items)

    def sel_pos(self, it): return self.sel_cursor.get(id(it), 0)
    def sel_set(self, it, pos):
        ch = it["selector"]["choices"]; self.sel_cursor[id(it)] = pos % len(ch)
    def sel_next(self, it): self.sel_set(it, self.sel_pos(it) + 1)
    def sel_choice(self, it):
        ch = it["selector"]["choices"]; return ch[self.sel_pos(it) % len(ch)]

# ---------- Drawing ----------
def _centered_header(text: str) -> str:
    cols = screen_cols()
    raw = f"== {text} =="
    pad = max(0, (cols - len(raw)) // 2)
    return (" " * pad + raw)[:cols]

def draw_text_lines(lines, hold=0.0):
    cols = screen_cols()
    wrapped=[]
    for ln in lines:
        wrapped += wrap(ln, cols) or [""]
    with canvas(DEVICE) as draw:
        y=0
        for ln in wrapped[:screen_rows()]:
            draw.text((0, y), ln, font=FONT, fill=255)
            y += LINE_H
    if hold>0: time.sleep(hold)

def render_list(state: "MenuState", header_text: str):
    cols = screen_cols()
    rows = screen_rows()
    lines = [_centered_header(header_text)]
    usable_rows = max(0, rows - 1)
    view = state.visible_slice(usable_rows=usable_rows)
    for i, it in enumerate(view, start=state.offset):
        name = title_of(it)
        if is_selector(it):
            lab = choice_label(state.sel_choice(it))
            name = f"{name}: {lab}"
        prefix = "> " if i == state.index else "  "
        lines.append((prefix + name)[:cols*2])
    draw_text_lines(lines)

# ----- Detail view (for status outputs after Select) -----
_detail = None  # dict with {'title': str, 'raw_lines': list[str], 'offset': int}

def detail_open(title: str, raw_lines: list[str]):
    global _detail
    _detail = {"title": title, "raw_lines": raw_lines, "offset": 0}

def detail_close():
    global _detail
    _detail = None

def detail_active() -> bool:
    return _detail is not None

def render_detail():
    cols = screen_cols()
    rows = screen_rows()
    head = "> " + _detail["title"]
    body_wrapped = []
    for ln in _detail["raw_lines"]:
        body_wrapped += wrap(ln, cols) or [""]
    max_body_rows = max(0, rows - 1)
    max_off = max(0, len(body_wrapped) - max_body_rows)
    off = max(0, min(_detail["offset"], max_off))
    page = [head] + body_wrapped[off: off + max_body_rows]
    draw_text_lines(page)
    _detail["offset"] = off

def toast(msg: str, ms: float = TOAST_TIME):
    draw_text_lines(wrap(msg, screen_cols()), hold=ms)

# ---------- Screensaver helpers ----------
# _saver_mode: 0=off, 1=logo shown, 2=powered off
_last_input = time.monotonic()
_saver_mode = 0
_current_header = "Menu"  # track header label
_saver_on  = False        # device hidden flag (backward-compat)

def _low(pin): return GPIO.input(pin) == GPIO.LOW

def _wait_release(pin, timeout=RELEASE_WAIT):
    t0 = time.monotonic()
    while _low(pin):
        time.sleep(0.01)
        if time.monotonic() - t0 > timeout: break

def _toggle_rotate():  # toggle 0 <-> 2 only
    cur = _load_rotation()
    new_rot = 2 if cur != 2 else 0
    _save_rotation(new_rot)
    global DEVICE
    try:
        DEVICE = _make_device(new_rot)
    except Exception as e:
        print(f"[!] Re-init OLED failed after rotate: {e}")

def _render_logo_once():
    # Draws the saver image (if present) scaled and centered.
    try:
        from PIL import ImageOps

        # Search common names & extensions
        candidates = [
            Path(P4WN_HOME) / "oled" / "saver.png",
            Path(P4WN_HOME) / "oled" / "saver.jpg",
            Path(P4WN_HOME) / "oled" / "saver.jpeg",
            Path(P4WN_HOME) / "oled" / "saver.bmp",
            Path(P4WN_HOME) / "oled" / "p4wnp1-o2.png",
            Path(P4WN_HOME) / "oled" / "p4wnp1-o2.jpg",
        ]
        img_path = next((p for p in candidates if p.exists()), None)

        with canvas(DEVICE) as draw:
            if img_path:
                img = Image.open(img_path)

                # Convert to 1-bit, ensure white-on-black for OLED
                img = img.convert("L")  # grayscale
                # OPTIONAL: flip this boolean if your image looks inverted
                INVERT = False
                if INVERT:
                    img = ImageOps.invert(img)
                img = img.point(lambda p: 255 if p >= 128 else 0, mode="1")

                # Scale to fit
                W, H = DEVICE.width, DEVICE.height
                iw, ih = img.size
                scale = min(W/iw, H/ih)
                nw, nh = max(1, int(iw*scale)), max(1, int(ih*scale))
                img = img.resize((nw, nh), Image.LANCZOS)

                # Center
                x = (W - nw) // 2
                y = (H - nh) // 2
                draw.bitmap((x, y), img, fill=255)
            else:
                # Fallback minimal text logo if no file found
                draw.text((0, 0), "P4wnP1 O2", font=FONT, fill=255)
    except Exception:
        pass

def _show_logo():
    global _saver_mode
    if _saver_mode == 1:  # already showing
        return
    try:
        DEVICE.show()
    except Exception:
        pass
    _render_logo_once()
    _saver_mode = 1

def _power_off():
    global _saver_mode
    try:
        DEVICE.hide()
    except Exception:
        pass
    _saver_mode = 2

def _wake_from_saver():
    global _saver_mode
    if _saver_mode == 2:
        try: DEVICE.show()
        except Exception: pass
    _saver_mode = 0

def _peek_logo(duration=SAVER_PEEK_S):
    _show_logo()
    time.sleep(max(0.0, duration))
    _wake_from_saver()

def _idle_tick():
    """Two-stage saver: logo after SAVER_SHOW_AFTER_S, power off after SAVER_POWER_OFF_S."""
    global _saver_mode
    idle = time.monotonic() - _last_input
    if idle >= SAVER_POWER_OFF_S and _saver_mode != 2:
        _power_off()
    elif idle >= SAVER_SHOW_AFTER_S and _saver_mode == 0:
        _show_logo()

def _mark_input():
    global _last_input
    _last_input = time.monotonic()
    if _saver_mode:
        _wake_from_saver()

# ---------- Input (debounced; rotation-aware mapping) ----------
def read_event():
    """Return one of: 'up','down','enter','back','sel-cycle','rotate', or None."""
    rot = _load_rotation()

    # Map side keys
    if rot == 2:
        if _low(KEY1):
            t0 = time.monotonic()
            while _low(KEY1):
                time.sleep(0.02)
                if time.monotonic() - t0 >= LONG_PRESS_S:
                    _wait_release(KEY1); _mark_input(); return 'rotate'
            time.sleep(DEBOUNCE); _mark_input(); return 'sel-cycle'
        if _low(KEY2):
            time.sleep(DEBOUNCE); _wait_release(KEY2); _mark_input(); return 'back'
        if _low(KEY3):
            time.sleep(DEBOUNCE); _wait_release(KEY3); _mark_input(); return 'enter'
    else:
        if _low(KEY3):
            t0 = time.monotonic()
            while _low(KEY3):
                time.sleep(0.02)
                if time.monotonic() - t0 >= LONG_PRESS_S:
                    _wait_release(KEY3); _mark_input(); return 'rotate'
            time.sleep(DEBOUNCE); _mark_input(); return 'sel-cycle'
        if _low(KEY2):
            time.sleep(DEBOUNCE); _wait_release(KEY2); _mark_input(); return 'back'
        if _low(KEY1):
            time.sleep(DEBOUNCE); _wait_release(KEY1); _mark_input(); return 'enter'

    # Joystick up/down — **flip when ROT==0**
    if _low(JOY_UP):
        time.sleep(DEBOUNCE); _wait_release(JOY_UP); _mark_input()
        return 'down' if rot == 0 else 'up'
    if _low(JOY_DOWN):
        time.sleep(DEBOUNCE); _wait_release(JOY_DOWN); _mark_input()
        return 'up' if rot == 0 else 'down'

    return None

# ---------- Exec ----------
def exec_item(it):
    if is_status(it):
        lines = read_status_lines(it["status_cmd"])
        detail_open(title_of(it), lines)
        render_detail()
        return

    label = title_of(it).replace(" ", "_")
    bg = bool(it.get("background"))

    def _resolve_cmd():
        if is_action(it):
            return it["action"]
        if is_script(it):
            path = token(it["script"])
            if os.path.isfile(path):
                if   path.endswith(".py"): return f"python3 {path}"
                if   path.endswith(".sh"): return f"bash {path}"
            return path
        return None

    cmd = _resolve_cmd()
    if not cmd:
        toast("Unknown item"); return

    if bg:
        ok, msg = run_cmd_bg(cmd, label)
        toast(msg)
    else:
        ok, msg = run_cmd_like(cmd, label)
        toast(msg)

# ---------- Main ----------
def main():
    items_root = load_menu_items()
    stack = [MenuState(items_root)]
    header_stack = ["Menu"]  # keep current header for centering
    global _current_header
    _current_header = header_stack[-1]

    try:
        last_mtime = MENU_CONFIG.stat().st_mtime
    except Exception:
        last_mtime = 0

    render_list(stack[-1], header_stack[-1])

    while True:
        _idle_tick()  # manage screensaver stages

        # hot-reload at root when NOT in detail view
        try:
            mt = MENU_CONFIG.stat().st_mtime
            if mt != last_mtime and not detail_active():
                last_mtime = mt
                stack[0] = MenuState(load_menu_items())
                header_stack[0] = "Menu"
                if len(stack) == 1 and _saver_mode == 0:
                    render_list(stack[-1], header_stack[-1])
        except Exception:
            pass

        ev = read_event()
        if ev is None:
            time.sleep(0.03)
            continue

        if detail_active():
            if ev == 'rotate':
                _toggle_rotate(); render_detail(); continue
            if ev == 'back':
                detail_close(); render_list(stack[-1], header_stack[-1]); continue
            if ev in ('up','down'):
                cols = screen_cols(); rows = screen_rows()
                body_wrapped=[]
                for ln in _detail["raw_lines"]:
                    body_wrapped += wrap(ln, cols) or [""]
                max_body_rows = max(0, rows - 1)
                max_off = max(0, len(body_wrapped) - max_body_rows)
                if ev == 'up':
                    _detail["offset"] = max(0, _detail["offset"] - 1)
                else:
                    _detail["offset"] = min(max_off, _detail["offset"] + 1)
                render_detail(); continue
            # ignore enter/sel-cycle while in detail
            continue

        # Normal list navigation
        st = stack[-1]
        cur = st.current()
        _current_header = header_stack[-1]

        if ev == 'rotate':
            _toggle_rotate()
            toast(f"Rotate={_load_rotation()}")
            if _saver_mode == 0:
                render_list(st, _current_header)
            continue

        if ev == 'up':   st.up();   render_list(st, _current_header); continue
        if ev == 'down': st.down(); render_list(st, _current_header); continue

        if ev == 'back':
            if len(stack) > 1:
                stack.pop(); header_stack.pop()
                render_list(stack[-1], header_stack[-1])
            else:
                # At top: show the logo briefly instead of a text toast
                _peek_logo(SAVER_PEEK_S)
                render_list(st, header_stack[-1])
            continue

        if ev == 'sel-cycle':
            if cur and is_selector(cur):
                st.sel_next(cur); render_list(st, _current_header)
            else:
                toast("Hold to rotate"); render_list(st, _current_header)
            continue

        if ev == 'enter':
            if not cur: continue
            if is_selector(cur):
                ch   = st.sel_choice(cur)
                val  = choice_value(ch)
                disp = choice_label(ch)
                cmd  = cur["selector"]["action_template"].replace("{value}", str(val)).replace("{P4WN_HOME}", P4WN_HOME)
                toast(run_cmd_like(cmd, label=f"{title_of(cur)}_{disp}".replace(" ","_"))[1])
                render_list(st, _current_header); continue
            if is_submenu(cur):
                sub = validate_items(cur["submenu"])
                stack.append(MenuState(sub))
                header_stack.append(title_of(cur))
                render_list(stack[-1], header_stack[-1]); continue
            exec_item(cur)
            if not detail_active():
                render_list(st, _current_header)
            continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        try: GPIO.cleanup()
        except Exception: pass
