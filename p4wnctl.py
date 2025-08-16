#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
import curses

# ======= Paths / constants =======
P4WN_HOME = Path(os.environ.get("P4WN_HOME", "/opt/p4wnp1"))
HOOKS = P4WN_HOME / "hooks"
CONFIG = P4WN_HOME / "config"
USB_GADGET = Path("/sys/kernel/config/usb_gadget/p4wnp1")
ACTIVE_PAYLOAD_FILE = CONFIG / "active_payload"

WEBUI_UNIT = "p4wnp1-webui.service"
WEBUI_OVERRIDE_DIR = Path(f"/etc/systemd/system/{WEBUI_UNIT}.d")
WEBUI_OVERRIDE_FILE = WEBUI_OVERRIDE_DIR / "override.conf"

# ======= Small helpers =======
def sh(cmd: str, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)

def need_root():
    if os.geteuid() != 0:
        print("This command requires root (sudo).", file=sys.stderr)
        sys.exit(2)

def systemctl(*args) -> subprocess.CompletedProcess:
    return sh("systemctl " + " ".join(args), check=False)

def usb_preflight():
    sh("modprobe configfs || true", check=False)
    sh("mount -t configfs none /sys/kernel/config || true", check=False)
    sh("modprobe dwc2 || true", check=False)
    sh("modprobe libcomposite || true", check=False)
    uds = Path("/sys/class/udc")
    if not uds.exists() or not any(uds.iterdir()):
        print("[!] No USB Device Controller under /sys/class/udc.\n"
              "    Add 'dtoverlay=dwc2' to /boot/config.txt (or /boot/firmware/config.txt) and reboot.",
              file=sys.stderr)
        sys.exit(3)

def last_line(txt: str) -> str:
    for ln in reversed((txt or "").splitlines()):
        ln = ln.strip()
        if ln:
            return ln
    return ""

# ======= USB =======
def usb_status_text() -> str:
    if not USB_GADGET.exists():
        return "USB: none"
    funcs = USB_GADGET / "functions"
    if not funcs.exists():
        return "USB: none"
    hid   = (funcs / "hid.usb0").exists()
    rndis = (funcs / "rndis.usb0").exists()
    ecm   = (funcs / "ecm.usb0").exists()
    msd   = (funcs / "mass_storage.usb0").exists()

    if msd and (hid and (rndis or ecm)):
        mode = "hid_storage_net"
    elif hid and (rndis or ecm):
        mode = "hid_net_only"
    elif msd and not any([hid, rndis, ecm]):
        mode = "storage_only"
    else:
        mode = "custom/unknown"

    parts = []
    if hid: parts.append("HID")
    if rndis or ecm: parts.append("NET")
    if msd: parts.append("MSD")
    lines = [f"USB: {mode} ({'+'.join(parts) if parts else 'none'})"]
    for c in ["c.1", "c.2"]:
        cdir = USB_GADGET / "configs" / c
        if cdir.exists():
            links = []
            for name in ["hid.usb0","rndis.usb0","ecm.usb0","mass_storage.usb0"]:
                if (cdir / name).exists(): links.append(name.split(".")[0])
            lines.append(f" {c}: {('+'.join(links) if links else 'n/a')}")
    return "\n".join(lines)

def usb_status(_args=None) -> int:
    print(usb_status_text()); return 0

def usb_set(mode: str) -> int:
    need_root()
    usb_preflight()
    script = {
        "hid_net_only":     CONFIG / "usb_gadgets" / "hid_net_only.sh",
        "hid_storage_net":  CONFIG / "usb_gadgets" / "hid_storage_net.sh",
        "storage_only":     CONFIG / "usb_gadgets" / "storage_only.sh",
    }.get(mode)
    if not script or not script.exists():
        print(f"Unknown mode or missing script: {mode}", file=sys.stderr)
        return 4
    reset = HOOKS / "gadget_reset.sh"
    if reset.exists():
        sh(f"bash {reset}", check=False)
    cp = sh(f"bash {script}", check=False)
    sys.stdout.write(cp.stdout); sys.stderr.write(cp.stderr)
    return cp.returncode

USB_CHOICES = [
    ("HID + NET", "hid_net_only"),
    ("HID + NET + MSD", "hid_storage_net"),
    ("Storage Only", "storage_only")
]

# ======= Payloads =======
def _payload_candidates(name: str):
    return [
        P4WN_HOME / f"payloads/{name}.sh",
        P4WN_HOME / f"payloads/hid/{name}.sh",
        P4WN_HOME / f"payloads/network/{name}.sh",
        P4WN_HOME / f"payloads/listeners/{name}.sh",
        P4WN_HOME / f"payloads/shell/{name}.sh",
    ]

def resolve_payload(name_or_path: str) -> Path | None:
    p = Path(name_or_path)
    if p.is_file():
        return p
    for c in _payload_candidates(name_or_path):
        if c.exists():
            return c
    return None

def payload_status_text() -> str:
    if not ACTIVE_PAYLOAD_FILE.exists(): return "Payload: none"
    val = ACTIVE_PAYLOAD_FILE.read_text().strip()
    if not val: return "Payload: none"
    resolved = resolve_payload(val)
    if resolved is None:
        return f"Payload: {Path(val).stem} (missing file)"
    if Path(val) != resolved:
        try: ACTIVE_PAYLOAD_FILE.write_text(str(resolved))
        except Exception: pass
    return f"Payload: {resolved.stem}"

def payload_status(_args=None) -> int:
    print(payload_status_text()); return 0

def payload_list(_args=None) -> int:
    seen = set()
    roots = [
        P4WN_HOME / "payloads",
        P4WN_HOME / "payloads/hid",
        P4WN_HOME / "payloads/network",
        P4WN_HOME / "payloads/listeners",
        P4WN_HOME / "payloads/shell",
    ]
    for r in roots:
        if not r.exists(): continue
        for p in sorted(r.glob("*.sh")):
            name = p.stem
            if name in seen: continue
            seen.add(name)
            print(name)
    if not seen: print("(no payloads found)")
    return 0

def payload_set(name: str) -> int:
    need_root()
    p = resolve_payload(name)
    if p is None:
        print(f"Payload not found: {name}", file=sys.stderr); return 5
    ACTIVE_PAYLOAD_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_PAYLOAD_FILE.write_text(str(p))
    print(f"Active payload set: {p.stem}")
    return 0

def get_payload_choices():
    # Build selector choices dynamically
    names = []
    roots = [
        P4WN_HOME / "payloads",
        P4WN_HOME / "payloads/hid",
        P4WN_HOME / "payloads/network",
        P4WN_HOME / "payloads/listeners",
        P4WN_HOME / "payloads/shell",
    ]
    for r in roots:
        if not r.exists(): continue
        for p in sorted(r.glob("*.sh")):
            n = p.stem
            if n not in names: names.append(n)
    if not names:
        names = ["reverse_shell","autorun_powershell","test_typing"]
    return [(n, n) for n in names]

# ======= Web UI =======
def web_status_text() -> str:
    st = systemctl("is-active", WEBUI_UNIT).stdout.strip() or "unknown"
    en = systemctl("is-enabled", WEBUI_UNIT).stdout.strip() or "disabled?"
    host = port = None
    if WEBUI_OVERRIDE_FILE.exists():
        text = WEBUI_OVERRIDE_FILE.read_text()
        for line in text.splitlines():
            if "WEBUI_HOST=" in line:
                host = line.split("WEBUI_HOST=")[-1].strip().strip('"')
            if "WEBUI_PORT=" in line:
                try: port = int(line.split("WEBUI_PORT=")[-1].split('"')[0].strip())
                except Exception: pass
    if host or port:
        return f"WebUI: {st} ({en})  {host or '-'}:{port or '-'}"
    return f"WebUI: {st} ({en})  (default bind)"

def web_status(_args=None) -> int:
    print(web_status_text()); return 0

def web_start():   need_root(); return systemctl("start", WEBUI_UNIT).returncode
def web_stop():    need_root(); return systemctl("stop", WEBUI_UNIT).returncode
def web_restart(): need_root(); return systemctl("restart", WEBUI_UNIT).returncode
def web_enable():  need_root(); return systemctl("enable", WEBUI_UNIT).returncode
def web_disable(): need_root(); return systemctl("disable", WEBUI_UNIT).returncode

def _web_override_write(host: str, port: int):
    need_root()
    WEBUI_OVERRIDE_DIR.mkdir(parents=True, exist_ok=True)
    content = dedent(f"""\
        [Service]
        Environment="WEBUI_HOST={host}" "WEBUI_PORT={port}"
    """)
    WEBUI_OVERRIDE_FILE.write_text(content)
    systemctl("daemon-reload")
    systemctl("restart", WEBUI_UNIT)

def web_config_show(_args=None) -> int:
    if WEBUI_OVERRIDE_FILE.exists():
        print(WEBUI_OVERRIDE_FILE.read_text().rstrip())
    else:
        print("(no override set; service defaults in effect)")
    return 0

def web_config_set(host: str, port: int) -> int:
    _web_override_write(host, port)
    print(f"WebUI configured: {host}:{port} (override written)")
    return 0

WEB_BIND_CHOICES = [
    ("127.0.0.1:8080", ("127.0.0.1", 8080)),
    ("10.13.37.1:8080", ("10.13.37.1", 8080)),
    ("0.0.0.0:8080", ("0.0.0.0", 8080)),
    ("127.0.0.1:8000", ("127.0.0.1", 8000)),
    ("0.0.0.0:9090", ("0.0.0.0", 9090)),
]

# ======= IP =======
def ip_text() -> str:
    """
    List IPv4 for all relevant NICs with smart ordering:
      1) USB-backed (sysfs path contains '/usb/') e.g., usb0, rndis0, ecm0, enx...
      2) Wired (eth*, en*)
      3) Wi-Fi (wlan*)
      4) Others (if any)
    Show operstate and 'no ip' when applicable.
    """
    base = Path("/sys/class/net")
    ifaces = [p.name for p in base.iterdir() if p.is_dir() and p.name != "lo"]

    def is_usb(iface: str) -> bool:
        # A USB NIC will have a device symlink path containing '/usb/'
        dev = base / iface / "device"
        try:
            target = os.readlink(dev)  # relative symlink
            # resolve to absolute for certainty
            full = (dev.parent / target).resolve()
            return "/usb" in str(full)
        except OSError:
            return False

    def oper_state(iface: str) -> str:
        try:
            return (base / iface / "operstate").read_text().strip()
        except Exception:
            return "unknown"

    # rank: USB first, then eth/en, then wlan, then others
    def rank(iface: str) -> tuple:
        name = iface.lower()
        if is_usb(iface):               pri = 0
        elif name.startswith(("eth","en")): pri = 1
        elif name.startswith("wlan"):   pri = 2
        else:                           pri = 3
        return (pri, name)

    ifaces.sort(key=rank)

    lines = []
    for iface in ifaces:
        state = oper_state(iface)
        cp = sh(f"ip -4 addr show {iface}", check=False)
        ipline = ""
        if "inet " in cp.stdout:
            # take first IPv4
            for ln in cp.stdout.splitlines():
                ln = ln.strip()
                if ln.startswith("inet "):
                    # looks like: "inet 10.13.37.1/24 brd ... scope global ..."
                    parts = ln.split()
                    if len(parts) > 1:
                        ipline = parts[1]  # CIDR
                        break
        if ipline:
            lines.append(f"{iface} ({state}): {ipline}")
        else:
            lines.append(f"{iface} ({state}): no ip")
    return "\n".join(lines) if lines else "No interfaces"

def ip_show(_args=None) -> int:
    print(ip_text())
    return 0

# ======= Minimal help screens =======
MAIN_HELP = dedent("""\
P4wnP1-O2 control CLI

Subcommands:
  usb         USB gadget controls
  payload     Payload controls
  web         Web UI controls (port/host, start/stop, enable/disable)
  ip          Show IP addresses
  menu        Interactive menu (arrow keys)
""")

USB_HELP = dedent("""\
USB gadget controls
-------------------
Commands:
  usb status
  usb set {hid_net_only|hid_storage_net|storage_only}

Examples:
  p4wnctl usb status
  sudo p4wnctl usb set hid_net_only
  sudo p4wnctl usb set hid_storage_net
""")

PAYLOAD_HELP = dedent("""\
Payload controls
----------------
Commands:
  payload status
  payload list
  payload set <name>

Examples:
  p4wnctl payload status
  p4wnctl payload list
  sudo p4wnctl payload set reverse_shell
""")

WEB_HELP = dedent(f"""\
Web UI controls
---------------
Commands:
  web status
  web start | stop | restart
  web enable | disable
  web config show
  web config set --host <ip> --port <n>

Notes:
  • Config writes systemd override at:
    {WEBUI_OVERRIDE_FILE}
  • Flask app should read WEBUI_HOST / WEBUI_PORT env vars.

Examples:
  p4wnctl web status
  sudo p4wnctl web config set --host 127.0.0.1 --port 8080
  sudo p4wnctl web restart
""")

# ======= Curses TUI (arrow-driven) =======
class MenuItem:
    def __init__(self, label, kind, data=None, status_fn=None):
        self.label = label
        self.kind = kind  # 'submenu' | 'action' | 'selector' | 'status'
        self.data = data or {}
        self.status_fn = status_fn  # callable -> str (one-liner or small block)

class MenuState:
    def __init__(self, title, items):
        self.title = title
        self.items = items
        self.idx = 0
        self.sel_idx = {}  # selector cursor per item

    def current(self):
        if not self.items: return None
        return self.items[self.idx]

def draw_menu(stdscr, state: MenuState, toast: str = ""):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    def add(y, x, s, attr=0):
        if 0 <= y < h:
            stdscr.addnstr(y, x, s, max(1, w-1-x), attr)

    add(0, 0, state.title, curses.A_BOLD)
    add(1, 0, "↑↓ move   ← back   →/Enter select", curses.A_DIM)

    # status block (from current item) — show multiple lines
    status_lines = []
    cur = state.current()
    if cur and cur.status_fn:
        try:
            block = cur.status_fn() or ""
            status_lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        except Exception:
            status_lines = []

    # print up to 3 status lines under the header
    max_status = min(3, max(0, h - 8))  # avoid overflow in tiny terminals
    used = 0
    for i, ln in enumerate(status_lines[:max_status]):
        add(2 + i, 0, ln)
        used += 1

    top = 4 + used

    for i, it in enumerate(state.items):
        prefix = "  "
        if i == state.idx:
            prefix = "> "
        label = it.label
        if it.kind == "selector":
            # show current choice
            curpos = state.sel_idx.get(id(it), 0)
            choices = it.data.get("choices", [])
            if choices:
                lab = choices[curpos][0]
                label = f"{label}: {lab}"
        add(top + i, 0, prefix + label, curses.A_REVERSE if i == state.idx else 0)

    # toast area
    if toast:
        add(h-2, 0, toast[:w-1], curses.A_BOLD)
    stdscr.refresh()

def tui_menu(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)

    # Build menu tree
    usb_sub = MenuState("USB", [
        MenuItem("Current", "status", status_fn=usb_status_text),
        MenuItem("Select Mode", "selector", data={"choices": USB_CHOICES}),
        MenuItem("Apply: HID + NET", "action", data={"fn": lambda: usb_set("hid_net_only")}),
        MenuItem("Apply: HID + NET + MSD", "action", data={"fn": lambda: usb_set("hid_storage_net")}),
        MenuItem("Apply: Storage Only", "action", data={"fn": lambda: usb_set("storage_only")}),
    ])

    def payload_set_cur(name): return lambda: payload_set(name)

    payload_choices = get_payload_choices()
    payload_sub = MenuState("Payloads", [
        MenuItem("Current", "status", status_fn=payload_status_text),
        MenuItem("Select Payload", "selector", data={"choices": payload_choices}),
        # convenience applies:
        *[MenuItem(f"Apply: {lab}", "action", data={"fn": payload_set_cur(val)}) for lab, val in payload_choices[:6]],
    ])

    web_sub = MenuState("Web UI", [
        MenuItem("Status", "status", status_fn=web_status_text),
        MenuItem("Bind (host:port)", "selector", data={"choices": WEB_BIND_CHOICES}),
        MenuItem("Start", "action", data={"fn": web_start}),
        MenuItem("Stop", "action", data={"fn": web_stop}),
        MenuItem("Restart", "action", data={"fn": web_restart}),
        MenuItem("Enable", "action", data={"fn": web_enable}),
        MenuItem("Disable", "action", data={"fn": web_disable}),
        MenuItem("Show override", "action", data={"fn": lambda: web_config_show(None)}),
    ])

    root = MenuState("P4wnP1-O2", [
        MenuItem("USB", "submenu", data={"submenu": usb_sub}),
        MenuItem("Payloads", "submenu", data={"submenu": payload_sub}),
        MenuItem("Web UI", "submenu", data={"submenu": web_sub}),
        MenuItem("IP", "status", status_fn=ip_text),
        MenuItem("Quit", "action", data={"fn": lambda: "QUIT"}),
    ])

    stack = [root]
    toast = ""

    while True:
        draw_menu(stdscr, stack[-1], toast)
        toast = ""
        k = stdscr.getch()

        if k in (curses.KEY_UP, ord('k')):
            st = stack[-1]; st.idx = (st.idx - 1) % len(st.items)
        elif k in (curses.KEY_DOWN, ord('j')):
            st = stack[-1]; st.idx = (st.idx + 1) % len(st.items)
        elif k in (curses.KEY_LEFT, curses.KEY_BACKSPACE, 127, ord('h')):
            # back OR selector-left
            st = stack[-1]
            cur = st.current()
            if cur and cur.kind == "selector":
                pos = st.sel_idx.get(id(cur), 0)
                choices = cur.data.get("choices", [])
                if choices:
                    st.sel_idx[id(cur)] = (pos - 1) % len(choices)
            elif len(stack) > 1:
                stack.pop()
        elif k in (curses.KEY_RIGHT, curses.KEY_ENTER, 10, 13, ord('l')):
            st = stack[-1]
            cur = st.current()
            if not cur:
                continue
            if cur.kind == "submenu":
                stack.append(cur.data["submenu"])
            elif cur.kind == "status":
                # show the status block quickly as toast
                try: toast = last_line(cur.status_fn())
                except Exception: toast = ""
            elif cur.kind == "selector":
                # apply current choice
                pos = st.sel_idx.get(id(cur), 0)
                choices = cur.data.get("choices", [])
                if not choices: continue
                label, value = choices[pos]
                if cur.label.startswith("Select Mode"):
                    rc = usb_set(value)
                elif cur.label.startswith("Bind (host:port)"):
                    host, port = value
                    rc = web_config_set(host, port)
                elif cur.label.startswith("Select Payload"):
                    rc = payload_set(value)
                else:
                    rc = 0
                toast = "✓ OK" if rc == 0 else f"✗ ERR ({rc})"
            elif cur.kind == "action":
                fn = cur.data.get("fn")
                if not fn: continue
                r = fn()
                if r == "QUIT":
                    return
                toast = "✓ OK" if (isinstance(r, int) and r == 0) or r is None else ("✓" if r else "✓")
        elif k in (ord('q'),):
            return

# ======= CLI parsing / behavior =======
def main() -> int:
    # No args: minimal help
    if len(sys.argv) == 1 or sys.argv[1] in ("-h", "--help"):
        print(MAIN_HELP.rstrip()); return 0

    cmd = sys.argv[1].lower()

    # usb
    if cmd == "usb":
        if len(sys.argv) == 2:
            print(USB_HELP.rstrip()); return 0
        sub = sys.argv[2].lower()
        if sub == "status": return usb_status()
        if sub == "set":
            if len(sys.argv) < 4:
                print(USB_HELP.rstrip()); return 1
            return usb_set(sys.argv[3])
        print(USB_HELP.rstrip()); return 1

    # payload
    if cmd == "payload":
        if len(sys.argv) == 2:
            print(PAYLOAD_HELP.rstrip()); return 0
        sub = sys.argv[2].lower()
        if sub == "status": return payload_status()
        if sub == "list":   return payload_list()
        if sub == "set":
            if len(sys.argv) < 4:
                print(PAYLOAD_HELP.rstrip()); return 1
            return payload_set(sys.argv[3])
        print(PAYLOAD_HELP.rstrip()); return 1

    # web
    if cmd == "web":
        if len(sys.argv) == 2:
            print(WEB_HELP.rstrip()); return 0
        sub = sys.argv[2].lower()
        if sub == "status":  return web_status()
        if sub == "start":   return web_start()
        if sub == "stop":    return web_stop()
        if sub == "restart": return web_restart()
        if sub == "enable":  return web_enable()
        if sub == "disable": return web_disable()
        if sub == "config":
            if len(sys.argv) == 3:
                print(WEB_HELP.rstrip()); return 0
            action = sys.argv[3].lower()
            if action == "show": return web_config_show()
            if action == "set":
                # parse --host / --port
                host = None; port = None
                args = sys.argv[4:]; i = 0
                while i < len(args):
                    if args[i] == "--host" and i+1 < len(args):
                        host = args[i+1]; i += 2; continue
                    if args[i] == "--port" and i+1 < len(args):
                        try: port = int(args[i+1])
                        except ValueError: print("port must be an integer"); return 1
                        i += 2; continue
                    i += 1
                if not host or port is None:
                    print(WEB_HELP.rstrip()); return 1
                return web_config_set(host, port)
        print(WEB_HELP.rstrip()); return 1

    # ip
    if cmd == "ip":
        return ip_show()

    # menu
    if cmd == "menu":
        curses.wrapper(tui_menu)
        return 0

    print(MAIN_HELP.rstrip())
    return 1

if __name__ == "__main__":
    sys.exit(main())
