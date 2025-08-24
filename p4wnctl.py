#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import curses
import socket
import subprocess
from pathlib import Path
from textwrap import dedent

# ======= Paths / constants =======
P4WN_HOME = Path(os.environ.get("P4WN_HOME", "/opt/p4wnp1"))
HOOKS = P4WN_HOME / "hooks"
CONFIG = P4WN_HOME / "config"
USB_GADGET = Path("/sys/kernel/config/usb_gadget/p4wnp1")
ACTIVE_PAYLOAD_FILE = CONFIG / "active_payload"

WEBUI_UNIT = "p4wnp1-webui.service"
WEBUI_OVERRIDE_DIR = Path(f"/etc/systemd/system/{WEBUI_UNIT}.d")
WEBUI_OVERRIDE_FILE = WEBUI_OVERRIDE_DIR / "override.conf"

# Payload discovery
PAYLOAD_DIRS = [
    P4WN_HOME / "payloads",
    P4WN_HOME / "payloads" / "hid",
    P4WN_HOME / "payloads" / "network",
    P4WN_HOME / "payloads" / "listeners",
    P4WN_HOME / "payloads" / "shell",
]
PAYLOAD_MANIFEST_DIRS = [P4WN_HOME / "payloads" / "manifests"]

TRANSIENT_UNIT_PREFIX = "p4w-payload-"

# Known units for Services submenu (optional convenience)
SERVICE_UNITS = [
    ("USB Core", "p4wnp1.service"),
    ("USB Prep", "p4wnp1-usb-prep.service"),
    ("OLED Menu", "oledmenu.service"),
    ("Web UI", "p4wnp1-webui.service"),
]

# Defaults for gadget network and MSD
USB_NET_DEVADDR = os.environ.get("P4WN_USB_DEVADDR", "02:1A:11:00:00:01")
USB_NET_HOSTADDR = os.environ.get("P4WN_USB_HOSTADDR", "02:1A:11:00:00:02")
USB0_CIDR = os.environ.get("P4WN_USB0_CIDR", "10.13.37.1/24")
MSD_IMAGE = Path(os.environ.get("P4WN_MSD_IMAGE", str(CONFIG / "mass_storage.img")))
MSD_SIZE_MB = int(os.environ.get("P4WN_MSD_SIZE_MB", "128"))

# Presets for the TUI selector
USB_CHOICES = [
    ("HID + NET", "hid_net_only"),
    ("HID + NET + SER (ACM)", "hid_net_acm"),
    ("HID + NET + MSD", "hid_storage_net"),
    ("HID + NET + MSD + SER", "hid_storage_net_acm"),
    ("Storage Only", "storage_only"),

]

# ======= Small helpers =======
def sh(cmd: str, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)

def need_root():
    if os.geteuid() != 0:
        print("This command requires root (sudo).", file=sys.stderr)
        sys.exit(2)

def systemctl(*args) -> subprocess.CompletedProcess:
    return sh("systemctl " + " ".join(args), check=False)

def last_line(txt: str) -> str:
    for ln in reversed((txt or "").splitlines()):
        ln = ln.strip()
        if ln:
            return ln
    return ""

def ensure_mass_storage_image(img="/opt/p4wnp1/config/usb_mass_storage.img", size_mb=256):
    import subprocess, os
    os.makedirs(os.path.dirname(img), exist_ok=True)
    if not os.path.exists(img) or os.path.getsize(img) < size_mb*1024*1024:
        subprocess.run(["truncate", "-s", f"{size_mb}M", img], check=True)
        subprocess.run(["mkfs.vfat", "-F", "32", "-n", "P4WNP1", img], check=True)
    return img

def which(path: str) -> str | None:
    for d in os.environ.get("PATH", "").split(os.pathsep):
        c = Path(d) / path
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None

# ======= Dynamic IP helpers =======
def _ip_json() -> list[dict]:
    ip_bin = which("ip") or "/sbin/ip"
    try:
        out = sh(f"{ip_bin} -json addr show", check=False).stdout
        return json.loads(out) if out else []
    except Exception:
        return []

def ips_by_iface() -> dict[str, list[str]]:
    data = _ip_json()
    res: dict[str, list[str]] = {}
    for link in data:
        ifname = link.get("ifname")
        for a in link.get("addr_info", []) or []:
            if a.get("family") == "inet":
                res.setdefault(ifname, []).append(a.get("local"))
    return res

def primary_iface(order=("usb0", "eth0", "wlan0")) -> str | None:
    mapping = ips_by_iface()
    for want in order:
        if want in mapping and mapping[want]:
            return want
    for k, v in mapping.items():
        if k.startswith("enx") and v:
            return k
    for k, v in mapping.items():
        if v:
            return k
    return None

def primary_ip(order=("usb0", "eth0", "wlan0")) -> str | None:
    mapping = ips_by_iface()
    for want in order:
        if want in mapping and mapping[want]:
            return mapping[want][0]
    for k, v in mapping.items():
        if k.startswith("enx") and v:
            return v[0]
    for v in mapping.values():
        if v:
            return v[0]
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

def default_route_iface() -> str | None:
    """Return the interface used for the default route (0.0.0.0/0)."""
    ip_bin = which("ip") or "/sbin/ip"

    # Fast path: ‘ip route show default’
    cp = sh(f"{ip_bin} route show default", check=False)
    if cp.stdout:
        toks = cp.stdout.strip().split()
        if "dev" in toks:
            try:
                return toks[toks.index("dev") + 1]
            except Exception:
                pass

    # Fallback: look at route to a public IP
    cp = sh(f"{ip_bin} route get 1.1.1.1", check=False)
    if cp.stdout:
        toks = cp.stdout.strip().split()
        if "dev" in toks:
            try:
                return toks[toks.index("dev") + 1]
            except Exception:
                pass
    return None

def current_ssh_iface() -> str | None:
    """
    Best effort: if running under SSH, find the local interface used to reach the client IP.
    """
    peer = os.environ.get("SSH_CLIENT") or os.environ.get("SSH_CONNECTION")
    if not peer:
        return None
    client_ip = peer.strip().split()[0]
    ip_bin = which("ip") or "/sbin/ip"
    cp = sh(f"{ip_bin} route get {client_ip}", check=False)
    if cp.stdout and " dev " in cp.stdout:
        parts = cp.stdout.split()
        for i, tok in enumerate(parts):
            if tok == "dev" and i + 1 < len(parts):
                return parts[i + 1]
    return None

def gadget_ifaces() -> list[str]:
    """
    Return a list of NIC names provided by the USB gadget (RNDIS/ECM),
    e.g., ['usb0', 'usb1'] — robust even if names differ.
    """
    import os
    bases = "/sys/class/net"
    res = []
    for iface in os.listdir(bases):
        dev = os.path.join(bases, iface, "device")
        if not os.path.exists(dev):
            continue
        drv = os.path.join(dev, "driver")
        # e.g. /sys/class/net/usb0/device/driver -> .../usb_f_rndis or usb_f_ecm
        if os.path.islink(drv):
            target = os.readlink(drv).lower()
            if "usb" in target or "rndis" in target or "ecm" in target or "g_" in target:
                res.append(iface)
    return sorted(set(res))

# ======= Service management (generic) =======
def svc_paths(unit: str) -> tuple[Path, Path]:
    src1 = P4WN_HOME / "systemd" / unit
    src2 = P4WN_HOME / unit
    dst  = Path("/etc/systemd/system") / unit
    return (src1 if src1.exists() else src2, dst)

def svc_install(unit: str) -> int:
    need_root()
    src, dst = svc_paths(unit)
    if not src.exists():
        print(f"Unit not found in repo: {src}", file=sys.stderr)
        return 10
    try:
        dst.write_bytes(src.read_bytes())
        os.chmod(dst, 0o644)
        systemctl("daemon-reload")
        systemctl("enable", "--now", unit)
        systemctl("status", "--no-pager", "--lines=5", unit)
        return 0
    except Exception as e:
        print(f"Install failed: {e}", file=sys.stderr); return 11

def svc_uninstall(unit: str) -> int:
    need_root()
    systemctl("disable", "--now", unit)
    _p = Path("/etc/systemd/system") / unit
    if _p.exists():
        try: _p.unlink()
        except Exception: pass
    systemctl("daemon-reload")
    print(f"{unit} uninstalled.")
    return 0

def svc_status_text(unit: str) -> str:
    active = systemctl("is-active", unit).stdout.strip() or "unknown"
    enabled = systemctl("is-enabled", unit).stdout.strip() or "unknown"
    return f"{unit}: {active} ({enabled})"

# ======= USB (configfs builder, no legacy g_* modules) =======
def usb_unbind_all():
    base = Path("/sys/kernel/config/usb_gadget")
    for g in base.iterdir():
        if not g.is_dir(): continue
        udc = g / "UDC"
        if udc.exists():
            try: udc.write_text("")
            except Exception: pass

def usb_unload_legacy():
    for mod in ["g_hid","g_ether","g_serial","g_mass_storage","g_multi","g_acm"]:
        sh(f"rmmod {mod}", check=False)

def usb_force_reset():
    need_root()
    usb_preflight()
    # These often “hold” /dev/ttyGS0 or interfere with UDC binding
    systemctl("stop", "serial-getty@ttyGS0.service")
    systemctl("stop", "ModemManager.service")
    usb_unbind_all()
    usb_unload_legacy()

def usb_preflight():
    sh("modprobe configfs || true", check=False)
    sh("mount -t configfs none /sys/kernel/config || true", check=False)
    sh("modprobe dwc2 || true", check=False)
    sh("modprobe libcomposite || true", check=False)
    uds = Path("/sys/class/udc")
    if not uds.exists() or not any(uds.iterdir()):
        print("[!] No USB Device Controller under /sys/class/udc.\n"
              "    Add 'dtoverlay=dwc2' to /boot/config.txt and reboot.",
              file=sys.stderr)
        sys.exit(3)

def _hid_report_desc_bytes() -> bytes:
    return bytes([
        0x05,0x01, 0x09,0x06, 0xA1,0x01, 0x05,0x07,
        0x19,0xE0, 0x29,0xE7, 0x15,0x00, 0x25,0x01,
        0x75,0x01, 0x95,0x08, 0x81,0x02, 0x95,0x01,
        0x75,0x08, 0x81,0x03, 0x95,0x05, 0x75,0x01,
        0x05,0x08, 0x19,0x01, 0x29,0x05, 0x91,0x02,
        0x95,0x01, 0x75,0x03, 0x91,0x03, 0x95,0x06,
        0x75,0x08, 0x15,0x00, 0x25,0x65, 0x05,0x07,
        0x19,0x00, 0x29,0x65, 0x81,0x00, 0xC0
    ])

def _ensure_msd_image():
    if MSD_IMAGE.exists():
        return
    MSD_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    with open(MSD_IMAGE, "wb") as f:
        f.truncate(MSD_SIZE_MB * 1024 * 1024)

def _unlink_all(cfg_dir: Path):
    for l in list(cfg_dir.iterdir()):
        if l.is_symlink():
            try: l.unlink()
            except Exception: pass

def _remove_dir_tree(p: Path):
    if not p.exists(): return
    for child in sorted(p.iterdir(), reverse=True):
        if child.is_symlink():
            try: child.unlink()
            except Exception: pass
        elif child.is_dir():
            _remove_dir_tree(child)
        else:
            try: child.unlink()
            except Exception: pass
    try: p.rmdir()
    except Exception: pass

def usb_unbind():
    if USB_GADGET.exists():
        udc = USB_GADGET / "UDC"
        try:
            udc.write_text("")
        except Exception:
            pass

def usb_teardown():
    usb_unbind()
    for sub in ("functions", "configs"):
        base = USB_GADGET / sub
        if not base.exists(): continue
        for x in list(base.iterdir()):
            if sub == "configs":
                _unlink_all(x)
            _remove_dir_tree(x)

def _write(path: Path, content: str | bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        with open(path, "wb") as f: f.write(content)
    else:
        path.write_text(content)

def _bind_first_udc():
    udcs = sorted([p.name for p in Path("/sys/class/udc").iterdir()])
    if not udcs:
        raise RuntimeError("No UDC available")
    (USB_GADGET / "UDC").write_text(udcs[0])

def _gadget_common_init():
    USB_GADGET.mkdir(parents=True, exist_ok=True)
    _write(USB_GADGET / "idVendor", "0x1d6b")
    _write(USB_GADGET / "idProduct", "0x0104")
    _write(USB_GADGET / "bcdDevice", "0x0100")
    _write(USB_GADGET / "bcdUSB", "0x0200")
    s = USB_GADGET / "strings/0x409"
    _write(s / "serialnumber", "P4wnP1-O2")
    _write(s / "manufacturer", "quasialex")
    _write(s / "product", "P4wnP1-O2 Gadget")
    cfg = USB_GADGET / "configs/c.1"
    _write(cfg / "MaxPower", "250")
    _write(USB_GADGET / "configs/c.1/strings/0x409/configuration", "Config 1")

def _func_hid():
    f = USB_GADGET / "functions/hid.usb0"
    f.mkdir(parents=True, exist_ok=True)
    _write(f / "protocol", "1")
    _write(f / "subclass", "1")
    _write(f / "report_length", "8")
    _write(f / "report_desc", _hid_report_desc_bytes())
    return f

def _func_ecm():
    f = USB_GADGET / "functions/ecm.usb0"
    f.mkdir(parents=True, exist_ok=True)
    _write(f / "dev_addr", USB_NET_DEVADDR)
    _write(f / "host_addr", USB_NET_HOSTADDR)
    return f

def _func_rndis():
    f = USB_GADGET / "functions/rndis.usb0"
    f.mkdir(parents=True, exist_ok=True)
    _write(f / "dev_addr", USB_NET_DEVADDR)
    _write(f / "host_addr", USB_NET_HOSTADDR)
    return f

def _func_msd():
    _ensure_msd_image()
    f = USB_GADGET / "functions/mass_storage.usb0"
    f.mkdir(parents=True, exist_ok=True)
    _write(f / "stall", "0")
    _write(f / "lun.0/removable", "1")
    _write(f / "lun.0/ro", "0")
    _write(f / "lun.0/file", str(MSD_IMAGE))
    return f

def _func_acm():
    f = USB_GADGET / "functions/acm.usb0"
    f.mkdir(parents=True, exist_ok=True)
    return f

def _link(f: Path, cfg: Path):
    ln = cfg / f.name
    if not ln.exists():
        ln.symlink_to(f)

def _ensure_usb0_ip():
    ip_bin = which("ip") or "/sbin/ip"
    q = sh(f"{ip_bin} -4 addr show usb0", check=False).stdout
    has_ip = "inet " in (q or "")
    if not has_ip and USB0_CIDR:
        sh(f"{ip_bin} addr add {USB0_CIDR} dev usb0 2>/dev/null || true", check=False)
        sh(f"{ip_bin} link set usb0 up 2>/dev/null || true", check=False)

def usb_apply_mode(mode: str) -> int:
    need_root()
    usb_preflight()
    _gadget_common_init()
    cfg = USB_GADGET / "configs/c.1"
    usb_teardown()
    _gadget_common_init()

    if mode == "hid_net_only":
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)
        _link(_func_rndis(), cfg)
    elif mode == "hid_storage_net":
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)
        _link(_func_rndis(), cfg)
        _link(_func_msd(), cfg)
    elif mode == "hid_net_acm":
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)
        _link(_func_rndis(), cfg)
        _link(_func_acm(), cfg)
    elif mode == "hid_storage_net_acm":
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)
        _link(_func_rndis(), cfg)
        _link(_func_msd(), cfg)
        _link(_func_acm(), cfg)
    elif mode == "storage_only":
        _link(_func_msd(), cfg)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        return 4

    try:
        _bind_first_udc()
    except Exception as e:
        print(f"Bind failed: {e}", file=sys.stderr)
        return 6

    _ensure_usb0_ip()
    return 0

def usb_caps_now() -> dict:
    funcs = USB_GADGET / "functions"
    def ex(n): return (funcs / n).exists()
    return {
        "hid": ex("hid.usb0"),
        "net": ex("ecm.usb0") or ex("rndis.usb0"),
        "msd": ex("mass_storage.usb0"),
        "acm": ex("acm.usb0"),
    }

def usb_compose_apply(hid: bool, net: bool, msd: bool, acm: bool = False) -> int:
    """
    Build gadget with requested functions. Extends presets without new shell scripts.
    """
    need_root()
    usb_preflight()
    usb_force_reset()
    usb_teardown()
    _gadget_common_init()
    cfg = USB_GADGET / "configs/c.1"

    if hid: _link(_func_hid(), cfg)
    if net:
        _link(_func_ecm(), cfg)
        _link(_func_rndis(), cfg)
    if msd: _link(_func_msd(), cfg)
    if acm: _link(_func_acm(), cfg)

    try:
        _bind_first_udc()
    except Exception as e:
        print(f"Bind failed: {e}", file=sys.stderr); return 6

    _ensure_usb0_ip()
    print(usb_status_text())
    return 0

def usb_status_text() -> str:
    try:
        mounts = Path("/proc/mounts").read_text()
    except Exception:
        mounts = ""
    cfg_mounted = " configfs " in mounts

    if not USB_GADGET.exists():
        return "USB: none (configfs mounted, no gadget)" if cfg_mounted else "USB: unavailable (configfs not mounted)"

    funcs = USB_GADGET / "functions"
    if not funcs.exists():
        return "USB: none (gadget dir present, no functions)"

    hid   = (funcs / "hid.usb0").exists()
    rndis = (funcs / "rndis.usb0").exists()
    ecm   = (funcs / "ecm.usb0").exists()
    msd   = (funcs / "mass_storage.usb0").exists()
    acm   = (funcs / "acm.usb0").exists()

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
    if acm: parts.append("SER")
    lines = [f"USB: {mode} ({'+'.join(parts) if parts else 'none'})"]
    for c in ["c.1", "c.2"]:
        cdir = USB_GADGET / "configs" / c
        if cdir.exists():
            links = []
            for name in ["hid.usb0","rndis.usb0","ecm.usb0","mass_storage.usb0","acm.usb0"]:
                if (cdir / name).exists(): links.append(name.split(".")[0])
            lines.append(f" {c}: {('+'.join(links) if links else 'n/a')}")
    return "\n".join(lines)

def usb_status(_args=None) -> int:
    print(usb_status_text()); return 0

def usb_set(mode: str) -> int:
    # Guard: do not change gadget if the *default route* is on usb*, unless forced
    route_if = default_route_iface()
    force = os.environ.get("P4WN_FORCE_USB", "0").lower() in ("1","true","yes","on")
    if route_if and route_if.startswith("usb") and not force:
        print(f"[!] Refusing to change USB gadget while default route is via '{route_if}'.", file=sys.stderr)
        print("    Connect over Wi‑Fi/Ethernet or set P4WN_FORCE_USB=1 to override.", file=sys.stderr)
        return 2

    if "storage" in mode:
        ensure_mass_storage_image()
    need_root()
    usb_preflight()
    usb_force_reset()
    usb_teardown()
    rc = usb_apply_mode(mode)
    if rc != 0:
        return rc
    try:
        udc = (USB_GADGET / "UDC").read_text().strip()
        if not udc:
            print("[!] Gadget not bound to any UDC (still empty).", file=sys.stderr)
    except Exception:
        pass
    print(usb_status_text())
    return 0

# ======= Payload discovery / manifests =======
try:
    import yaml  # optional
except Exception:
    yaml = None

def _manifest_files():
    files = []
    for d in PAYLOAD_MANIFEST_DIRS:
        if d.exists():
            files += sorted(list(d.glob("*.json")) + list(d.glob("*.yml")) + list(d.glob("*.yaml")))
    return files

def _read_manifest(path: Path) -> dict | None:
    try:
        text = path.read_text()
        suf = path.suffix.lower()
        if suf == ".json":
            return json.loads(text)
        if suf in (".yml", ".yaml") and yaml:
            return yaml.safe_load(text)
    except Exception:
        return None
    return None

def load_manifests() -> dict[str, dict]:
    out = {}
    for p in _manifest_files():
        m = _read_manifest(p)
        if not isinstance(m, dict):
            continue
        name = str(m.get("name", "")).strip() or p.stem
        if "script" in m and m["script"]:
            sp = Path(m["script"])
            if not sp.is_absolute():
                sp = (P4WN_HOME / sp).resolve()
            m["script"] = str(sp)
        m["_manifest_path"] = str(p)
        out[name] = m
    return out

def find_python_script(name: str) -> Path | None:
    candidates = []
    for r in PAYLOAD_DIRS:
        candidates.append(r / f"{name}.py")
        for cat in ("hid","network","listeners","shell"):
            candidates.append(r / cat / f"{name}.py")
    for c in candidates:
        if c.exists():
            return c
    return None

def list_payload_names() -> list[str]:
    names = set(load_manifests().keys())
    for r in PAYLOAD_DIRS:
        if not r.exists(): continue
        for p in r.glob("*.py"): names.add(p.stem)
        for cat in ("hid","network","listeners","shell"):
            d = r / cat
            if d.exists():
                for p in d.glob("*.py"): names.add(p.stem)
    for r in PAYLOAD_DIRS:
        if not r.exists(): continue
        for p in r.glob("*.sh"): names.add(p.stem)
        for cat in ("hid","network","listeners","shell"):
            d = r / cat
            if d.exists():
                for p in d.glob("*.sh"): names.add(p.stem)
    return sorted(names)

def transient_unit_name(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in name.lower())
    return f"{TRANSIENT_UNIT_PREFIX}{safe}.service"

def payload_status_text_by_name(name: str) -> str:
    unit = transient_unit_name(name)
    active = systemctl("is-active", unit).stdout.strip() or "unknown"
    enabled = systemctl("is-enabled", unit).stdout.strip() or "transient"
    return f"{name} [{unit}]: {active} ({enabled})"

def _apply_env_and_cwd(cmd: str, env: dict | None, wdir: str | None) -> str:
    parts = []
    if env:
        for k, v in env.items():
            parts.append(f'export {k}={json.dumps(str(v))};')
    if wdir:
        parts.append(f'cd {json.dumps(wdir)};')
    parts.append(cmd)
    return " ".join(parts)

def _run_preflight(env: dict | None, wdir: str | None, pre: list[str] | None) -> int:
    if not pre:
        return 0
    # Always set noninteractive to avoid dpkg/apt prompts; add a sane default timeout
    env = dict(env or {})
    env.setdefault("DEBIAN_FRONTEND", "noninteractive")
    env.setdefault("APT_LISTCHANGES_FRONTEND", "none")
    seq = " && ".join(pre)
    full = _apply_env_and_cwd(seq, env, wdir)
    # Use unbuffered output to the journald via systemd-run later; here we still run synchronously but won’t prompt
    cp = subprocess.run(
        f"/bin/bash -lc {json.dumps(full)}",
        shell=True,
        text=True,
        capture_output=True,
        timeout=1200  # 20 minutes cap so it never wedges your TTY
    )
    if cp.returncode != 0:
        sys.stdout.write(cp.stdout or "")
        sys.stderr.write(cp.stderr or "")
    return cp.returncode

def _transient_unit_cleanup(unit: str):
    """Ensure no stale fragment/transient unit blocks systemd-run."""
    # Stop/disable if present (ignore errors)
    sh(f"systemctl stop {unit}", check=False)
    sh(f"systemctl disable {unit}", check=False)

    # Remove any persistent fragment
    frag = Path("/etc/systemd/system") / unit
    dropin = Path("/etc/systemd/system") / (unit + ".d")
    try:
        if frag.exists():
            frag.unlink()
    except Exception:
        pass
    try:
        if dropin.exists():
            for f in dropin.glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass
            try:
                dropin.rmdir()
            except Exception:
                pass
    except Exception:
        pass

    # Remove stale transient instance
    run_frag = Path("/run/systemd/transient") / unit
    try:
        if run_frag.exists():
            run_frag.unlink()
    except Exception:
        pass

    # Reload & clear failures
    sh("systemctl daemon-reload", check=False)
    sh("systemctl reset-failed", check=False)

def payload_start(name: str) -> int:
    unit = f"p4w-payload-{name}.service"
    _transient_unit_cleanup(unit)
    need_root()
    mans = load_manifests()
    m = mans.get(name, {})

    cmd = m.get("cmd")
    binp = m.get("bin")
    script = m.get("script")
    args = m.get("args", []) or []
    env = m.get("env", {}) or {}
    wdir = m.get("working_dir")
    harden = bool(m.get("harden", True))
    pre = m.get("preflight", []) or []

    if not (cmd or binp or script):
        sp = find_python_script(name)
        if sp:
            script = str(sp)
        else:
            print(f"No manifest or payload found for '{name}'. "
                  f"Add payloads/manifests/{name}.json|.yml or {name}.py.", file=sys.stderr)
            return 1

    # Dynamic env
    lhost = primary_ip()
    if lhost:
        env = dict(env or {})
        env.setdefault("P4WN_LHOST", lhost)
    iface = primary_iface()
    if iface:
        env = dict(env or {})
        env.setdefault("P4WN_NET_IFACE", iface)

    rc = _run_preflight(env, wdir, pre)
    if rc != 0:
        return rc

    unit = transient_unit_name(name)
    props = [
        "--property=Restart=on-failure",
        "--property=RestartSec=2",
        "--property=StandardOutput=journal",
        "--property=StandardError=journal",
        "--collect",
    ]
    if harden:
        props += [
            "--property=NoNewPrivileges=yes",
            "--property=PrivateTmp=yes",
            "--property=ProtectSystem=full",
            "--property=ProtectHome=yes",
        ]
    for k, v in (env or {}).items():
        props.append(f"--setenv={k}={v}")
    if wdir:
        props.append(f"--working-directory={wdir}")

    if cmd:
        final_cmd = _apply_env_and_cwd(cmd, None, None)
    elif binp:
        parts = [binp] + [str(a) for a in args]
        final_cmd = " ".join(parts)
    else:
        py = "/usr/bin/env python3"
        script_quoted = json.dumps(str(script))
        arg_str = " ".join(json.dumps(str(a)) for a in (args or []))
        final_cmd = f"{py} {script_quoted}" + (f" {arg_str}" if arg_str else "")

    cmdline = f"systemd-run --unit={unit} " + " ".join(props) + " /bin/bash -lc " + json.dumps(final_cmd)
    cp = sh(cmdline, check=False)
    sys.stdout.write(cp.stdout); sys.stderr.write(cp.stderr)
    return cp.returncode

def payload_stop(name: str) -> int:
    need_root()
    unit = transient_unit_name(name)
    return systemctl("stop", unit).returncode

def payload_logs(name: str) -> int:
    unit = transient_unit_name(name)
    return sh(f"journalctl -u {unit} --no-pager -n 100", check=False).returncode

def payload_status_named(name: str) -> int:
    print(payload_status_text_by_name(name)); return 0

def payload_status_all() -> int:
    names = list_payload_names()
    if not names:
        print("(no payloads found)"); return 0
    for name in names:
        print(payload_status_text_by_name(name))
    return 0

# ======= Legacy "active payload" helpers (kept) =======
def _payload_candidates(name: str):
    return [
        P4WN_HOME / f"payloads/{name}.sh",
        P4WN_HOME / f"payloads/hid/{name}.sh",
        P4WN_HOME / f"payloads/network/{name}.sh",
        P4WN_HOME / f"payloads/listeners/{name}.sh",
        P4WN_HOME / f"payloads/shell/{name}.sh",
        P4WN_HOME / f"payloads/{name}.py",
        P4WN_HOME / f"payloads/hid/{name}.py",
        P4WN_HOME / f"payloads/network/{name}.py",
        P4WN_HOME / f"payloads/listeners/{name}.py",
        P4WN_HOME / f"payloads/shell/{name}.py",
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

def payload_list(group: str | None = None) -> int:
    mans = load_manifests()
    names = list_payload_names()
    if not names:
        print("(no payloads found)"); return 0
    for n in names:
        m = mans.get(n)
        g = (m or {}).get("group")
        if group and g != group:
            continue
        summ = (m or {}).get("summary", "")
        print(n if not summ else f"{n} - {summ}")
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

def payload_describe(name: str) -> int:
    m = load_manifests().get(name)
    if not m:
        print(f"(no manifest for '{name}')"); return 1
    print(f"{m.get('name', name)}")
    if m.get("group"): print(f"Group: {m['group']}")
    if m.get("summary"): print(f"\nSummary:\n  {m['summary']}")
    if m.get("usage"):
        print("\nUsage:")
        for u in m["usage"]:
            print(f"  - {u}")
    if m.get("requirements"):
        print("\nRequirements:")
        for r in m["requirements"]:
            print(f"  - {r}")
    if m.get("risks"):
        print("\nOpSec / Risks:")
        for r in m["risks"]:
            print(f"  - {r}")
    if m.get("estimated_runtime"):
        print(f"\nEstimated runtime: {m['estimated_runtime']}")
    print(f"\nManifest: {m.get('_manifest_path','(unknown)')}")
    return 0

def get_payload_choices():
    names = list_payload_names()
    return [(n, n) for n in names]

# ======= "Run Now" (requirements-aware) =======
REQ_OVERRIDES = {
    # HID
    "reverse_inmemory": ["hid"],
    "reverse_http_fetch": ["hid"],
    "usb_stealer": ["hid"],
    "domain_enum_hid": ["hid"],
    "lockpicker": ["hid"],
    "test_typing": ["hid"],
    # Network
    "rogue_dhcp_dns": ["net"],
    "dns_spoof_redirect": ["net"],
    "responder_attack": ["net"],
    "credsnarf_spoof": ["net"],
    "reverse_shell_listener": ["net"],
    # Shell/admin
    "start_tmux_shell": ["net", "tmux"],
    "reverse_to_host": ["serial"],
    "hid_backdoor": ["net"],
}

def _infer_group_from_path(name: str) -> str | None:
    sp = find_python_script(name)
    if not sp:
        return None
    p = str(sp)
    if "/payloads/hid/" in p: return "hid"
    if "/payloads/network/" in p: return "network"
    if "/payloads/shell/" in p: return "shell"
    if "/payloads/listeners/" in p: return "listeners"
    return None

def payload_requirements_for(name: str) -> list[str]:
    m = load_manifests().get(name, {})
    if "requirements" in m and isinstance(m["requirements"], list):
        return list(m["requirements"])
    if name in REQ_OVERRIDES:
        return REQ_OVERRIDES[name]
    g = _infer_group_from_path(name)
    if g == "hid": return ["hid"]
    if g == "network": return ["net"]
    if g == "shell": return []
    return []

def ensure_for_requirements(reqs: list[str]) -> int:
    want_hid = "hid" in reqs
    want_net = "net" in reqs
    want_msd = "msd" in reqs
    want_acm = "serial" in reqs

    # If nothing USB-related requested, skip touching the gadget
    if not (want_hid or want_net or want_msd or want_acm):
        # best-effort tmux warning only
        if "tmux" in reqs and not which("tmux"):
            print("[!] tmux not found; install tmux for best results.", file=sys.stderr)
        return 0

    rc = usb_compose_apply(want_hid, want_net, want_msd, want_acm)

    if "tmux" in reqs and not which("tmux"):
        print("[!] tmux not found; install tmux for best results.", file=sys.stderr)

    return rc

def payload_run_now(name: str) -> int:
    # Prevent shooting ourselves in the foot: if a payload will flip wlan0 into AP mode
    # and our current SSH session is on wlan0, refuse unless explicitly forced.
    dangerous = name.lower().startswith("wifi_ap_")
    if dangerous:
        ssh_if = current_ssh_iface()
        if ssh_if == "wlan0" and os.environ.get("P4WN_FORCE_WIFI", "0").lower() not in ("1","true","yes","on"):
            print("[!] Refusing to start Wi‑Fi AP payload while current SSH session is on wlan0.", file=sys.stderr)
            print("    Reconnect over Ethernet/USB gadget or set P4WN_FORCE_WIFI=1 to override.", file=sys.stderr)
            return 2
    """
    Ensure required modes (HID/NET/MSD/Serial), then start payload.
    'active' uses the legacy ACTIVE_PAYLOAD_FILE pointer.
    """
    if name in ("", "active"):
        if not ACTIVE_PAYLOAD_FILE.exists():
            print("No active payload set.", file=sys.stderr); return 2
        name = Path(ACTIVE_PAYLOAD_FILE.read_text().strip()).stem
    reqs = payload_requirements_for(name)
    rc = ensure_for_requirements(reqs)
    if rc != 0:
        return rc
    return payload_start(name)

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
    if host == "auto":
        auto = primary_ip()
        if not auto:
            print("Could not determine primary IP for 'auto'", file=sys.stderr); return 1
        host = auto
    if not isinstance(port, int) or not (1 <= port <= 65535):
        print("Port must be 1..65535", file=sys.stderr); return 1
    if not host or any(ch.isspace() for ch in host):
        print("Host must be a single token (no spaces).", file=sys.stderr); return 1
    _web_override_write(host, port)
    print(f"WebUI configured: {host}:{port} (override written)")
    return 0

def web_url() -> int:
    host = None
    port = None
    if WEBUI_OVERRIDE_FILE.exists():
        text = WEBUI_OVERRIDE_FILE.read_text()
        for line in text.splitlines():
            if "WEBUI_HOST=" in line:
                host = line.split("WEBUI_HOST=")[-1].strip().strip('"')
            if "WEBUI_PORT=" in line:
                try: port = int(line.split("WEBUI_PORT=")[-1].split('"')[0].strip())
                except Exception: pass
    if not host:
        host = primary_ip() or "0.0.0.0"
    if port is None:
        port = int(os.environ.get("WEBUI_PORT", "8080"))
    print(f"http://{host}:{port}")
    return 0

def _web_bind_choices():
    cur = primary_ip() or "0.0.0.0"
    return [
        (f"{cur}:8080", (cur, 8080)),
        ("127.0.0.1:8080", ("127.0.0.1", 8080)),
        ("0.0.0.0:8080", ("0.0.0.0", 8080)),
        ("127.0.0.1:8000", ("127.0.0.1", 8000)),
        ("0.0.0.0:9090", ("0.0.0.0", 9090)),
    ]

# ======= IP =======
def ip_text() -> str:
    base = Path("/sys/class/net")
    if not base.exists():
        return "No interfaces"
    ifaces = [p.name for p in base.iterdir() if p.is_dir() and p.name != "lo"]

    def is_usb(iface: str) -> bool:
        dev = base / iface / "device"
        try:
            target = os.readlink(dev)
            full = (dev.parent / target).resolve()
            return "/usb" in str(full)
        except OSError:
            return False

    def oper_state(iface: str) -> str:
        try:
            return (base / iface / "operstate").read_text().strip()
        except Exception:
            return "unknown"

    def rank(iface: str) -> tuple:
        name = iface.lower()
        if is_usb(iface): pri = 0
        elif name.startswith(("eth","en")): pri = 1
        elif name.startswith("wlan"): pri = 2
        else: pri = 3
        return (pri, name)

    ifaces.sort(key=rank)

    lines = []
    for iface in ifaces:
        state = oper_state(iface)
        cp = sh(f"ip -4 addr show {iface}", check=False)
        ipline = ""
        if "inet " in cp.stdout:
            for ln in cp.stdout.splitlines():
                ln = ln.strip()
                if ln.startswith("inet "):
                    parts = ln.split()
                    if len(parts) > 1:
                        ipline = parts[1]
                        break
        lines.append(f"{iface} ({state}): {ipline if ipline else 'no ip'}")
    prim = primary_ip()
    if prim:
        lines.append(f"primary: {prim}")
    return "\n".join(lines) if lines else "No interfaces"

def ip_show(_args=None) -> int:
    print(ip_text())
    return 0

def ip_primary(_args=None) -> int:
    ip = primary_ip()
    if not ip: return 1
    print(ip); return 0

def ip_env(_args=None) -> int:
    ip = primary_ip()
    if not ip: return 1
    print(f"export LHOST={ip}"); return 0

def ip_json(_args=None) -> int:
    print(json.dumps(ips_by_iface(), indent=2)); return 0

# ======= Template render (for __HOST__) =======
def template_render(path: str) -> int:
    p = Path(path)
    if not p.is_file():
        print(f"File not found: {p}", file=sys.stderr); return 1
    host = primary_ip()
    if not host:
        print("Could not resolve primary IP", file=sys.stderr); return 1
    text = p.read_text(encoding="utf-8", errors="ignore")
    print(text.replace("__HOST__", host), end="")
    return 0

# ======= Help screens =======
MAIN_HELP = dedent("""\
P4wnP1-O2 control CLI

Subcommands:
  usb         USB gadget controls
  payload     Payload controls (list/set + start/stop/status/logs/describe/run-now)
  web         Web UI controls (port/host, start/stop, enable/disable, url)
  service     Manage systemd units (install/uninstall/start/stop/...)
  ip          Show IPs (also: ip primary | ip env | ip json)
  template    Render a text file replacing __HOST__ with device IP
  menu        Interactive menu (arrow keys)
""")

USB_HELP = dedent("""\
USB gadget controls
-------------------
Commands:
  usb status
  usb set {hid_net_only|hid_storage_net|storage_only}
  usb set {hid_net_only|hid_net_acm|hid_storage_net|hid_storage_net_acm|storage_only}
  usb compose --hid=0|1 --net=0|1 --msd=0|1 [--acm=0|1]
""")

PAYLOAD_HELP = dedent("""\
Payload controls
----------------
Commands:
  payload list
  payload set <name>         # legacy active payload pointer (sh/py)
  payload status             # shows active payload pointer
  payload status all         # transient runner states for all discovered payloads
  payload status <name>
  payload start <name>       # runs using manifest (cmd|bin|script)
  payload run-now <name|active>   # ensure USB/WiFi prereqs, then start
  payload stop <name>
  payload logs <name>
  payload describe <name>
""")

WEB_HELP = dedent(f"""\
Web UI controls
---------------
Commands:
  web status
  web start | stop | restart
  web enable | disable
  web config show
  web config set --host <ip|auto> --port <n>
  web url
""")

SERVICE_HELP = dedent("""\
Service controls
----------------
Usage:
  p4wnctl service <install|uninstall|start|stop|restart|enable|disable|status|logs> <unit>
""")

# ======= Curses TUI (arrow-driven) =======
class MenuItem:
    def __init__(self, label, kind, data=None, status_fn=None):
        self.label = label
        self.kind = kind  # 'submenu' | 'action' | 'selector' | 'status'
        self.data = data or {}
        self.status_fn = status_fn  # callable -> str

class MenuState:
    def __init__(self, title, items):
        self.title = title
        self.items = items
        self.idx = 0
        self.sel_idx = {}

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

    status_lines = []
    cur = state.current()
    if cur and cur.status_fn:
        try:
            block = cur.status_fn() or ""
            status_lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        except Exception:
            status_lines = []

    max_status = min(3, max(0, h - 8))
    used = 0
    for i, ln in enumerate(status_lines[:max_status]):
        add(2 + i, 0, ln)
        used += 1

    top = 4 + used

    for i, it in enumerate(state.items):
        prefix = "> " if i == state.idx else "  "
        label = it.label
        if it.kind == "selector":
            curpos = state.sel_idx.get(id(it), 0)
            choices = it.data.get("choices", [])
            if choices:
                lab = choices[curpos][0]
                label = f"{label}: {lab}"
        add(top + i, 0, prefix + label, curses.A_REVERSE if i == state.idx else 0)

    if toast:
        add(h-2, 0, toast[:w-1], curses.A_BOLD)
    stdscr.refresh()

def tui_menu(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)

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
        MenuItem("Active (pointer)", "status", status_fn=payload_status_text),
        MenuItem("Select Active", "selector", data={"choices": payload_choices}),
        *[MenuItem(f"Set active: {lab}", "action", data={"fn": payload_set_cur(val)}) for lab, val in payload_choices[:6]],
        MenuItem("--- transient runner ---", "status", status_fn=lambda: " "),
        MenuItem("Status (all)", "action", data={"fn": lambda: payload_status_all()}),
        *[MenuItem(f"Start: {lab}", "action", data={"fn": (lambda v=val: (need_root(), payload_start(v))[1])}) for lab, val in payload_choices[:5]],
        *[MenuItem(f"Stop:  {lab}", "action", data={"fn": (lambda v=val: (need_root(), payload_stop(v))[1])}) for lab, val in payload_choices[:5]],
    ])

    web_sub = MenuState("Web UI", [
        MenuItem("Status", "status", status_fn=web_status_text),
        MenuItem("Bind (host:port)", "selector", data={"choices": _web_bind_choices()}),
        MenuItem("Start", "action", data={"fn": web_start}),
        MenuItem("Stop", "action", data={"fn": web_stop}),
        MenuItem("Restart", "action", data={"fn": web_restart}),
        MenuItem("Enable", "action", data={"fn": web_enable}),
        MenuItem("Disable", "action", data={"fn": web_disable}),
        MenuItem("Show override", "action", data={"fn": lambda: web_config_show(None)}),
        MenuItem("Show URL", "action", data={"fn": web_url}),
    ])

    def mk_svc_actions(title, unit):
        return MenuState(title, [
            MenuItem("Status",  "status", status_fn=lambda u=unit: svc_status_text(u)),
            MenuItem("Start",   "action", data={"fn": lambda u=unit: (need_root(), systemctl('start', u).returncode)[1]}),
            MenuItem("Stop",    "action", data={"fn": lambda u=unit: (need_root(), systemctl('stop', u).returncode)[1]}),
            MenuItem("Restart", "action", data={"fn": lambda u=unit: (need_root(), systemctl('restart', u).returncode)[1]}),
            MenuItem("Enable",  "action", data={"fn": lambda u=unit: (need_root(), systemctl('enable', u).returncode)[1]}),
            MenuItem("Disable", "action", data={"fn": lambda u=unit: (need_root(), systemctl('disable', u).returncode)[1]}),
            MenuItem("Install (copy+enable)",    "action", data={"fn": lambda u=unit: svc_install(u)}),
            MenuItem("Uninstall (disable+rm)",   "action", data={"fn": lambda u=unit: svc_uninstall(u)}),
        ])
    svc_items = [MenuItem(nice, "submenu", data={"submenu": mk_svc_actions(nice, unit)}) for nice, unit in SERVICE_UNITS]
    services_sub = MenuState("Services", svc_items if svc_items else [MenuItem("(no units)", "status")])

    root = MenuState("P4wnP1-O2", [
        MenuItem("USB", "submenu", data={"submenu": usb_sub}),
        MenuItem("Payloads", "submenu", data={"submenu": payload_sub}),
        MenuItem("Web UI", "submenu", data={"submenu": web_sub}),
        MenuItem("Services", "submenu", data={"submenu": services_sub}),
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
                try: toast = last_line(cur.status_fn())
                except Exception: toast = ""
            elif cur.kind == "selector":
                pos = st.sel_idx.get(id(cur), 0)
                choices = cur.data.get("choices", [])
                if not choices: continue
                label, value = choices[pos]
                if cur.label.startswith("Select Mode"):
                    rc = usb_set(value)
                elif cur.label.startswith("Bind (host:port)"):
                    host, port = value
                    rc = web_config_set(host, port)
                elif cur.label.startswith("Select Active"):
                    rc = payload_set(value)
                else:
                    rc = 0
                toast = "✓ OK" if rc == 0 else f"✗ ERR ({rc})"
            elif cur.kind == "action":
                fn = cur.data.get("fn")
                if not fn: continue
                r = fn()
                if r == "QUIT": return
                toast = "✓ OK" if (isinstance(r, int) and r == 0) or r is None else "✓"
        elif k in (ord('q'),):
            return

# ======= CLI parsing =======
def main() -> int:
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
        if sub == "compose":
            # Usage: p4wnctl usb compose --hid=0|1 --net=0|1 --msd=0|1 [--acm=0|1]
            def pbool(name):
                for a in sys.argv[3:]:
                    if a.startswith(f"--{name}="):
                        v = a.split("=",1)[1].strip().lower()
                        if v in ("1","true","on","yes"):  return True
                        if v in ("0","false","off","no"): return False
                return None
            caps = usb_caps_now()
            hid = pbool("hid"); net = pbool("net"); msd = pbool("msd"); acm = pbool("acm")
            return usb_compose_apply(
                caps["hid"] if hid is None else hid,
                caps["net"] if net is None else net,
                caps["msd"] if msd is None else msd,
                caps["acm"] if acm is None else acm
            )
        print(USB_HELP.rstrip()); return 1

    # payload
    if cmd == "payload":
        if len(sys.argv) == 2:
            print(PAYLOAD_HELP.rstrip()); return 0
        sub = sys.argv[2].lower()

        if sub == "list":   return payload_list()
        if sub == "set":
            if len(sys.argv) < 4: print(PAYLOAD_HELP.rstrip()); return 1
            return payload_set(sys.argv[3])
        if sub == "status":
            if len(sys.argv) == 3: return payload_status()
            if len(sys.argv) == 4 and sys.argv[3] == "all": return payload_status_all()
            if len(sys.argv) == 4: return payload_status_named(sys.argv[3])
            print(PAYLOAD_HELP.rstrip()); return 1
        if sub == "start":
            if len(sys.argv) < 4: print("usage: p4wnctl payload start <name>"); return 1
            return payload_start(sys.argv[3])
        if sub == "run-now":
            nm = sys.argv[3] if len(sys.argv) >= 4 else "active"
            return payload_run_now(nm)
        if sub == "stop":
            if len(sys.argv) < 4: print("usage: p4wnctl payload stop <name>"); return 1
            return payload_stop(sys.argv[3])
        if sub == "logs":
            if len(sys.argv) < 4: print("usage: p4wnctl payload logs <name>"); return 1
            return payload_logs(sys.argv[3])
        if sub == "describe":
            if len(sys.argv) < 4: print("usage: p4wnctl payload describe <name>"); return 1
            return payload_describe(sys.argv[3])

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
        if sub == "url":     return web_url()
        if sub == "config":
            if len(sys.argv) == 3:
                print(WEB_HELP.rstrip()); return 0
            action = sys.argv[3].lower()
            if action == "show": return web_config_show()
            if action == "set":
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

    # service
    if cmd == "service":
        if len(sys.argv) < 4:
            print(SERVICE_HELP.rstrip()); return 1
        action = sys.argv[2].lower()
        unit = sys.argv[3]
        if action == "install":   return svc_install(unit)
        if action == "uninstall": return svc_uninstall(unit)
        if action == "status":
            print(svc_status_text(unit)); return 0
        if action == "logs":
            rc1 = systemctl("status", "--no-pager", unit).returncode
            rc2 = sh(f"journalctl -u {unit} --no-pager -n 100", check=False).returncode
            return rc1 or rc2
        if action in ("start","stop","restart","enable","disable"):
            need_root()
            return systemctl(action, unit).returncode
        print(SERVICE_HELP.rstrip()); return 1

    # ip
    if cmd == "ip":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "show"
        if sub == "show":    return ip_show()
        if sub == "primary": return ip_primary()
        if sub == "env":     return ip_env()
        if sub == "json":    return ip_json()
        return ip_show()

    # template
    if cmd == "template":
        if len(sys.argv) >= 4 and sys.argv[2] == "render":
            return template_render(sys.argv[3])
        print("usage: p4wnctl template render <file>"); return 1

    # menu
    if cmd == "menu":
        try:
            curses.wrapper(tui_menu)
            return 0
        except Exception:
            print("Menu needs an interactive terminal. Try: p4wnctl usb status / web status / service ...")
            return 1

    print(MAIN_HELP.rstrip())
    return 1

if __name__ == "__main__":
    sys.exit(main())
