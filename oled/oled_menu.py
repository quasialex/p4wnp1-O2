#!/usr/bin/env python3
# P4wnP1-O2 OLED menu — Waveshare 1.3" SPI SH1106 (hard-coded)
# Rotation-aware controls:
#   ROT=2 (180°):  KEY3=Select, KEY2=Back, KEY1=Rotate(long), KEY1 short = selector cycle
#   ROT=0 (0°):    KEY1=Select, KEY2=Back, KEY3=Rotate(long), KEY3 short = selector cycle
# Joystick: up/down only. **Flipped when ROT=0** so UP always feels like UP.

import json, subprocess, os, sys, time, traceback
import shlex, signal, shutil
from pathlib import Path
from textwrap import wrap

import RPi.GPIO as GPIO
from PIL import ImageFont
from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.oled.device import sh1106, ssd1306

# ---------- Paths / constants ----------
P4WN_HOME    = os.getenv("P4WN_HOME", "/opt/p4wnp1")
MENU_CONFIG  = Path(P4WN_HOME) / "oled" / "menu_config.json"
ROT_FILE     = Path(P4WN_HOME) / "oled" / "rotation.json"
LOG_DIR      = Path(P4WN_HOME) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

IDLE_TIMEOUT_S   = 10.0
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
# Mapping is rotation-aware in read_event()
KEY1, KEY2, KEY3 = 21, 20, 16

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
for p in (JOY_UP, JOY_DOWN, JOY_LEFT, JOY_RIGHT, JOY_CENTER, KEY1, KEY2, KEY3):
    GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# --- Dynamic header (lightweight) ---
HEADER_TTL = 1.0  # seconds to cache command output to avoid thrashing
_header_cache = {}  # {(cmd:str): (ts:float, lastline:str)}

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

# ---------- Font / layout (smaller if possible) ----------
def _load_font():
    # Try tiny monospace TTF for more columns; fallback to PIL bitmap
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
    # Fallback bitmap font
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

def _last_nonempty_line(s: str) -> str:
    s = (s or "").strip("\n")
    for ln in s.splitlines()[::-1]:
        ln = ln.strip()
        if ln:
            return ln
    return ""

def eval_header_cached(prefix: str | None, cmd: str | None) -> str | None:
    """Return 'prefix + last stdout line', stderr ignored, cached for HEADER_TTL."""
    if not cmd:
        return None
    now = time.monotonic()
    cached = _header_cache.get(cmd)
    if cached and (now - cached[0]) < HEADER_TTL:
        line = cached[1]
    else:
        try:
            r = shell(cmd, timeout=STATUS_TIMEOUT)
            line = _last_nonempty_line(r.stdout) or "(no output)"   # stdout only
        except Exception:
            line = "(error)"
        _header_cache[cmd] = (now, line)
    return f"{prefix or ''}{line}"

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

import shlex, signal

def run_cmd_bg(cmd: str, label: str = "bg"):
    """
    Detach a long-running command (listener/daemon) so the OLED menu doesn't block.
    Stdout/err go to logs/<label>.log.
    """
    raw = token(cmd)
    logf = (LOG_DIR / f"{label}.log").open("ab", buffering=0)
    try:
        # Prefer systemd-run (if available) so scope is tracked by systemd
        if shutil.which("systemd-run"):
            # --collect cleans the transient unit after exit
            unit = f"p4wnp1-{label}".replace("/", "_")
            scmd = f'systemd-run --unit={unit} --collect --property=StandardOutput=append:{logf.name} ' \
                   f'--property=StandardError=append:{logf.name} -- {raw}'
            subprocess.Popen(scmd, shell=True, cwd=P4WN_HOME)
        else:
            # Fallback: double-fork via setsid
            subprocess.Popen(raw, shell=True, cwd=P4WN_HOME,
                             stdout=logf, stderr=logf,
                             preexec_fn=os.setsid, start_new_session=True)
        return True, f"Started in background: {raw}"
    except Exception as e:
        return False, f"✗ BG start failed: {e}"

def header_value(prefix: str|None, cmd: str|None) -> str|None:
    """Return 'prefix + value' using stdout only (ignore stderr), cached for HEADER_TTL."""
    if not cmd:
        return None
    now = time.monotonic()
    cached = _header_cache.get(cmd)
    if cached and (now - cached[0]) < HEADER_TTL:
        line = cached[1]
    else:
        try:
            r = shell(cmd, timeout=STATUS_TIMEOUT)
            line = _last_nonempty_line(r.stdout)  # stdout only to avoid /bin/sh errors on screen
            if not line:
                line = "(no output)"
        except Exception:
            line = "(error)"
        _header_cache[cmd] = (now, line)
    return f"{prefix or ''}{line}"

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
        # Hide any "← Back" entries; we have a real Back key (KEY2)
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
        self.header_meta = None   # NEW: tuple(prefix, cmd) for this menu, or None

    def rows(self): return screen_rows()
    def current(self): return self.items[self.index] if self.items else None

    def visible_slice(self):
        rows = self.rows()
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

def render_list(state: "MenuState"):
    cols = screen_cols()

    # If this menu itself has a header, draw it as the first, non-selectable line
    header_lines = []
    if state.header_meta:
        hp, hc = state.header_meta
        hv = header_value(hp, hc)
        if hv:
            header_lines.append(hv[:cols*2])  # clamp width; we already wrap later

    view = state.visible_slice()
    lines = []

    # Draw list items
    for i, it in enumerate(view, start=state.offset):
        name = title_of(it)
        if is_selector(it):
            lab = choice_label(state.sel_choice(it))
            name = f"{name}: {lab}"
        prefix = "> " if i == state.index else "  "
        lines.append((prefix + name)[:cols*2])

    # If we are hovering an item in the parent menu that has header_cmd/prefix, show it
    cur = state.current()
    if cur and is_submenu(cur) and ("header_cmd" in cur or "header_prefix" in cur):
        hv = header_value(cur.get("header_prefix"), cur.get("header_cmd"))
        if hv:
            # Append at the end (like your screenshots), still non-selectable
            lines.append(hv[:cols*2])

    draw_text_lines(header_lines + lines)

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
    # wrap body lines fresh each draw (adapts to rotation/font changes)
    body_wrapped = []
    for ln in _detail["raw_lines"]:
        body_wrapped += wrap(ln, cols) or [""]
    max_body_rows = max(0, rows - 1)
    max_off = max(0, len(body_wrapped) - max_body_rows)
    off = max(0, min(_detail["offset"], max_off))

    page = [head] + body_wrapped[off: off + max_body_rows]
    draw_text_lines(page)

    # clamp stored offset
    _detail["offset"] = off

def toast(msg: str, ms: float = TOAST_TIME):
    draw_text_lines(wrap(msg, screen_cols()), hold=ms)

# ---------- Input (debounced, idle & saver, rotation-aware mapping) ----------
_last_input = time.monotonic()
_saver_on   = False

def _low(pin): return GPIO.input(pin) == GPIO.LOW

def _wait_release(pin, timeout=RELEASE_WAIT):
    t0 = time.monotonic()
    while _low(pin):
        time.sleep(0.01)
        if time.monotonic() - t0 > timeout: break

def _wake_if_saver():
    global _saver_on
    if _saver_on:
        try: DEVICE.show()
        except Exception: pass
        _saver_on = False

def _maybe_saver():
    global _saver_on
    if (time.monotonic() - _last_input) >= IDLE_TIMEOUT_S and not _saver_on:
        try: DEVICE.hide()
        except Exception: pass
        _saver_on = True

def _toggle_rotate():  # toggle 0 <-> 2 only
    cur = _load_rotation()
    new_rot = 2 if cur != 2 else 0
    _save_rotation(new_rot)
    global DEVICE
    try:
        DEVICE = _make_device(new_rot)
    except Exception as e:
        print(f"[!] Re-init OLED failed after rotate: {e}")

def read_event():
    """Return one of: 'up','down','enter','back','sel-cycle','rotate', or None.
       Mapping is based on current rotation (0 vs 2).
       Joystick UP/DOWN are **flipped when ROT==0** so UI always feels consistent."""
    global _last_input
    rot = _load_rotation()

    # Map side keys
    if rot == 2:
        # ROT=2: KEY3=Enter, KEY2=Back, KEY1=Rotate(long)/Cycle(short)
        if _low(KEY1):
            t0 = time.monotonic()
            while _low(KEY1):
                time.sleep(0.02)
                if time.monotonic() - t0 >= LONG_PRESS_S:
                    _wait_release(KEY1); _last_input=time.monotonic(); _wake_if_saver(); return 'rotate'
            time.sleep(DEBOUNCE); _last_input=time.monotonic(); _wake_if_saver(); return 'sel-cycle'
        if _low(KEY2):
            time.sleep(DEBOUNCE); _wait_release(KEY2); _last_input=time.monotonic(); _wake_if_saver(); return 'back'
        if _low(KEY3):
            time.sleep(DEBOUNCE); _wait_release(KEY3); _last_input=time.monotonic(); _wake_if_saver(); return 'enter'
    else:
        # ROT=0: KEY1=Enter, KEY2=Back, KEY3=Rotate(long)/Cycle(short)
        if _low(KEY3):
            t0 = time.monotonic()
            while _low(KEY3):
                time.sleep(0.02)
                if time.monotonic() - t0 >= LONG_PRESS_S:
                    _wait_release(KEY3); _last_input=time.monotonic(); _wake_if_saver(); return 'rotate'
            time.sleep(DEBOUNCE); _last_input=time.monotonic(); _wake_if_saver(); return 'sel-cycle'
        if _low(KEY2):
            time.sleep(DEBOUNCE); _wait_release(KEY2); _last_input=time.monotonic(); _wake_if_saver(); return 'back'
        if _low(KEY1):
            time.sleep(DEBOUNCE); _wait_release(KEY1); _last_input=time.monotonic(); _wake_if_saver(); return 'enter'

    # Joystick up/down — **flip when ROT==0**
    if _low(JOY_UP):
        time.sleep(DEBOUNCE); _wait_release(JOY_UP); _last_input=time.monotonic(); _wake_if_saver()
        return 'down' if rot == 0 else 'up'
    if _low(JOY_DOWN):
        time.sleep(DEBOUNCE); _wait_release(JOY_DOWN); _last_input=time.monotonic(); _wake_if_saver()
        return 'up' if rot == 0 else 'down'

    # ignore left/right/center
    return None

# ---------- Exec ----------
def exec_item(it):
    # Status items open a scrollable detail view (only on Select)
    if is_status(it):
        lines = read_status_lines(it["status_cmd"])
        detail_open(title_of(it), lines)
        render_detail()
        return

    label = title_of(it).replace(" ", "_")
    bg = bool(it.get("background"))

    # Choose the resolver used by both "action" and "script"
    def _resolve_cmd():
        if is_action(it):
            return it["action"]
        if is_script(it):
            path = token(it["script"])
            # If script path isn't a file, treat it as a shell command
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
    root = load_menu_items()
    stack = [MenuState(root)]
    try:
        last_mtime = MENU_CONFIG.stat().st_mtime
    except Exception:
        last_mtime = 0

    render_list(stack[-1])

    while True:
        _maybe_saver()

        # hot-reload at root when NOT in detail view
        try:
            mt = MENU_CONFIG.stat().st_mtime
            if mt != last_mtime and not detail_active():
                last_mtime = mt
                stack[0] = MenuState(load_menu_items())
                if len(stack) == 1:
                    render_list(stack[-1])
        except Exception:
            pass

        ev = read_event()
        if ev is None:
            time.sleep(0.03)
            continue

        if detail_active():
            # In detail view: up/down scroll, back exits, rotate re-render
            if ev == 'rotate':
                _toggle_rotate(); render_detail(); continue
            if ev == 'back':
                detail_close(); render_list(stack[-1]); continue
            if ev == 'up' or ev == 'down':
                # recompute wrapped length to know bounds
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
            if ev in ('enter','sel-cycle'):
                # ignore selects while in detail view
                render_detail(); continue
            # anything else: continue loop
            continue

        # Normal list navigation
        st = stack[-1]
        cur = st.current()

        if ev == 'rotate':
            _toggle_rotate()
            toast(f"Rotate={_load_rotation()}")
            render_list(st)
            continue

        if ev == 'up':   st.up();   render_list(st); continue
        if ev == 'down': st.down(); render_list(st); continue

        if ev == 'back':
            if len(stack) > 1:
                stack.pop()
                render_list(stack[-1])
            else:
                toast("Top menu")
                render_list(st)
            continue

        if ev == 'sel-cycle':
            if cur and is_selector(cur):
                st.sel_next(cur); render_list(st)
            else:
                toast("Hold to rotate"); render_list(st)
            continue

        if ev == 'enter':
            if not cur: continue
            if is_selector(cur):
                ch   = st.sel_choice(cur)
                val  = choice_value(ch)
                disp = choice_label(ch)
                cmd  = cur["selector"]["action_template"].replace("{value}", str(val)).replace("{P4WN_HOME}", P4WN_HOME)
                toast(run_cmd_like(cmd, label=f"{title_of(cur)}_{disp}".replace(" ","_"))[1])
                render_list(st); continue
            if is_submenu(cur):
                sub = validate_items(cur["submenu"])
                sub_state = MenuState(sub)
                # NEW: pin this submenu's header (non-selectable first line)
                sub_state.header_meta = (cur.get("header_prefix"), cur.get("header_cmd"))
                stack.append(sub_state)
                render_list(stack[-1]); continue
            exec_item(cur);  # may open detail view or run action/script
            if not detail_active():
                render_list(st)
            continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        try: GPIO.cleanup()
        except Exception: pass
