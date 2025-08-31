#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import json
import time
import curses
import signal
import socket
import subprocess
from pathlib import Path
from textwrap import dedent
from string import Template
from ipaddress import ip_interface, IPv4Interface, ip_network

# ======= Paths / constants =======
P4WN_HOME = Path(os.environ.get("P4WN_HOME", "/opt/p4wnp1"))
HOOKS = P4WN_HOME / "hooks"
CONFIG = P4WN_HOME / "config"
USB_GADGET = Path("/sys/kernel/config/usb_gadget/p4wnp1")
ACTIVE_PAYLOAD_FILE = CONFIG / "active_payload"
RUN_DIR      = Path("/run/p4wnp1")

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

# Payloads web server (static files for HID/NET payloads)
PAYLOADS_ROOT = P4WN_HOME / "payloads" / "www"
PAYLOADS_WEB_UNIT = "p4wnp1-payloads.service"
PAYLOADS_WEB_OVERRIDE_DIR  = Path("/etc/systemd/system") / f"{PAYLOADS_WEB_UNIT}.d"
PAYLOADS_WEB_OVERRIDE_FILE = PAYLOADS_WEB_OVERRIDE_DIR / "override.conf"
# TLS bits for payloads HTTPS
PAYLOADS_TLS_DIR = CONFIG / "tls"
PAYLOADS_CERT = PAYLOADS_TLS_DIR / "payloads.crt"
PAYLOADS_KEY  = PAYLOADS_TLS_DIR / "payloads.key"

PAYLOADS_HTTPS_UNIT = "p4wnp1-payloads-https.service"
PAYLOADS_HTTPS_OVERRIDE_DIR  = Path("/etc/systemd/system") / f"{PAYLOADS_HTTPS_UNIT}.d"
PAYLOADS_HTTPS_OVERRIDE_FILE = PAYLOADS_HTTPS_OVERRIDE_DIR / "override.conf"

# Persisted USB identity
USB_ID_FILE = CONFIG / "usb.json"
LAST_MODE_FILE = CONFIG / "usb.last_mode"

# --- Wi-Fi portal paths ---
PORTAL_DIR = P4WN_HOME / "services" / "portal"
PORTAL_BIN = PORTAL_DIR / "bin" / "portal_ctl.py"
PORTAL_APACHE_VHOST = PORTAL_DIR / "conf" / "p4wnp1-portal.conf"   # informational

LURE_PID   = RUN_DIR / "wifi_lure.pid"
LURE_STATE = RUN_DIR / "wifi_lure.json"
LURE_LIST  = Path("/opt/p4wnp1/config/lure_ssids.txt")
LURE_CFG   = Path("/opt/p4wnp1/config/lure.json")

# Known units for Services submenu (optional convenience)
SERVICE_UNITS = [
    ("Core", "p4wnp1.service"),
    ("OLED Menu", "oledmenu.service"),
]

USB_CHOICES = [
    ("HID only", "hid"),
    ("Storage only", "storage"),
    ("Serial only", "serial"),
    ("HID + Storage", "hid_storage"),
    ("HID + Serial", "hid_acm"),
    ("HID + RNDIS (Windows)", "hid_rndis"),
    ("HID + NCM (Win/macOS/Linux)", "hid_ncm"),
    ("HID + ECM (macOS/Linux)", "hid_ecm"),
    ("HID + RNDIS + Serial", "hid_rndis_acm"),
    ("HID + NCM + Serial", "hid_ncm_acm"),
    ("HID + NET + Serial (legacy)", "hid_net_acm"),
    ("HID + RNDIS + Storage", "hid_storage_rndis"),
    ("HID + NCM + Storage", "hid_storage_ncm"),
    ("HID + ECM + Storage", "hid_storage_ecm"),
    ("HID + NET(all) + Storage", "hid_storage_net"),
]

# Defaults for Wifi AP (persisted in CONFIG/ap.json; no env required)
AP_SETTINGS_FILE = CONFIG / "ap.json"
AP_SSID   = "P4WNP1"
AP_PSK    = "p4wnp1o2"          # 8+ chars
AP_CIDR   = "10.36.1.1/24"
AP_CHAN   = 6
AP_COUNTRY= "ES"
AP_HIDDEN = False

AP_HOSTAPD_PID  = RUN_DIR / "hostapd.wlan0.pid"
AP_DNSMASQ_PID  = RUN_DIR / "dnsmasq.ap.pid"
AP_DNSMASQ_CONF = RUN_DIR / "dnsmasq.ap.conf"
AP_HOSTAPD_CONF = Path("/etc/hostapd/hostapd-p4wnp1.conf")
AP_HOSTAPD_LOG = RUN_DIR / "hostapd.ap.log"
AP_DNSMASQ_LOG = RUN_DIR / "dnsmasq.ap.log"

# --- Bluetooth scan files ---
BT_SCAN_PID  = RUN_DIR / "ble_scan.pid"
BT_SCAN_LOG  = RUN_DIR / "ble_scan.jsonl"

USB_NET_DEVADDR = os.environ.get("P4WN_USB_DEVADDR", "02:1A:11:00:00:01")
USB_NET_HOSTADDR = os.environ.get("P4WN_USB_HOSTADDR", "02:1A:11:00:00:02")
USB0_CIDR = os.environ.get("P4WN_USB0_CIDR", "10.13.37.1/24")
MSD_IMAGE = Path(os.environ.get("P4WN_MSD_IMAGE", str(CONFIG / "mass_storage.img")))
MSD_SIZE_MB = int(os.environ.get("P4WN_MSD_SIZE_MB", "128"))

# ------------ PID helpers -------------
def write_pid(path: Path, pid: int) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(int(pid)))
    except Exception:
        pass

def read_pid(path: Path) -> int | None:
    try:
        if path.exists():
            v = int((path.read_text().strip() or "0"))
            return v if v > 0 and Path(f"/proc/{v}").exists() else None
    except Exception:
        return None
    return None

# ------------ Small helpers ------------
def sh(cmd: str, check=True, input: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check, input=input)

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

def ensure_mass_storage_image(img=str(MSD_IMAGE), size_mb=MSD_SIZE_MB):
    """
    Back-compat wrapper. Sets MSD_IMAGE/MSD_SIZE_MB then calls _ensure_msd_image().
    """
    global MSD_IMAGE, MSD_SIZE_MB
    MSD_IMAGE = Path(img)
    MSD_SIZE_MB = int(size_mb)
    _ensure_msd_image()
    return str(MSD_IMAGE)

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

# ------------ Service management (generic) ------------
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

# ------------ USB (configfs builder, no legacy g_* modules) ------------
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
              "    Enable the USB OTG controller and reboot.\n"
              "    EITHER run: p4wnctl usb prep\n"
              "    OR add: dtoverlay=dwc2,dr_mode=peripheral to /boot/firmware/config.txt and reboot.",
              file=sys.stderr)
        sys.exit(3)

def _boot_config_candidates() -> list[Path]:
    return [Path("/boot/firmware/config.txt"), Path("/boot/config.txt")]

def _boot_config_path() -> Path | None:
    for p in _boot_config_candidates():
        if p.exists():
            return p
    return None

def _disable_otg_mode(lines: list[str]) -> tuple[list[str], bool]:
    """
    Comment out any 'otg_mode=...' lines (Bookworm defaults often set otg_mode=1).
    Returns (new_lines, changed)
    """
    changed = False
    out = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("otg_mode="):
            # comment it so users can see the prior value
            out.append(f"# P4wnP1-O2 disabled: {ln}".rstrip())
            changed = True
        else:
            out.append(ln)
    return out, changed

def _ensure_peripheral_under_all() -> tuple[bool, str]:
    """
    Ensure dtoverlay=dwc2,dr_mode=peripheral exists under an [all] section
    in /boot/firmware/config.txt (fallback to /boot/config.txt).
    Also disables any otg_mode=... lines.
    Returns (changed, path_str)
    """
    p = _boot_config_path()
    if not p:
        return (False, "(no config.txt found)")
    text = p.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    # 1) Disable otg_mode
    lines, ch_otg = _disable_otg_mode(lines)

    # 2) Find last [all] section
    all_idxs = [i for i, ln in enumerate(lines) if ln.strip().lower() == "[all]"]
    if all_idxs:
        start = all_idxs[-1] + 1
        # find end of this section (next [section] or EOF)
        end = next((i for i in range(start, len(lines)) if lines[i].strip().startswith("[") and lines[i].strip().endswith("]")), len(lines))

        # scan for existing dwc2 line inside this [all]
        dwc_idx = None
        for i in range(start, end):
            if lines[i].strip().startswith("dtoverlay=dwc2"):
                dwc_idx = i
                break

        desired = "dtoverlay=dwc2,dr_mode=peripheral"
        ch_overlay = False
        if dwc_idx is None:
            lines.insert(end, desired)
            ch_overlay = True
        else:
            s = lines[dwc_idx].strip()
            if "dr_mode=peripheral" not in s:
                lines[dwc_idx] = desired
                ch_overlay = True
    else:
        # no [all] — append a fresh section at the end
        desired = ["", "# Added by P4wnP1-O2 usb prep", "[all]", "dtoverlay=dwc2,dr_mode=peripheral"]
        lines.extend(desired)
        ch_overlay = True

    changed = ch_otg or ch_overlay
    if changed:
        need_root()
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return (changed, str(p))

def _ensure_modules_load_conf() -> tuple[bool, str]:
    """
    Ensure /etc/modules-load.d/p4wnp1-usb.conf loads dwc2 and libcomposite.
    Returns (changed, path_str).
    """
    path = Path("/etc/modules-load.d/p4wnp1-usb.conf")
    desired = "dwc2\nlibcomposite\n"
    cur = path.read_text() if path.exists() else ""
    if cur != desired:
        need_root()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(desired)
        return (True, str(path))
    return (False, str(path))

def usb_prep() -> int:
    """
    Prepare the system for USB gadget mode (dwc2 overlay + modules-load).
    Requires a reboot to take effect.
    """
    need_root()
    # Make sure configfs is available now (harmless if already active)
    sh("modprobe configfs || true", check=False)
    sh("mount -t configfs none /sys/kernel/config || true", check=False)

    ch1, cfgp = _ensure_peripheral_under_all()
    ch2, mlp  = _ensure_modules_load_conf()

    print(f"Boot config: {cfgp} {'(updated)' if ch1 else '(ok)'}")
    print(f"Modules-load: {mlp} {'(updated)' if ch2 else '(ok)'}")
    print("\nReboot required for the USB Device Controller (UDC) to appear.")
    print("After reboot, run:  p4wnctl usb set hid_net")
    return 0

def usb_replug() -> int:
    """
    Re-enumerate without physically unplugging.
    Strategy:
      1) Stop services holding endpoints, detach MSD LUN, ensure MSD link exists.
      2) Retry clean unbind/rebind a few times (backoff).
      3) If still failing, rebuild from the persisted preset.
    """
    need_root()
    udc_file = USB_GADGET / "UDC"
    if not udc_file.exists():
        print("[!] No gadget bound (UDC file missing).", file=sys.stderr)
        return 2

    # Make success more likely up front
    systemctl("stop", "serial-getty@ttyGS0.service")
    systemctl("stop", "ModemManager.service")
    _msd_detach()
    _ensure_msd_link_present()

    # Read the current UDC name (best-effort)
    try:
        current = udc_file.read_text().strip()
    except Exception:
        current = ""

    # helper: retry a write a few times
    def _retry_write(path: Path, val: str, tries=6, delay=0.25) -> bool:
        for i in range(tries):
            try:
                path.write_text(val)
                return True
            except OSError:
                time.sleep(delay)
        return False

    # Try clean unbind
    if not _retry_write(udc_file, ""):
        print("[*] Clean unbind failed (EBUSY).", file=sys.stderr)
    else:
        # Re-attach the LUN now; it doesn't block rebind
        _msd_attach()
        # Try rebind to same (preferred) or first available UDC
        udcs = sorted([p.name for p in Path("/sys/class/udc").iterdir()])
        reb = current if current in udcs else (udcs[0] if udcs else "")
        if not reb:
            print("[!] No UDC available to rebind.", file=sys.stderr)
            _ensure_msd_link_present(); _msd_attach()
            return 4
        if _retry_write(udc_file, reb):
            print(f"Replugged on UDC: {reb}")
            return 0
        else:
            print("[*] Clean rebind failed (EBUSY).", file=sys.stderr)
            # make sure MSD didn't get lost
            _ensure_msd_link_present(); _msd_attach()

    # ---- Fallback: full preset rebuild (always restores exact mode) ----
    preset = ""
    try:
        if LAST_MODE_FILE.exists():
            preset = LAST_MODE_FILE.read_text().strip()
    except Exception:
        pass

    try:
        usb_force_reset()
        if preset:
            rc = usb_apply_mode(preset)
            if rc == 0:
                print(f"Replugged by preset rebuild: {preset}")
                return 0
            print(f"[*] Preset rebuild ({preset}) failed (rc={rc}); trying snapshot…", file=sys.stderr)

        # Snapshot rebuild (exact links)
        caps = usb_caps_now()
        _msd_detach()
        usb_teardown()
        _gadget_common_init()
        cfg = USB_GADGET / "configs/c.1"
        if caps.get("hid"):    _link(_func_hid(), cfg)
        if caps.get("ecm"):    _link(_func_ecm(), cfg)
        if caps.get("rndis"):  _link(_func_rndis(), cfg)
        if caps.get("msd"):    _link(_func_msd(), cfg)
        if caps.get("acm"):    _link(_func_acm(), cfg)
        if caps.get("ncm"):    _link(_func_ncm(), cfg)
        if caps.get("rndis"):
            _enable_ms_os_desc_for_rndis("c.1", "rndis.usb0")
        _bind_first_udc()
        _ensure_usb0_ip()
        print("Replugged by snapshot rebuild.")
        return 0
    except Exception as e2:
        print(f"[!] Replug (rebuild) failed: {e2}", file=sys.stderr)
        # final safety so we don't end half-configured
        _ensure_msd_link_present(); _msd_attach()
        return 1

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
    """
    Ensure MSD image exists at MSD_IMAGE with size MSD_SIZE_MB and is FAT32 formatted.
    """
    MSD_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    target_sz = MSD_SIZE_MB * 1024 * 1024
    need_create = (not MSD_IMAGE.exists()) or (MSD_IMAGE.stat().st_size < target_sz)
    if need_create:
        # (Re)create image file
        with open(MSD_IMAGE, "wb") as f:
            f.truncate(target_sz)
        # Try to format as FAT32 (mkfs.vfat or mkdosfs). If unavailable, leave raw.
        mkfs = which("mkfs.vfat") or which("mkdosfs")
        if mkfs:
            sh(f'{mkfs} -F 32 -n P4WNP1 "{MSD_IMAGE}"', check=False)

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
    _msd_detach()   # <— IMPORTANT: free the LUN to avoid EBUSY
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

    # Load persisted VID/PID + strings (or defaults)
    ids = usb_id_load()
    _write(USB_GADGET / "idVendor",  ids.get("vid", "0x1d6b"))
    _write(USB_GADGET / "idProduct", ids.get("pid", "0x0104"))

    _write(USB_GADGET / "bcdDevice", "0x0100")
    _write(USB_GADGET / "bcdUSB",    "0x0200")
    _write(USB_GADGET / "bDeviceClass",    "0xEF")
    _write(USB_GADGET / "bDeviceSubClass", "0x02")
    _write(USB_GADGET / "bDeviceProtocol", "0x01")

    s  = USB_GADGET / "strings/0x409"
    st = ids.get("strings") or {}
    _write(s / "serialnumber", st.get("serial",       "P4wnP1-O2"))
    _write(s / "manufacturer", st.get("manufacturer", "quasialex"))
    _write(s / "product",      st.get("product",      "P4wnP1-O2 Gadget"))

    cfg = USB_GADGET / "configs/c.1"
    _write(cfg / "MaxPower", "250")
    _write(USB_GADGET / "configs/c.1/strings/0x409/configuration", "Config 1")

    # MS OS descriptors (global)
    osd = USB_GADGET / "os_desc"
    try:
        _write(osd / "b_vendor_code", "0xcd")  # any non-zero vendor-specific code
        _write(osd / "qw_sign", "MSFT100")
        _write(osd / "use", "1")
    except Exception:
        pass

def usb_id_load() -> dict:
    d = {
        "vid": "0x1d6b",
        "pid": "0x0104",
        "strings": {
            "serial": "P4wnP1-O2",
            "manufacturer": "quasialex",
            "product": "P4wnP1-O2 Gadget",
        },
    }
    try:
        if USB_ID_FILE.exists():
            j = json.loads(USB_ID_FILE.read_text())
            if isinstance(j, dict):
                d.update({k: j.get(k, d[k]) for k in ("vid", "pid")})
                sj = (j.get("strings") or {}) if isinstance(j.get("strings"), dict) else {}
                d["strings"] = {**d["strings"], **sj}
    except Exception:
        pass
    return d

def usb_id_save(vid: str | None=None, pid: str | None=None, **strings):
    cur = usb_id_load()
    if vid: cur["vid"] = vid
    if pid: cur["pid"] = pid
    if strings:
        cur["strings"] = {**(cur.get("strings") or {}), **strings}
    USB_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    USB_ID_FILE.write_text(json.dumps(cur, indent=2))

def usb_id_show() -> int:
    d = usb_id_load()
    s = d.get("strings") or {}
    print(f"VID={d['vid']} PID={d['pid']}")
    print(f'serial="{s.get("serial","")}" manufacturer="{s.get("manufacturer","")}" product="{s.get("product","")}"')
    return 0

def usb_id_set(vid: str, pid: str) -> int:
    if not (vid.lower().startswith("0x") and pid.lower().startswith("0x")):
        print("[!] Use hex like 0x1d6b 0x0104", file=sys.stderr); return 1
    usb_id_save(vid=vid, pid=pid)
    print(f"Saved VID/PID: {vid} {pid} (replug to apply)")
    return 0

def usb_id_strings(serial: str | None=None, manufacturer: str | None=None, product: str | None=None) -> int:
    filt = {k:v for k,v in {
        "serial": serial, "manufacturer": manufacturer, "product": product
    }.items() if v is not None}
    if not filt:
        print('usage: p4wnctl usb id strings [--serial s] [--manufacturer m] [--product p]')
        return 1
    usb_id_save(**filt)
    print("Saved USB strings (replug to apply).")
    return 0

def usb_id_reset() -> int:
    try: USB_ID_FILE.unlink()
    except Exception: pass
    print("USB identity reset to defaults (replug to apply).")
    return 0

def _set_vid_pid(vid: str, pid: str):
    """
    Override vendor/product IDs (must be called before binding the UDC).
    """
    _write(USB_GADGET / "idVendor", vid)
    _write(USB_GADGET / "idProduct", pid)

def _enable_ms_os_desc_for_rndis(config_name="c.1", func_name="rndis.usb0"):
    """
    Link the active config into os_desc (required for Windows to see MSFT100).
    Call after configs exist but before binding the UDC.
    """
    osd = USB_GADGET / "os_desc"
    link_target = USB_GADGET / "configs" / config_name
    link_name   = osd / config_name
    try:
        if link_name.exists() or link_name.is_symlink():
            link_name.unlink()
        os.symlink(link_target, link_name)
    except Exception as e:
        print(f"[!] os_desc link failed: {e}", file=sys.stderr)

def _func_hid():
    f = USB_GADGET / "functions/hid.usb0"
    f.mkdir(parents=True, exist_ok=True)
    _write(f / "protocol", "1")
    _write(f / "subclass", "1")
    _write(f / "report_length", "8")
    _write(f / "report_desc", _hid_report_desc_bytes())
    return f

def _func_ncm():
    f = USB_GADGET / "functions/ncm.usb0"
    f.mkdir(parents=True, exist_ok=True)
    _write(f / "dev_addr", USB_NET_DEVADDR)
    _write(f / "host_addr", USB_NET_HOSTADDR)
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

    # --- MS OS descriptors (interface level; must happen BEFORE linking) ---
    intf = f / "os_desc" / "interface.rndis"
    if intf.exists():
        try:
            _write(intf / "compatible_id", "RNDIS")
            _write(intf / "sub_compatible_id", "5162001")
        except Exception:
            pass
    else:
        # fallback for older kernels exposing files directly under f/os_desc
        f_osd = f / "os_desc"
        if f_osd.exists():
            try:
                _write(f_osd / "compatible_id", "RNDIS")
                _write(f_osd / "sub_compatible_id", "5162001")
                _write(f_osd / "use", "1")
            except Exception:
                pass

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

def _msd_detach():
    """
    Safely detach the mass-storage LUN so configfs ops don't fail with EBUSY.
    We try 'eject' if available, else blank the 'file' attribute.
    """
    f = USB_GADGET / "functions/mass_storage.usb0"
    if not f.exists():
        return
    eject = f / "lun.0/eject"
    if eject.exists():
        try:
            eject.write_text("1")
            time.sleep(0.1)
            return
        except Exception:
            pass
    file_attr = f / "lun.0/file"
    if file_attr.exists():
        try:
            file_attr.write_text("")   # detach backing file
            time.sleep(0.1)
        except Exception:
            pass

def _msd_attach(path: str | None = None):
    """
    Re-attach the MSD LUN to the backing file (defaults to MSD_IMAGE).
    """
    if path is None:
        path = str(MSD_IMAGE)
    f = USB_GADGET / "functions/mass_storage.usb0" / "lun.0" / "file"
    try:
        f.write_text(path)
        time.sleep(0.1)
    except Exception:
        pass

def _msd_linked() -> bool:
    return (USB_GADGET / "configs/c.1/mass_storage.usb0").exists() and \
           (USB_GADGET / "functions/mass_storage.usb0").exists()

def _ensure_msd_link_present():
    """If the MSD function exists but the c.1 symlink was lost, restore it."""
    f = USB_GADGET / "functions/mass_storage.usb0"
    cfg = USB_GADGET / "configs/c.1"
    ln = cfg / "mass_storage.usb0"
    if f.exists() and not ln.exists():
        try: ln.symlink_to(f)
        except Exception: pass

def _rndis_inf_text(vid="0525", pid="A4A2") -> str:
    txt = dedent(f"""\
    ; P4wnP1-O2 RNDIS binding to inbox driver
    [Version]
    Signature="$Windows NT$"
    Class=Net
    ClassGuid={{4d36e972-e325-11ce-bfc1-08002be10318}}
    Provider=%Provider%
    DriverVer=07/01/2021,10.0.19041.1

    [Manufacturer]
    %Provider%=DeviceList,NTamd64

    [DeviceList.NTamd64]
    %RNDIS.DeviceDesc%=RNDIS_Install, USB\\VID_{vid}&PID_{pid}

    [RNDIS_Install.NT]
    Include=netrndis.inf
    Needs=netrndis.ndis6

    [Strings]
    Provider="P4wnP1-O2"
    RNDIS.DeviceDesc="USB Ethernet (RNDIS) Gadget"
    """).strip("\n")
    # Ensure CRLF line endings for Windows
    return "\r\n".join(txt.splitlines()) + "\r\n"

def usb_inf_write() -> int:
    """
    Mount the MSD image and write an INF file for quick manual binding on Windows.
    """
    need_root()
    _ensure_msd_image()
    # Detach LUN while we modify the image to avoid EBUSY/corruption
    _msd_detach()
    mnt = Path("/mnt/p4wnp1_msd")
    mnt.mkdir(parents=True, exist_ok=True)
    cp = sh(f"mount -o loop,uid=0,gid=0 {MSD_IMAGE} {mnt}", check=False)
    if cp.returncode != 0:
        sys.stderr.write(cp.stderr or "")
        print("[!] Could not mount MSD image; is it in use?", file=sys.stderr)
        return 1
    try:
        d = mnt / "RNDIS"
        d.mkdir(exist_ok=True)
        inf = d / "P4wnP1-O2-RNDIS.inf"

        # read current gadget VID/PID (e.g. "0x1d6b" → "1D6B")
        vid_txt = (USB_GADGET / "idVendor").read_text().strip()
        pid_txt = (USB_GADGET / "idProduct").read_text().strip()
        vid = vid_txt.replace("0x", "").replace("0X", "").upper().zfill(4)
        pid = pid_txt.replace("0x", "").replace("0X", "").upper().zfill(4)

        inf.write_text(_rndis_inf_text(vid, pid))

        print(f"Wrote {inf}")
    finally:
        sh(f"umount {mnt}", check=False)
    # Re-attach LUN so host sees the updated content
    _msd_attach()

    return 0

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

# ------------ USB0 DHCP + NAT helpers ------------

DNSMASQ_PID  = RUN_DIR / "dnsmasq.usb0.pid"
DNSMASQ_CONF = RUN_DIR / "dnsmasq.usb0.conf"
WPA_CONF = RUN_DIR / "wpa_supplicant-wlan0.conf"
WPA_PID  = RUN_DIR / "wpa_supplicant.wlan0.pid"
DHCLIENT_PID = RUN_DIR / "dhclient.wlan0.pid"

def _wpa_conf_text(ssid: str, psk: str, hidden: bool=False) -> str:
    # scan_ssid=1 helps find hidden networks
    scan = "1" if hidden else "0"
    return f"""\
    ctrl_interface=/run/wpa_supplicant
    update_config=1
    country={AP_COUNTRY}

    network={{
        ssid="{ssid}"
        psk="{psk}"
        key_mgmt=WPA-PSK
        scan_ssid={scan}
    }}
    """

def _dnsmasq_conf_text() -> str:
    return "\n".join([
        "interface=usb0",
        "bind-interfaces",
        "dhcp-range=10.13.37.100,10.13.37.200,255.255.255.0,1h",
        "dhcp-option=3,10.13.37.1",                      # gateway
        "dhcp-option=6,1.1.1.1,9.9.9.9",                 # DNS
        "domain-needed",
        "bogus-priv",
        "no-resolv",
        "log-queries",
        "log-dhcp",
    ]) + "\n"

def usb_dhcp_start() -> int:
    need_root()
    _ensure_usb0_ip()
    if not which("dnsmasq"):
        print("[!] dnsmasq not installed", file=sys.stderr); return 2
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    DNSMASQ_CONF.write_text(_dnsmasq_conf_text())
    if DNSMASQ_PID.exists():
        usb_dhcp_stop()
    cp = sh(f"dnsmasq --conf-file={DNSMASQ_CONF} --pid-file={DNSMASQ_PID}", check=False)
    if cp.returncode != 0:
        sys.stderr.write(cp.stderr or "")
        print("[!] dnsmasq failed", file=sys.stderr)
        return 1
    print("DHCP: started on usb0 (dnsmasq).")
    return 0

def usb_dhcp_stop() -> int:
    need_root()
    if DNSMASQ_PID.exists():
        try:
            pid = int(DNSMASQ_PID.read_text().strip() or "0")
            if pid > 0:
                os.kill(pid, 15)
                time.sleep(0.2)
        except Exception:
            pass
        DNSMASQ_PID.unlink(missing_ok=True)
    # kill stray dnsmasq on our conf
    sh("pkill -f dnsmasq.*dnsmasq.usb0.conf", check=False)
    print("DHCP: stopped.")
    return 0

def usb_dhcp_status() -> int:
    print("DHCP:", "running" if DNSMASQ_PID.exists() else "stopped")
    return 0

NFT_RULESET = Template("""
table inet p4wnp1 {
  chain fwd {
    type filter hook forward priority filter;
    ct state established,related accept
    iifname "usb0" oifname "$uplink" accept
    iifname "$uplink" oifname "usb0" ct state established,related accept
  }
  chain post {
    type nat hook postrouting priority srcnat;
    oifname "$uplink" masquerade
  }
}
""")

def net_share_start(uplink: str) -> int:
    need_root()
    if not which("nft"):
        print("[!] nftables (nft) not installed", file=sys.stderr); return 2

    Path("/proc/sys/net/ipv4/ip_forward").write_text("1\n")

    # wipe any previous table, then (re)create
    sh("nft delete table inet p4wnp1", check=False)
    rc = sh("nft add table inet p4wnp1", check=False).returncode
    if rc != 0:
        print("[!] nftables: cannot add table 'inet p4wnp1'", file=sys.stderr)
        return 1

    # chains (quote braces so the shell doesn't eat them)
    sh("nft 'add chain inet p4wnp1 fwd  { type filter hook forward priority 0; policy accept; }'", check=False)
    sh("nft 'add chain inet p4wnp1 post { type nat    hook postrouting priority srcnat; policy accept; }'", check=False)

    # rules
    sh("nft add rule inet p4wnp1 fwd ct state established,related accept", check=False)
    sh(f"nft add rule inet p4wnp1 fwd iifname usb0  oifname {uplink} accept", check=False)
    sh(f"nft add rule inet p4wnp1 fwd iifname {uplink} oifname usb0 ct state established,related accept", check=False)
    sh(f"nft add rule inet p4wnp1 post oifname {uplink} masquerade", check=False)

    print(f"NAT: usb0 -> {uplink} enabled.")
    return 0

def net_share_stop() -> int:
    need_root()
    sh("nft delete table inet p4wnp1", check=False)
    print("NAT: disabled.")
    return 0

def usb_apply_mode(mode: str) -> int:
    need_root()
    usb_preflight()
    usb_teardown()
    _gadget_common_init()
    cfg = USB_GADGET / "configs/c.1"

    if mode == "hid_net":
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)
        _link(_func_rndis(), cfg)
    elif mode == "hid_acm":
        _link(_func_hid(), cfg)
        _link(_func_acm(), cfg)
    elif mode == "hid_storage":
        _link(_func_hid(), cfg)
        _link(_func_msd(), cfg)
    elif mode == "hid_rndis":
        _link(_func_hid(), cfg)
        _link(_func_rndis(), cfg)
    elif mode == "hid_ecm":
        # macOS/Linux: HID + ECM only
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)    
    elif mode == "hid_ncm":
        _link(_func_hid(), cfg)
        _link(_func_ncm(), cfg)
    elif mode == "hid_storage_ncm":
        _link(_func_hid(), cfg)
        _link(_func_ncm(), cfg)
        _link(_func_msd(), cfg)
    elif mode == "hid_storage_ecm":
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)
        _link(_func_msd(), cfg)
    elif mode == "hid_ncm_acm":
        _link(_func_hid(), cfg)
        _link(_func_ncm(), cfg)
        _link(_func_acm(), cfg)
    elif mode == "hid_storage_net":
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)
        _link(_func_rndis(), cfg)
        _link(_func_msd(), cfg)
    elif mode == "hid_storage_rndis":
        _link(_func_hid(), cfg)
        _link(_func_rndis(), cfg)
        _link(_func_msd(), cfg) 
    elif mode == "hid_net_acm":
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)
        _link(_func_rndis(), cfg)
        _link(_func_acm(), cfg)
    elif mode == "hid_rndis_acm":
        _link(_func_rndis(), cfg)
        _link(_func_acm(), cfg)
        _link(_func_hid(), cfg)
    elif mode == "hid_storage_net_acm":
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)
        _link(_func_rndis(), cfg)
        _link(_func_msd(), cfg)
        _link(_func_acm(), cfg)
    elif mode == "storage":
        _link(_func_msd(), cfg)
    elif mode == "hid":
        _link(_func_hid(), cfg)
    elif mode == "serial":
        _link(_func_acm(), cfg)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        return 4

    # --- MS OS descriptors for Windows RNDIS ---
    if (USB_GADGET / "functions" / "rndis.usb0").exists():
        _enable_ms_os_desc_for_rndis("c.1", "rndis.usb0")
    # -------------------------------------------

    try:
        _ensure_msd_link_present()
        _bind_first_udc()
    except Exception as e:
        print(f"Bind failed: {e}", file=sys.stderr)
        # If we intended to have MSD but its link got lost somehow, restore it
        _ensure_msd_link_present()        
        return 6

    _ensure_usb0_ip()
    # Persist last applied mode
    try:
        LAST_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_MODE_FILE.write_text(mode)
    except Exception:
        pass
    return 0

def usb_caps_now() -> dict:
    """
    Detect currently ACTIVE functions by inspecting the c.1 config links,
    not by the presence of function directories.
    """
    cfg = USB_GADGET / "configs" / "c.1"
    def linked(name: str) -> bool:
        return (cfg / name).exists()
    caps = {
        "hid":   linked("hid.usb0"),
        "rndis": linked("rndis.usb0"),
        "ecm":   linked("ecm.usb0"),
        "ncm":   linked("ncm.usb0"),
        "msd":   linked("mass_storage.usb0"),
        "acm":   linked("acm.usb0"),
    }
    caps["net"] = caps["rndis"] or caps["ecm"] or caps["ncm"] 
    return caps

def _iface_carrier(ifname="usb0") -> bool:
    p = Path(f"/sys/class/net/{ifname}/carrier")
    try:
        return p.exists() and p.read_text().strip() == "1"
    except Exception:
        return False

def usb_auto(timeout_sec: int = 8) -> int:
    """
    Try in order: RNDIS (Windows), NCM (Windows 10/11, macOS, Linux), ECM (macOS/Linux).
    Uses link-carrier as success signal (driver must bind on host).
    """
    print("Auto: trying HID+RNDIS...")
    rc = usb_apply_mode("hid_rndis")
    if rc != 0:
        return rc
    for _ in range(timeout_sec * 10):
        if _iface_carrier("usb0"):
            print("Auto: RNDIS linked.")
            return 0
        time.sleep(0.1)

    print("Auto: no RNDIS link, trying HID+NCM...")
    rc = usb_apply_mode("hid_ncm")
    if rc != 0:
        return rc
    for _ in range(timeout_sec * 10):
        if _iface_carrier("usb0"):
            print("Auto: NCM linked.")
            return 0
        time.sleep(0.1)

    print("Auto: no NCM link, trying HID+ECM...")
    rc = usb_apply_mode("hid_ecm")
    if rc != 0:
        return rc
    for _ in range(timeout_sec * 10):
        if _iface_carrier("usb0"):
            print("Auto: ECM linked.")
            return 0
        time.sleep(0.1)

    print("Auto: no link established; leaving HID+ECM active.")
    return 1

def usb_compose_apply(hid: bool, net: bool, msd: bool, acm: bool = False, nettype: str = "all") -> int:
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
        if nettype in ("all", "ecm"):   _link(_func_ecm(), cfg)
        if nettype in ("all", "rndis"): _link(_func_rndis(), cfg)
        if nettype in ("all", "ncm"):   _link(_func_ncm(),   cfg)
    if msd: _link(_func_msd(), cfg)
    if acm: _link(_func_acm(), cfg)
    if net:
        _enable_ms_os_desc_for_rndis("c.1", "rndis.usb0")

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
    ncm   = (funcs / "ncm.usb0").exists()
    ecm   = (funcs / "ecm.usb0").exists()
    msd   = (funcs / "mass_storage.usb0").exists()
    acm   = (funcs / "acm.usb0").exists()

    # derive explicit mode name
    if    hid and not (rndis or ncm or ecm or msd or acm):          mode = "hid"
    elif  msd and not (hid or rndis or ncm or ecm or acm):          mode = "storage"
    elif  acm and not (hid or rndis or ncm or ecm or msd):          mode = "serial"
    elif  hid and msd and not (rndis or ncm or ecm or acm):         mode = "hid_storage"
    elif  hid and acm and not (rndis or ncm or ecm or msd):         mode = "hid_acm"
    elif  hid and  rndis and not (ncm or ecm or msd or acm):        mode = "hid_rndis"
    elif  hid and  ncm   and not (rndis or ecm or msd or acm):      mode = "hid_ncm"
    elif  hid and  ecm   and not (rndis or ncm or msd or acm):      mode = "hid_ecm"
    elif  hid and  rndis and      (not ncm) and (not ecm) and acm:  mode = "hid_rndis_acm"
    elif  hid and  ncm   and      (not rndis) and (not ecm) and acm:mode = "hid_ncm_acm"
    elif  hid and (rndis or ncm or ecm) and acm and not msd:        mode = "hid_net_acm"
    elif  hid and  rndis and not (ncm or ecm) and msd and not acm:  mode = "hid_storage_rndis"
    elif  hid and  ncm   and not (rndis or ecm) and msd and not acm:mode = "hid_storage_ncm"
    elif  hid and  ecm   and not (rndis or ncm) and msd and not acm:mode = "hid_storage_ecm"
    elif  hid and (rndis or ncm or ecm) and msd and not acm:        mode = "hid_storage_net"
    else:                                                           mode = "custom/unknown"

    parts = []
    if hid: parts.append("HID")
    if rndis or ncm or ecm: parts.append("NET")
    if msd: parts.append("MSD")
    if acm: parts.append("SER")

    lines = [f"USB: {mode} ({'+'.join(parts) if parts else 'none'})"]
    for c in ["c.1"]:
        cdir = USB_GADGET / "configs" / c
        if cdir.exists():
            links = []
            for name in ["hid.usb0","rndis.usb0","ncm.usb0","ecm.usb0","mass_storage.usb0","acm.usb0"]:
                if (cdir / name).exists(): links.append(name.split(".")[0])
            lines.append(f" {c}: {('+'.join(links) if links else 'n/a')}")
    return "\n".join(lines)

def usb_status(_args=None) -> int:
    print(usb_status_text()); return 0

def usb_fixperms() -> int:
    """
    Make /dev/hidg* world-writable for quick testing (use udev for a permanent rule).
    """
    need_root()
    changed = 0
    for i in range(8):
        p = Path(f"/dev/hidg{i}")
        if p.exists():
            try:
                os.chmod(p, 0o666)
                changed += 1
            except Exception as e:
                print(f"[!] chmod {p} failed: {e}", file=sys.stderr)
    print(f"HID perms adjusted on {changed} device(s).")
    return 0

def usb_serial_enable() -> int:
    need_root()
    return systemctl("enable", "--now", "serial-getty@ttyGS0.service").returncode

def usb_serial_disable() -> int:
    need_root()
    return systemctl("disable", "--now", "serial-getty@ttyGS0.service").returncode

def usb_serial_status() -> int:
    st = systemctl("is-active", "serial-getty@ttyGS0.service").stdout.strip() or "unknown"
    en = systemctl("is-enabled", "serial-getty@ttyGS0.service").stdout.strip() or "unknown"
    print(f"serial-getty@ttyGS0: {st} ({en})"); return 0

# ------------------------------- WiFi AP --------------------------------

def _parse_bool_word(v: str) -> bool:
    return str(v).strip().lower() in ("1","true","yes","on","y")

def ap_settings_load() -> dict:
    """
    Load AP settings from CONFIG/ap.json, override module globals so
    hostapd/dnsmasq get fresh values without restarting the process.
    """
    global AP_SSID, AP_PSK, AP_CIDR, AP_CHAN, AP_COUNTRY, AP_HIDDEN
    cur = {
        "ssid": AP_SSID,
        "psk": AP_PSK,
        "cidr": AP_CIDR,
        "chan": AP_CHAN,
        "country": AP_COUNTRY,
        "hidden": bool(AP_HIDDEN),
    }
    try:
        if AP_SETTINGS_FILE.exists():
            data = json.loads(AP_SETTINGS_FILE.read_text())
            if isinstance(data, dict):
                cur.update(data)
    except Exception:
        pass

    # type/validation guards (cheap)
    cur["ssid"]    = str(cur["ssid"])
    cur["psk"]     = str(cur["psk"])
    cur["cidr"]    = str(cur["cidr"])
    cur["chan"]    = int(cur["chan"])
    cur["country"] = str(cur["country"])
    cur["hidden"]  = bool(cur["hidden"])

    # push into globals for functions which reference AP_* directly
    AP_SSID, AP_PSK, AP_CIDR, AP_CHAN, AP_COUNTRY, AP_HIDDEN = (
        cur["ssid"], cur["psk"], cur["cidr"], cur["chan"], cur["country"], cur["hidden"]
    )
    return cur
def ap_settings_save(**updates) -> dict:
    """
    Update and persist AP settings; returns the merged dict.
    """
    cur = ap_settings_load()
    cur.update(updates or {})
    # minimal validation here; setters do the heavy checks
    AP_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    AP_SETTINGS_FILE.write_text(json.dumps(cur, indent=2))
    # reflect into globals immediately
    return ap_settings_load()

def wifi_relay_start() -> int:
    rc = usb_dhcp_start()
    if rc != 0:
        return rc
    upl = default_route_iface() or "wlan0"
    return net_share_start(upl)

def wifi_relay_stop() -> int:
    usb_dhcp_stop()
    return net_share_stop()

def wifi_relay_status() -> int:
    usb_dhcp_status()
    rc = sh("nft list table inet p4wnp1", check=False)
    print("NAT:", "enabled" if rc.returncode == 0 else "disabled")
    return 0

def _iw_interfaces() -> list[str]:
    out = sh("iw dev 2>/dev/null | awk '/Interface/ {print $2}'", check=False).stdout or ""
    return [ln.strip() for ln in out.splitlines() if ln.strip()]

def _wifi_force_ap_type() -> None:
    """
    Put wlan0 into AP mode reliably.
    Must be called while wlan0 is DOWN.
    Also delete stale P2P devices which block AP mode on brcmfmac.
    """
    # Nuke any P2P “side-devices” first
    for iface in _iw_interfaces():
        if iface.startswith("p2p-") or iface.startswith("p2p-dev"):
            sh(f"iw dev {iface} del 2>/dev/null || true", check=False)

    # Now force the type while down
    sh("iw dev wlan0 set type __ap 2>/dev/null || iw dev wlan0 set type ap 2>/dev/null || true", check=False)

def _wifi_set_regdom(country: str) -> None:
    if country and len(country) == 2:
        sh(f"iw reg set {country.upper()} 2>/dev/null || true", check=False)

def _hostapd_conf() -> str:
    # refresh globals from persisted config
    ap_settings_load()
    hide = "1" if AP_HIDDEN else "0"
    return dedent(f"""\
    ctrl_interface=/run/hostapd
    interface=wlan0
    driver=nl80211
    ssid={AP_SSID}
    ignore_broadcast_ssid={hide}
    hw_mode=g
    channel={AP_CHAN}
    wmm_enabled=1
    ieee80211n=1
    ieee80211d=1
    country_code={AP_COUNTRY}
    auth_algs=1
    wpa=2
    wpa_key_mgmt=WPA-PSK
    rsn_pairwise=CCMP
    wpa_passphrase={AP_PSK}
    """).strip() + "\n"

def _dnsmasq_conf() -> str:
    # refresh globals from persisted config
    ap_settings_load()
    # derive DHCP range from AP_CIDR
    iface = ip_interface(AP_CIDR)
    if not isinstance(iface, IPv4Interface):
        # fall back to a sane default if user put IPv6
        gw = "172.24.0.1"
        start, end, mask = "172.24.0.100", "172.24.0.200", "255.255.255.0"
    else:
        net = iface.network
        gw = str(iface.ip)
        # heuristics: pick roughly the middle chunk of the pool
        hosts = [str(h) for h in net.hosts()]
        if len(hosts) >= 50:
            start = hosts[max(10, len(hosts)//4)]
            end   = hosts[min(len(hosts)-2, len(hosts)//4 + 100)]
        elif len(hosts) >= 10:
            start = hosts[2]; end = hosts[-3]
        else:
            start = hosts[0]; end = hosts[-1]
        mask = str(net.netmask)

    return dedent(f"""\
    interface=wlan0
    bind-interfaces
    domain-needed
    bogus-priv
    dhcp-range={start},{end},{mask},12h
    dhcp-option=3,{gw}
    dhcp-option=6,8.8.8.8,1.1.1.1
    log-queries
    log-dhcp
    """).strip() + "\n"

def _write_ap_configs():
    need_root()
    AP_HOSTAPD_CONF.parent.mkdir(parents=True, exist_ok=True)
    AP_HOSTAPD_CONF.write_text(_hostapd_conf())
    AP_DNSMASQ_CONF.parent.mkdir(parents=True, exist_ok=True)
    AP_DNSMASQ_CONF.write_text(_dnsmasq_conf())
    return str(AP_HOSTAPD_CONF), str(AP_DNSMASQ_CONF)

def _pid_alive(pidfile: Path) -> bool:
    try:
        pid = int(pidfile.read_text().strip() or "0")
        return pid > 0 and Path(f"/proc/{pid}").exists()
    except Exception:
        return False

def wifi_ap_start() -> int:
    need_root()
    ap_settings_load()  # pull latest SSID/PSK/CIDR/chan/country/hidden

    if not which("hostapd"):
        print("[!] hostapd not installed", file=sys.stderr); return 2
    if not which("dnsmasq"):
        print("[!] dnsmasq not installed", file=sys.stderr); return 2

    # Stop any client stack and managers that could grab wlan0
    wifi_client_disconnect()
    _dhcp_release("wlan0")

    # Extra belt-and-suspenders cleanup for brcmfmac
    sh("pkill -x wpa_supplicant 2>/dev/null || true", check=False)
    sh("pkill -f 'wpa_supplicant.*wlan0' 2>/dev/null || true", check=False)
    # Network managers which might revive STA mode
    systemctl("stop", "dhcpcd.service")
    systemctl("stop", "NetworkManager.service")
    systemctl("stop", "iwd.service")
    systemctl("stop", "wpa_supplicant@wlan0.service")
    systemctl("stop", "wpa_supplicant.service")

    # Reg domain and type
    _wifi_set_regdom(AP_COUNTRY)
    # Bring iface down before changing type
    sh("rfkill unblock wifi || true", check=False)
    ip = which("ip") or "/sbin/ip"
    sh(f"{ip} link set wlan0 down || true", check=False)

    # Force AP type now (must be while down)
    _wifi_force_ap_type()

    # Clean any old addressing and assign our AP IP, then up
    sh(f"{ip} addr flush dev wlan0 || true", check=False)
    sh(f"{ip} addr add {AP_CIDR} dev wlan0", check=False)
    sh(f"{ip} link set wlan0 up", check=False)

    # Write configs (hostapd picks up current AP_* via ap_settings_load())
    hostapd_conf, dnsmasq_conf = _write_ap_configs()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    AP_HOSTAPD_LOG.unlink(missing_ok=True)
    AP_DNSMASQ_LOG.unlink(missing_ok=True)

    # Kill previous AP instances (if any)
    sh("pkill -f 'hostapd.*hostapd-p4wnp1.conf' 2>/dev/null || true", check=False)
    sh("pkill -f dnsmasq.*dnsmasq.ap.conf 2>/dev/null || true", check=False)

    # Start dnsmasq (AP instance)
    cp_d = sh(f"dnsmasq --conf-file={AP_DNSMASQ_CONF} --pid-file={AP_DNSMASQ_PID} --log-facility={AP_DNSMASQ_LOG}", check=False)
    d_ok = _pid_alive(AP_DNSMASQ_PID)
    if not d_ok:
        # Retry as DHCP-only (port 53 conflict)
        sh("pkill -f dnsmasq.*dnsmasq.ap.conf 2>/dev/null || true", check=False)
        cp_d = sh(f"dnsmasq --port=0 --conf-file={AP_DNSMASQ_CONF} --pid-file={AP_DNSMASQ_PID} --log-facility={AP_DNSMASQ_LOG}", check=False)
        d_ok = _pid_alive(AP_DNSMASQ_PID)

    # Start hostapd
    cp_h = sh(f"hostapd -B -f {AP_HOSTAPD_LOG} -P {AP_HOSTAPD_PID} {hostapd_conf}", check=False)
    h_ok = _pid_alive(AP_HOSTAPD_PID)

    # Second retry: reload brcmfmac if still down
    if not h_ok:
        # Driver reload often fixes nl80211 init on Pi
        sh("modprobe -r brcmfmac 2>/dev/null || true", check=False)
        time.sleep(1)
        sh("modprobe brcmfmac 2>/dev/null || true", check=False)

        # Re-assert AP mode and IP
        _wifi_set_regdom(AP_COUNTRY)
        sh(f"{ip} link set wlan0 down || true", check=False)
        _wifi_force_ap_type()
        sh(f"{ip} addr flush dev wlan0 || true", check=False)
        sh(f"{ip} addr add {AP_CIDR} dev wlan0", check=False)
        sh(f"{ip} link set wlan0 up", check=False)

        # Try hostapd again on the persisted config
        cp_h = sh(f"hostapd -B -f {AP_HOSTAPD_LOG} -P {AP_HOSTAPD_PID} {hostapd_conf}", check=False)
        h_ok = _pid_alive(AP_HOSTAPD_PID)

    # If hostapd failed, try the “deep clean” dance and a safe channel
    if not h_ok:
        # delete P2P again, force type again, and try channel 1 once
        _wifi_force_ap_type()
        # patch channel to 1 just for this retry (don’t persist)
        conf_txt = AP_HOSTAPD_CONF.read_text()
        conf_txt = re.sub(r"^channel=.*$", "channel=1", conf_txt, flags=re.M)
        AP_HOSTAPD_CONF.write_text(conf_txt)
        sh(f"{ip} link set wlan0 down || true", check=False)
        sh(f"{ip} link set wlan0 up", check=False)
        cp_h = sh(f"hostapd -B -f {AP_HOSTAPD_LOG} -P {AP_HOSTAPD_PID} {hostapd_conf}", check=False)
        h_ok = _pid_alive(AP_HOSTAPD_PID)

    vis = "HIDDEN" if AP_HIDDEN else "BROADCAST"
    print(f"AP: hostapd={'active' if h_ok else 'inactive'}, dnsmasq={'active' if d_ok else 'failed'}")
    print(f"SSID: {AP_SSID} ({vis}) / PSK: {AP_PSK} / CIDR: {AP_CIDR}")

    if not h_ok:
        print("---- hostapd log (last 40 lines) ----")
        try: print("\n".join(Path(AP_HOSTAPD_LOG).read_text().splitlines()[-40:]))
        except Exception: print("(no log)")
    if not d_ok:
        print("---- dnsmasq AP log (last 40 lines) ----")
        try: print("\n".join(Path(AP_DNSMASQ_LOG).read_text().splitlines()[-40:]))
        except Exception: print("(no log)")

    return 0 if (h_ok and d_ok) else 1

def wifi_ap_stop() -> int:
    ap_settings_load()
    need_root()
    # dnsmasq (AP instance)
    if _pid_alive(AP_DNSMASQ_PID):
        try:
            pid = int(AP_DNSMASQ_PID.read_text().strip() or "0")
            os.kill(pid, 15); time.sleep(0.2)
        except Exception: pass
    AP_DNSMASQ_PID.unlink(missing_ok=True)
    sh("pkill -f dnsmasq.*dnsmasq.ap.conf 2>/dev/null || true", check=False)

    # hostapd (AP instance)
    if _pid_alive(AP_HOSTAPD_PID):
        try:
            pid = int(AP_HOSTAPD_PID.read_text().strip() or "0")
            os.kill(pid, 15); time.sleep(0.2)
        except Exception: pass
    AP_HOSTAPD_PID.unlink(missing_ok=True)
    sh("pkill -f 'hostapd.*hostapd-p4wnp1.conf' 2>/dev/null || true", check=False)

    print("AP: stopped")
    return 0

def wifi_ap_status():
    # hostapd status
    hs = sh("pgrep -af '^hostapd(\\s|$)'", check=False)
    ds = sh("pgrep -af 'dnsmasq.*p4wnp1-ap.conf'", check=False)

    ap = "active" if _pid_alive(AP_HOSTAPD_PID) else "inactive"
    dh = "active" if _pid_alive(AP_DNSMASQ_PID) else "inactive"

    ip = sh("ip -br addr show wlan0 | awk '{print $3}'", check=False).stdout.strip()
    print(f"AP: hostapd={ap}, dnsmasq={dh}")
    print(f"wlan0: {ip or 'down'}")

def wifi_portal_start():
    # assumes AP already up on wlan0
    if not PORTAL_BIN.exists():
        print("[!] Portal launcher not found:", PORTAL_BIN); return 1
    return sh(f"/usr/bin/env python3 {PORTAL_BIN} start", check=False).returncode

def wifi_portal_stop():
    if not PORTAL_BIN.exists():
        print("[!] Portal launcher not found:", PORTAL_BIN); return 1
    return sh(f"/usr/bin/env python3 {PORTAL_BIN} stop", check=False).returncode

def wifi_portal_status():
    if not PORTAL_BIN.exists():
        print("[!] Portal launcher not found:", PORTAL_BIN); return 3
    return sh(f"/usr/bin/env python3 {PORTAL_BIN} status", check=False).returncode

def _dhcp_acquire(iface="wlan0") -> int:
    # Try dhclient first, then dhcpcd
    if which("dhclient"):
        return sh(f"dhclient -4 -pf {DHCLIENT_PID} {iface}", check=False).returncode
    if which("dhcpcd"):
        return sh(f"dhcpcd -4 -q {iface}", check=False).returncode
    print("[!] No DHCP client (dhclient/dhcpcd) installed.", file=sys.stderr)
    return 2

def _dhcp_release(iface="wlan0"):
    if which("dhclient"):
        sh(f"dhclient -4 -r {iface}", check=False)
    if which("dhcpcd"):
        sh(f"dhcpcd -k {iface}", check=False)

def wifi_client_join(ssid: str, psk: str, hidden: bool=False) -> int:
    need_root()
    # Ensure AP services are down (free wlan0)
    sh("systemctl stop hostapd 2>/dev/null || true", check=False)
    sh("systemctl stop dnsmasq 2>/dev/null || true", check=False)

    ip = which("ip") or "/sbin/ip"
    sh(f"{ip} link set wlan0 down || true", check=False)
    sh(f"{ip} addr flush dev wlan0 || true", check=False)

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    WPA_CONF.write_text(_wpa_conf_text(ssid, psk, hidden))

    # Start wpa_supplicant in the background (no systemd dependency)
    sh("pkill -f 'wpa_supplicant.*wlan0' 2>/dev/null || true", check=False)
    cmd = f"wpa_supplicant -B -i wlan0 -c {WPA_CONF} -P {WPA_PID}"
    cp = sh(cmd, check=False)
    if cp.returncode != 0:
        sys.stderr.write(cp.stderr or "")
        print("[!] wpa_supplicant failed", file=sys.stderr); return 1

    # Bring iface up and get a lease
    sh(f"{ip} link set wlan0 up", check=False)
    if _dhcp_acquire("wlan0") != 0:
        print("[!] DHCP failed on wlan0", file=sys.stderr); return 2

    print(f"Client: joined SSID '{ssid}'" + (" (hidden)" if hidden else ""))
    return 0

def wifi_client_disconnect() -> int:
    need_root()
    _dhcp_release("wlan0")
    # stop wpa_supplicant (PID if present, else pkill)
    if WPA_PID.exists():
        try:
            pid = int(WPA_PID.read_text().strip() or "0")
            if pid > 0:
                os.kill(pid, 15); time.sleep(0.2)
        except Exception:
            pass
        WPA_PID.unlink(missing_ok=True)
    sh("pkill -f 'wpa_supplicant.*wlan0' 2>/dev/null || true", check=False)
    print("Client: disconnected")
    return 0

def wifi_client_status() -> int:
    ip = which("ip") or "/sbin/ip"
    ss = sh(f"{ip} -4 addr show wlan0", check=False).stdout or ""
    wl = sh("iw dev wlan0 link", check=False).stdout or ""
    print("Wi-Fi client status:")
    print(wl.strip() or "(not associated)")
    print(ss.strip())
    return 0

def wifi_status() -> int:
    ip = which("ip") or "/sbin/ip"
    ss = sh(f"{ip} -4 addr show wlan0", check=False).stdout or ""
    h = "active" if _pid_alive(AP_HOSTAPD_PID) else "inactive"
    d = "active" if _pid_alive(AP_DNSMASQ_PID) else "inactive"
    print(f"Wi-Fi: wlan0\n{ss.strip()}\nServices: hostapd={h}, dnsmasq={d}")
    return 0

def wifi_ap_diag() -> int:
    print("---- iw reg get ----")
    print(sh("iw reg get", check=False).stdout or "")
    print("---- iw dev ----")
    print(sh("iw dev", check=False).stdout or "")
    print("---- iw list (phy capabilities) ----")
    print(sh("iw list | sed -n '1,120p'", check=False).stdout or "")
    print("---- hostapd last 60 lines ----")
    try:
        print("\n".join(Path(AP_HOSTAPD_LOG).read_text().splitlines()[-60:]))
    except Exception:
        print("(no log)")
    return 0

def wifi_driver_reset() -> int:
    # Reload Broadcom FullMAC driver (fixes "Could not connect to kernel driver")
    sh("modprobe -r brcmfmac 2>/dev/null || true", check=False)
    time.sleep(1)
    sh("modprobe brcmfmac 2>/dev/null || true", check=False)
    print("Wi-Fi driver reloaded (brcmfmac).")
    return 0

def wifi_config_show() -> int:
    s = ap_settings_load()
    vis = "HIDDEN" if s["hidden"] else "BROADCAST"
    print("Wi-Fi AP config:")
    print(f'  ssid:    {s["ssid"]}')
    print(f'  password:{s["psk"]}')
    print(f'  cidr:    {s["cidr"]}')
    print(f'  channel: {s["chan"]}')
    print(f'  country: {s["country"]}')
    print(f'  hidden:  {vis}')
    return 0

def wifi_set_ssid(val: str) -> int:
    val = val.strip()
    if not (1 <= len(val) <= 32):
        print("[!] SSID must be 1..32 characters.", file=sys.stderr); return 1
    ap_settings_save(ssid=val)
    print(f"AP SSID set to: {val}")
    return 0

def wifi_set_password(val: str) -> int:
    if not (8 <= len(val) <= 63):
        print("[!] WPA2-PSK length must be 8..63 characters.", file=sys.stderr); return 1
    ap_settings_save(psk=val)
    print("AP password updated.")
    return 0

def wifi_set_cidr(val: str) -> int:
    try:
        iface = ip_interface(val)
        if not isinstance(iface, IPv4Interface):
            raise ValueError("IPv4 only")
    except Exception:
        print("[!] CIDR must be IPv4 like 172.24.0.1/24", file=sys.stderr); return 1
    ap_settings_save(cidr=str(iface))
    print(f"AP CIDR set to: {iface}")
    return 0

def wifi_set_hidden(val: str) -> int:
    ap_settings_save(hidden=_parse_bool_word(val))
    print(f"AP hidden={'yes' if _parse_bool_word(val) else 'no'}")
    return 0

def wifi_set_channel(val: str) -> int:
    try:
        ch = int(val)
    except ValueError:
        print("[!] Channel must be an integer.", file=sys.stderr); return 1
    # conservative: 1..13 (2.4 GHz). You can widen later per country.
    if not (1 <= ch <= 13):
        print("[!] Channel must be between 1 and 13.", file=sys.stderr); return 1
    ap_settings_save(chan=ch)
    print(f"AP channel set to: {ch}")
    return 0

def wifi_set_country(val: str) -> int:
    v = (val or "").strip().upper()
    if len(v) != 2 or not v.isalpha():
        print("[!] Country must be a 2-letter code like US/ES/DE.", file=sys.stderr); return 1
    ap_settings_save(country=v)
    print(f"AP country set to: {v}")
    return 0

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

# ------------------------------- WiFi Lures --------------------------------

def wifi_lure_start():
    if LURE_PID.exists():
        print("[*] Wi-Fi lure already running."); return 0
    env = os.environ.copy()
    cfg = _lure_cfg_read()
    env.setdefault("P4WN_LURE_LIST",  cfg.get("list", str(LURE_LIST)))
    env.setdefault("P4WN_LURE_STATE", str(LURE_STATE))
    env["P4WN_LURE_DWELL"] = str(cfg.get("dwell", 20))

    p = subprocess.Popen(
        [sys.executable, "/opt/p4wnp1/tools/wifi_lure.py"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
    )
    write_pid(LURE_PID, p.pid)
    print(f"Wi-Fi lure started (pid {p.pid}), cycling SSIDs from {LURE_LIST}")
    return 0

def wifi_lure_stop():
    pid = read_pid(LURE_PID)
    if not pid:
        print("[*] Wi-Fi lure not running."); return 0
    try: os.kill(pid, signal.SIGTERM)
    except ProcessLookupError: pass
    LURE_PID.unlink(missing_ok=True)
    print("Wi-Fi lure stopped.")
    return 0

def wifi_lure_status():
    if not LURE_PID.exists():
        print("Wi-Fi lure: stopped"); return 0
    print("Wi-Fi lure: running")
    if LURE_STATE.exists():
        try:
            import json; st = json.loads(LURE_STATE.read_text())
            print(f" Active SSID: {st.get('active_ssid')}")
        except Exception: pass
    return 0

def _lure_cfg_read():
    import json
    if LURE_CFG.exists():
        try: return json.loads(LURE_CFG.read_text())
        except Exception: pass
    return {"dwell": 20, "list": str(LURE_LIST)}

def _lure_cfg_write(cfg):
    import json, os
    os.makedirs(LURE_CFG.parent, exist_ok=True)
    LURE_CFG.write_text(json.dumps(cfg, indent=2))

def wifi_lure_set_dwell(sec):
    cfg = _lure_cfg_read()
    try:
        sec = int(sec)
        if sec < 5 or sec > 600:
            print("[!] Dwell must be between 5 and 600 seconds."); return 2
    except ValueError:
        print("[!] Dwell must be an integer."); return 2
    cfg["dwell"] = sec
    _lure_cfg_write(cfg)
    print(f"Lure dwell set to: {sec}s")
    return 0

def wifi_lure_set_list(path):
    p = Path(path)
    if not p.exists():
        print(f"[!] SSID list not found: {p}"); return 2
    cfg = _lure_cfg_read()
    cfg["list"] = str(p)
    _lure_cfg_write(cfg)
    print(f"Lure SSID list set: {p}")
    return 0

# ------------------------------- WiFi Captive Portal --------------------------------

def portal_start():
    # Ensure AP is up first (but don't bounce it if already running)
    if not _pid_alive(AP_HOSTAPD_PID):
        wifi_ap_start()
    # call the setup payload (idempotent)
    cp = sh("python3 /opt/p4wnp1/services/portal/bin/portal_ctl.py start", check=False)
    if cp.returncode == 0:
        print("Captive portal: started.")
    else:
        print("[!] Captive portal start failed.")
    return cp.returncode

def portal_stop():
    cp = sh("python3 /opt/p4wnp1/services/portal/bin/portal_ctl.py stop", check=False)
    wifi_ap_stop()
    if cp.returncode == 0:
        print("Captive portal: stopped.")
    else:
        print("[!] Captive portal stop failed.")
    return cp.returncode

def portal_status():
    # lightweight status: apache + hostapd + dnsmasq + our capture app
    apache = sh("systemctl is-active apache2", check=False).stdout.strip()
    print(f"Apache: {apache}")
    wifi_status()
    cap = Path("/var/log/p4wnp1/captive.log")
    if cap.exists():
        tail = sh(f"tail -n 10 {cap}", check=False).stdout
        print("---- captive log (last 10) ----")
        print(tail, end="")
    return 0

# ------------------------------- BLE Helpers --------------------------------

def bt_scan_start():
    if BT_SCAN_PID.exists():
        print("[*] BLE scan already running.")
        return 0
    env = os.environ.copy()
    env.setdefault("P4WN_BLE_LOG", str(BT_SCAN_LOG))
    p = subprocess.Popen(
        [sys.executable, "/opt/p4wnp1/tools/ble_scan.py"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
    )
    write_pid(BT_SCAN_PID, p.pid)
    print(f"BLE scan started (pid {p.pid}), logging to {BT_SCAN_LOG}")
    return 0

def bt_scan_stop():
    pid = read_pid(BT_SCAN_PID)
    if not pid:
        print("[*] BLE scan not running.")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    BT_SCAN_PID.unlink(missing_ok=True)
    print("BLE scan stopped.")
    return 0

def bt_scan_status():
    running = BT_SCAN_PID.exists()
    print(f"BLE scan: {'running' if running else 'stopped'}")
    if BT_SCAN_LOG.exists():
        try:
            tail = subprocess.check_output(["tail","-n","10",str(BT_SCAN_LOG)], text=True)
            print("---- last 10 beacons ----")
            print(tail, end="")
        except Exception:
            pass
    return 0
# ------------ Payload discovery / manifests ------------
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

def list_payload_units() -> list[str]:
    out = sh("systemctl list-units --type=service --all --no-legend 'p4w-payload-*.service'", check=False).stdout or ""
    units = []
    for ln in out.splitlines():
        toks = ln.split()
        if toks:
            units.append(toks[0])
    return units

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

def payload_start(name: str, extra_args: list[str] | None = None) -> int:
    unit = transient_unit_name(name)
    _transient_unit_cleanup(unit)
    need_root()
    mans = load_manifests()
    m = mans.get(name, {})

    cmd = m.get("cmd")
    binp = m.get("bin")
    script = m.get("script")
    base_args = (m.get("args", []) or [])
    args = base_args + (extra_args or [])
    env  = _payload_env_for(m)
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

    rc = _run_preflight(env, wdir, pre)
    if rc != 0:
        return rc

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

def payload_stop(name: str | None = None) -> int:
    need_root()
    units = [transient_unit_name(name)] if name else list_payload_units()
    if not units:
        print("(no running payload units)"); return 0
    stopped = []
    for u in units:
        if systemctl("is-active", u).stdout.strip() != "inactive":
            systemctl("stop", u); systemctl("reset-failed", u); stopped.append(u)
    if stopped:
        print("Stopped:", ", ".join(stopped))
    return 0

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

# ------------ Legacy "active payload" helpers (kept) ------------
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

def _manifest_for(name: str) -> dict | None:
    m = load_manifests().get(name)
    if not m:
        # try by filename: wifi_ap_captive_apache.json -> "wifi_ap_captive_apache"
        mm = load_manifests()
        if name in mm:
            return mm[name]
    return m

def usb_current_functions() -> set[str]:
    """Return active gadget functions from c.1 symlinks as: {'hid','rndis','ecm','ncm','msd','acm'}."""
    cfg = USB_GADGET / "configs" / "c.1"
    names = set()
    for n in ("hid","rndis","ecm","ncm","mass_storage","acm"):
        if (cfg / f"{n}.usb0").exists():
            names.add("msd" if n == "mass_storage" else n)
    return names

def iface_has_addr(ifname: str) -> bool:
    """True if interface has any IPv4 address."""
    return bool(ips_by_iface().get(ifname))

def _payload_requirements_ok(m: dict) -> tuple[bool, str]:
    reqs = m.get("requirements", [])
    missing = []
    for r in reqs:
        if r == "hid":
            if "hid" not in usb_current_functions(): missing.append("hid")
        elif r in ("msd", "storage"):
            if "msd" not in usb_current_functions() or not _msd_linked(): missing.append("msd")
        elif r in ("net", "usbnet"):
            if not iface_has_addr("usb0"): missing.append("usb0 up")
        elif r in ("serial", "acm"):
            if "acm" not in usb_current_functions(): missing.append("acm")
        elif r in ("payload_web", "payload-http"):
            if systemctl("is-active", PAYLOADS_WEB_UNIT).stdout.strip() != "active":
                missing.append("payload_web")
        elif r in ("payload_web_https", "payload-https"):
            if systemctl("is-active", PAYLOADS_HTTPS_UNIT).stdout.strip() != "active":
                missing.append("payload_web_https")
    return (len(missing) == 0, ", ".join(missing))

def _payload_env_for(m: dict) -> dict:
    env = os.environ.copy()
    env["P4WN_HOME"] = str(P4WN_HOME)

    # LHOST/IFACE defaults
    lhost = primary_ip()
    if lhost: env.setdefault("P4WN_LHOST", lhost)
    iface = primary_iface()
    if iface: env.setdefault("P4WN_NET_IFACE", iface)

    # HTTP base
    h, p, r = _payloadweb_cfg()
    adv_http = primary_ip() or h
    env.setdefault("P4WN_PAYLOAD_HOST", adv_http)
    env.setdefault("P4WN_PAYLOAD_PORT", str(p))
    env.setdefault("P4WN_PAYLOAD_URL", f"http://{adv_http}:{p}/")
    env.setdefault("P4WN_PAYLOAD_ROOT", r)

    # HTTPS base (if service active)
    tls_active = systemctl("is-active", PAYLOADS_HTTPS_UNIT).stdout.strip() == "active"
    th, tp, *_ = _payloadweb_https_cfg()
    adv_https = primary_ip() or th
    env.setdefault("P4WN_PAYLOAD_URL_TLS", f"https://{adv_https}:{tp}/")
    env.setdefault("P4WN_PAYLOAD_SCHEME", "https" if tls_active else "http")

    env.setdefault("P4WN_MSD_IMAGE", str(MSD_IMAGE))
    env.setdefault("P4WN_MSD_SIZE_MB", str(MSD_SIZE_MB))

    # allow manifest env block to override
    for k, v in (m.get("env") or {}).items():
        env[str(k)] = str(v)
    return env

def payload_run(name: str) -> int:
    need_root()
    m = _manifest_for(name)
    if not m:
        print(f"[!] Payload not found: {name}", file=sys.stderr); return 4
    ok, why = _payload_requirements_ok(m)
    if not ok:
        print(f"[!] Requirements not met: {why}", file=sys.stderr); return 6
    return payload_start(name)


def payload_status(name: str | None = None) -> int:
    units = [transient_unit_name(name)] if name else list_payload_units()
    if not units:
        print("(no running payload units)"); return 0
    for u in units:
        sh(f"systemctl status --no-pager '{u}'", check=False)
    return 0

def get_payload_choices():
    names = list_payload_names()
    return [(n, n) for n in names]

# ------------ "Run Now" (requirements-aware) ------------
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
    """
    Bring up the exact gadget functions (HID/NET/MSD/Serial) and auxiliary services
    required by a manifest or by an inferred payload group.

    Special requirement keys (strings, case-insensitive):
      - "hid", "net"/"usbnet", "msd"/"storage", "serial"/"acm"
      - "payload_web" / "payload-http"  -> start HTTP payload file server (:80)
      - "payload_web_https" / "payload-https" -> start HTTPS payload file server (:443)
      - "tmux" -> warn if tmux missing (no-op otherwise)
    """
    reqs = [str(r).lower() for r in (reqs or [])]

    want_hid = "hid" in reqs
    want_net = ("net" in reqs) or ("usbnet" in reqs)
    want_msd = ("msd" in reqs) or ("storage" in reqs)
    want_acm = ("serial" in reqs) or ("acm" in reqs)

    # Only touch the gadget when any USB capability is requested.
    if want_hid or want_net or want_msd or want_acm:
        rc = usb_compose_apply(want_hid, want_net, want_msd, want_acm)
        if rc != 0:
            return rc

    # Payload web servers
    if ("payload_web" in reqs) or ("payload-http" in reqs):
        payloadweb_start()

    if ("payload_web_https" in reqs) or ("payload-https" in reqs):
        payloadweb_https_start()

    if "tmux" in reqs and not which("tmux"):
        print("[!] tmux not found; install tmux for best results.", file=sys.stderr)

    return 0

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

# ------------ Web UI ------------
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

# ------------ Web Payloads ------------
def _payloadweb_unit_write():
    """
    Install the systemd unit if missing. Uses python http.server for simplicity/reliability.
    Root binds to :80; override host/port/root via Environment in override.conf.
    """
    unit_path = Path("/etc/systemd/system") / PAYLOADS_WEB_UNIT
    if unit_path.exists(): return
    need_root()
    repo = P4WN_HOME / "systemd" / PAYLOADS_WEB_UNIT
    if repo.exists():
        unit_path.write_bytes(repo.read_bytes())
        os.chmod(unit_path, 0o644)
        systemctl("daemon-reload")
        return
    content = dedent(f"""\
        [Unit]
        Description=P4wnP1 Payloads Web Server (static files)
        After=network-online.target
        Wants=network-online.target

        [Service]
        # Defaults (overridable via {PAYLOADS_WEB_OVERRIDE_FILE})
        Environment="PAYLOADS_HOST=0.0.0.0" "PAYLOADS_PORT=80" "PAYLOADS_ROOT={PAYLOADS_ROOT}"
        WorkingDirectory=/opt/p4wnp1
        ExecStart=/usr/bin/python3 -u -m http.server $PAYLOADS_PORT --bind $PAYLOADS_HOST --directory $PAYLOADS_ROOT
        Restart=on-failure
        # We bind privileged port 80; run as root to avoid setcap complexity.
        User=root

        [Install]
        WantedBy=multi-user.target
    """)
    unit_path.write_text(content)
    systemctl("daemon-reload")

def _payloadweb_override_write(host: str, port: int, root: Path):
    need_root()
    PAYLOADS_WEB_OVERRIDE_DIR.mkdir(parents=True, exist_ok=True)
    content = dedent(f"""\
        [Service]
        Environment="PAYLOADS_HOST={host}" "PAYLOADS_PORT={port}" "PAYLOADS_ROOT={root}"
    """)
    PAYLOADS_WEB_OVERRIDE_FILE.write_text(content)
    systemctl("daemon-reload")
    systemctl("restart", PAYLOADS_WEB_UNIT)

def _payloadweb_cfg() -> tuple[str, int, str]:
    host = "0.0.0.0"; port = 80; root = str(PAYLOADS_ROOT)
    if PAYLOADS_WEB_OVERRIDE_FILE.exists():
        text = PAYLOADS_WEB_OVERRIDE_FILE.read_text()
        for line in text.splitlines():
            if "PAYLOADS_HOST=" in line: host = line.split("PAYLOADS_HOST=")[-1].strip().strip('"')
            if "PAYLOADS_PORT=" in line:
                try: port = int(line.split("PAYLOADS_PORT=")[-1].split('"')[0].strip())
                except Exception: pass
            if "PAYLOADS_ROOT=" in line: root = line.split("PAYLOADS_ROOT=")[-1].strip().strip('"')
    return (host, port, root)

def payloadweb_env(_args=None) -> int:
    host, port, root = _payloadweb_cfg()
    adv = primary_ip() or host
    url = f"http://{adv}:{port}/"
    print(f"export P4WN_PAYLOAD_HOST={adv}")
    print(f"export P4WN_PAYLOAD_PORT={port}")
    print(f"export P4WN_PAYLOAD_URL={url}")
    print(f"export P4WN_PAYLOAD_ROOT={root}")
    return 0

def payloadweb_status_text() -> str:
    st = systemctl("is-active", PAYLOADS_WEB_UNIT).stdout.strip()
    en = systemctl("is-enabled", PAYLOADS_WEB_UNIT).stdout.strip()
    host, port, root = _payloadweb_cfg()
    adv = primary_ip() or host
    try:
        nfiles = sum(1 for p in Path(root).rglob("*") if p.is_file())
    except Exception:
        nfiles = 0
    return f"PayloadWeb: {st} ({en})  bind={host}:{port}  url=http://{adv}:{port}/  root={root} files={nfiles}"

def payloadweb_status(_args=None) -> int:
    print(payloadweb_status_text())
    print(payloadweb_https_status_text())
    return 0

def payloadweb_start():   _payloadweb_unit_write(); need_root(); return systemctl("start",   PAYLOADS_WEB_UNIT).returncode
def payloadweb_stop():    need_root();              return systemctl("stop",    PAYLOADS_WEB_UNIT).returncode
def payloadweb_restart(): need_root();              return systemctl("restart", PAYLOADS_WEB_UNIT).returncode
def payloadweb_enable():  _payloadweb_unit_write(); need_root(); return systemctl("enable",  PAYLOADS_WEB_UNIT).returncode
def payloadweb_disable(): need_root();              return systemctl("disable", PAYLOADS_WEB_UNIT).returncode

def payloadweb_config_show(_args=None) -> int:
    if PAYLOADS_WEB_OVERRIDE_FILE.exists():
        print(PAYLOADS_WEB_OVERRIDE_FILE.read_text().rstrip())
    else:
        print("(no override set; service defaults in effect)")
    return 0

def payloadweb_config_set(host: str, port: int, root: str | None) -> int:
    if host == "auto":
        auto = primary_ip()
        if not auto:
            print("Could not determine primary IP for 'auto'", file=sys.stderr); return 1
        host = auto
    if port <= 0 or port > 65535:
        print("invalid --port", file=sys.stderr); return 1
    root_path = Path(root) if root else PAYLOADS_ROOT
    if not root_path.exists():
        print(f"--root does not exist: {root_path}", file=sys.stderr); return 1
    _payloadweb_unit_write()
    _payloadweb_override_write(host, port, root_path)
    return 0

def payloadweb_url() -> int:
    host, port, _ = _payloadweb_cfg()
    adv = primary_ip() or host
    print(f"http://{adv}:{port}/");
    return 0

def payloadweb_https_url() -> int:
    host, port, *_ = _payloadweb_https_cfg()
    adv = primary_ip() or host
    print(f"https://{adv}:{port}/");
    return 0

def _payloadweb_https_script_path() -> Path:
    return P4WN_HOME / "bin" / "payloads_https.py"

def _payloadweb_https_script_write():
    path = _payloadweb_https_script_path()
    if path.exists(): return
    need_root()
    path.parent.mkdir(parents=True, exist_ok=True)
    code = dedent(r"""
    #!/usr/bin/env python3
    import os, ssl, sys
    from pathlib import Path
    from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
    host = os.environ.get("PAYLOADS_HOST", "0.0.0.0")
    port = int(os.environ.get("PAYLOADS_PORT", "443"))
    root = os.environ.get("PAYLOADS_ROOT", "/opt/p4wnp1/payloads/www")
    cert = os.environ.get("PAYLOADS_CERT")
    key  = os.environ.get("PAYLOADS_KEY")
    if not (cert and key and Path(cert).exists() and Path(key).exists()):
        print("[!] TLS cert/key missing", file=sys.stderr); sys.exit(2)
    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root, **kw)
    httpd = ThreadingHTTPServer((host, port), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=cert, keyfile=key)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print(f"Serving HTTPS payloads on https://{host}:{port}/ -> {root}", flush=True)
    httpd.serve_forever()
    """).lstrip()
    path.write_text(code)
    os.chmod(path, 0o755)

def _payloadweb_tls_ensure(cn="p4wnp1", days=3650):
    need_root()
    PAYLOADS_TLS_DIR.mkdir(parents=True, exist_ok=True)
    if not (PAYLOADS_CERT.exists() and PAYLOADS_KEY.exists()):
        sh(f'openssl req -x509 -nodes -newkey rsa:2048 -keyout "{PAYLOADS_KEY}" -out "{PAYLOADS_CERT}" -subj "/CN={cn}" -days {days}', check=False)

def _payloadweb_https_unit_write():
    unit_path = Path("/etc/systemd/system") / PAYLOADS_HTTPS_UNIT
    if unit_path.exists():
        return
    need_root()
    _payloadweb_https_script_write()
    _payloadweb_tls_ensure()
    content = dedent(f"""\
        [Unit]
        Description=P4wnP1 Payloads Web Server (HTTPS)
        After=network-online.target
        Wants=network-online.target

        [Service]
        # Defaults (overridable via {PAYLOADS_HTTPS_OVERRIDE_FILE})
        Environment="PAYLOADS_HOST=0.0.0.0" "PAYLOADS_PORT=443" "PAYLOADS_ROOT={PAYLOADS_ROOT}" "PAYLOADS_CERT={PAYLOADS_CERT}" "PAYLOADS_KEY={PAYLOADS_KEY}"
        WorkingDirectory=/opt/p4wnp1
        ExecStart=/usr/bin/python3 -u { _payloadweb_https_script_path() }
        Restart=on-failure
        User=root

        [Install]
        WantedBy=multi-user.target
    """)
    unit_path.write_text(content)
    systemctl("daemon-reload")

def _payloadweb_https_override_write(host: str, port: int, root: Path, cert: Path, key: Path):
    need_root()
    PAYLOADS_HTTPS_OVERRIDE_DIR.mkdir(parents=True, exist_ok=True)
    content = dedent(f"""\
        [Service]
        Environment="PAYLOADS_HOST={host}" "PAYLOADS_PORT={port}" "PAYLOADS_ROOT={root}" "PAYLOADS_CERT={cert}" "PAYLOADS_KEY={key}"
    """)
    PAYLOADS_HTTPS_OVERRIDE_FILE.write_text(content)
    systemctl("daemon-reload")
    systemctl("restart", PAYLOADS_HTTPS_UNIT)

def _payloadweb_https_cfg() -> tuple[str, int, str, str, str]:
    host = "0.0.0.0"; port = 443; root = str(PAYLOADS_ROOT)
    cert = str(PAYLOADS_CERT); key = str(PAYLOADS_KEY)
    if PAYLOADS_HTTPS_OVERRIDE_FILE.exists():
        text = PAYLOADS_HTTPS_OVERRIDE_FILE.read_text()
        for line in text.splitlines():
            if "PAYLOADS_HOST=" in line: host = line.split("PAYLOADS_HOST=")[-1].strip().strip('"')
            if "PAYLOADS_PORT=" in line:
                try: port = int(line.split("PAYLOADS_PORT=")[-1].split('"')[0].strip())
                except Exception: pass
            if "PAYLOADS_ROOT=" in line: root = line.split("PAYLOADS_ROOT=")[-1].strip().strip('"')
            if "PAYLOADS_CERT=" in line: cert = line.split("PAYLOADS_CERT=")[-1].strip().strip('"')
            if "PAYLOADS_KEY="  in line: key  = line.split("PAYLOADS_KEY=")[-1].strip().strip('"')
    return (host, port, root, cert, key)

def payloadweb_https_status_text() -> str:
    st = systemctl("is-active", PAYLOADS_HTTPS_UNIT).stdout.strip()
    en = systemctl("is-enabled", PAYLOADS_HTTPS_UNIT).stdout.strip()
    host, port, root, cert, key = _payloadweb_https_cfg()
    adv = primary_ip() or host
    return f"PayloadWebTLS: {st} ({en})  bind={host}:{port}  url=https://{adv}:{port}/  root={root}"

def payloadweb_https_status(_args=None) -> int: print(payloadweb_https_status_text()); return 0

def payloadweb_https_start():   _payloadweb_https_unit_write(); need_root(); return systemctl("start",   PAYLOADS_HTTPS_UNIT).returncode
def payloadweb_https_stop():    need_root();                    return systemctl("stop",    PAYLOADS_HTTPS_UNIT).returncode
def payloadweb_https_restart(): need_root();                    return systemctl("restart", PAYLOADS_HTTPS_UNIT).returncode
def payloadweb_https_enable():  _payloadweb_https_unit_write(); need_root(); return systemctl("enable",  PAYLOADS_HTTPS_UNIT).returncode
def payloadweb_https_disable(): need_root();                    return systemctl("disable", PAYLOADS_HTTPS_UNIT).returncode

def payloadweb_https_config_show(_args=None) -> int:
    if PAYLOADS_HTTPS_OVERRIDE_FILE.exists():
        print(PAYLOADS_HTTPS_OVERRIDE_FILE.read_text().rstrip())
    else:
        print("(no override set; service defaults in effect)")
    return 0

def payloadweb_https_config_set(host: str, port: int, root: str | None, cert: str | None, key: str | None) -> int:
    if host == "auto":
        auto = primary_ip()
        if not auto:
            print("Could not determine primary IP for 'auto'", file=sys.stderr); return 1
        host = auto
    if port <= 0 or port > 65535:
        print("invalid --port", file=sys.stderr); return 1
    root_path = Path(root) if root else PAYLOADS_ROOT
    if not root_path.exists():
        print(f"--root does not exist: {root_path}", file=sys.stderr); return 1
    cert_path = Path(cert) if cert else PAYLOADS_CERT
    key_path  = Path(key)  if key  else PAYLOADS_KEY
    if not (cert_path.exists() and key_path.exists()):
        print("[!] TLS cert/key not found; run: p4wnctl payload web cert gen", file=sys.stderr); return 1
    _payloadweb_https_unit_write()
    _payloadweb_https_override_write(host, port, root_path, cert_path, key_path)
    return 0

def payloadweb_cert_gen(cn="p4wnp1", days=3650) -> int:
    _payloadweb_tls_ensure(cn=cn, days=days)
    print(f"Generated (or exists):\n  cert: {PAYLOADS_CERT}\n  key:  {PAYLOADS_KEY}")
    return 0

# ------------ IP ------------
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

# ------------ Template render (for __HOST__) ------------
def template_render(path: str) -> int:
    p = Path(path)
    if not p.is_file():
        print(f"File not found: {p}", file=sys.stderr); return 1
    host = primary_ip()
    if not host:
        print("Could not resolve primary IP", file=sys.stderr); return 1
    text = p.read_text(encoding="utf-8", errors="ignore")
    # also inject the payload URL
    ph, pp, _ = _payloadweb_cfg()
    adv = host or ph
    text = text.replace("__HOST__", adv).replace("__PAYLOAD_URL__", f"http://{adv}:{pp}/")
    print(text, end="")
    return 0

# ------------ Help screens ----------
MAIN_HELP = dedent("""\
P4wnP1-O2 control CLI

Subcommands:
  usb         USB gadget controls
  wifi        Wi-Fi controls (AP / portal / client / relay)
  payload     Payload controls (list/set + start/stop/status/logs/describe/run)
  web         Web UI controls (port/host, start/stop, enable/disable, url)
  service     Manage systemd units (install/uninstall/start/stop/...)
  ip          Show IPs (also: ip primary | ip env | ip json)
  template    Render a text file replacing __HOST__ with device IP
""")


USB_HELP = dedent("""\
USB gadget controls
-------------------
Commands:
  usb status
  usb auto                        # tries RNDIS → NCM → ECM
  usb prep                        # add dwc2 overlay + modules-load; reboot afterwards
  usb replug                      # unbind/rebind UDC (or rebuild if busy)
  usb fixperms                    # chmod 0666 /dev/hidg* (quick test)
  usb inf write                   # drop an INF onto the MSD for Windows
  usb id show|set|strings|reset   # manage VID/PID and USB strings (persisted)
  usb dhcp {start|stop|status}
  usb serial {enable|disable|status}
  usb set {hid_net|hid_rndis|hid_ecm|hid_ncm|hid_net_acm|hid_rndis_acm|hid_storage_net|hid_storage_rndis|hid_storage_ncm|hid_storage_net_acm|storage}
  usb compose --hid=0|1 --net=0|1 --msd=0|1 [--acm=0|1] [--nettype=rndis|ncm|ecm|all]
""")

WIFI_HELP = dedent("""\
Wi-Fi controls
--------------
Commands:
  wifi status
  wifi ap start | stop | status
  wifi portal start | stop | status                         # Wi-Fi Captive portal
  wifi client join "<ssid>" "<psk>" [--hidden]
  wifi client disconnect | status
  wifi relay start | stop | status
  wifi lure start | stop | status                           # SSID cycling lure
  wifi lure set dwell <sec>                                 # dwell per SSID (default 20s)
  wifi lure set list <path>                                 # path to SSID list (one SSID per line)
  wifi set ssid "<str>" | password "<str>" | cidr "<ip/xx>" | hidden <yes|no> | channel <n> | country <CC>
  wifi config show
  wifi diag
  wifi driver-reset
""")

PAYLOAD_HELP = dedent("""\
Payload controls
----------------
Commands:
  payload web                # payload webserver submenu
  payload list
  payload set <name>         # legacy active payload pointer (sh/py)
  payload status             # shows active payload pointer
  payload status all         # transient runner states for all discovered payloads
  payload status <name>
  payload start <name>       # runs using manifest (cmd|bin|script)
  payload run <name|active>   # ensure USB/WiFi prereqs, then start (alias: run-now)
  payload stop <name>
  payload logs <name>
  payload describe <name>
""")

PAYLOADWEB_HELP = dedent(f"""\
usage: 

  p4wnctl payload web [status|start|stop|restart|enable|disable|url|env|config show|config set --host <ip|auto> --port <int> --root <path>]

  p4wnctl payload web https [status|start|stop|restart|enable|disable|url|config show|config set --host <ip|auto> --port <int> [--root <path>] [--cert <pem>] 
                                                                                                                                               [--key <pem>]]
  p4wnctl payload web cert gen [--cn <name>] [--days <n>]

Serves static payload files (HTTP on :80, optional HTTPS on :443) from: {PAYLOADS_ROOT}

First run (HTTPS):

  p4wnctl payload web cert gen              # create TLS cert/key
  p4wnctl payload web https enable          # install + enable the TLS unit
  p4wnctl payload web https status          # expect: active (enabled)
  p4wnctl payload web https url             # shows advertised URL (primary IP or override)

Notes:
  - 'inactive (not-found)' on status means the unit isn’t installed yet (run 'https enable').
  - 'url' commands show the advertised IP (not just the bind address).
  - Use 'env' to export P4WN_PAYLOAD_URL, P4WN_PAYLOAD_URL_TLS, and P4WN_PAYLOAD_SCHEME.

Examples:
  p4wnctl payload web start
  p4wnctl payload web env
  p4wnctl payload web https enable
  p4wnctl payload web cert gen --cn p4wnp1 --days 3650
  p4wnctl payload web https config set --host auto --port 443
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

NET_HELP = dedent("""\
Network share
-------------
Commands:
  net share <uplink>     # enable DHCP on usb0 + NAT out via <uplink> (e.g. wlan0)
  net unshare            # stop NAT/DHCP
  net status             # show NAT/DHCP status
""")

# ------------ CLI parsing --------------
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
        if sub == "prep":     return usb_prep()
        if sub == "replug":   return usb_replug()
        if sub == "fixperms":  return usb_fixperms()
        if sub == "auto":     return usb_auto()
        if sub == "set":
            if len(sys.argv) < 4:
                print(USB_HELP.rstrip()); return 1
            return usb_set(sys.argv[3])
        if sub == "inf":
            if len(sys.argv) == 4 and sys.argv[3] == "write":
                return usb_inf_write()
        if sub == "id":
            if len(sys.argv) >= 4 and sys.argv[3] == "show":
                return usb_id_show()
            if len(sys.argv) >= 6 and sys.argv[3] == "set":
                return usb_id_set(sys.argv[4], sys.argv[5])
            if len(sys.argv) >= 4 and sys.argv[3] == "strings":
                # parse --serial/--manufacturer/--product
                args = sys.argv[4:]
                def grab(flag):
                    for i,a in enumerate(args):
                        if a == flag and i+1 < len(args):
                            return args[i+1]
                    return None
                return usb_id_strings(
                    serial=grab("--serial"),
                    manufacturer=grab("--manufacturer"),
                    product=grab("--product"),
                )
            if len(sys.argv) >= 4 and sys.argv[3] == "reset":
                return usb_id_reset()
            print("usage:\n  usb id show\n  usb id set <0xVID> <0xPID>\n  usb id strings [--serial s] [--manufacturer m] [--product p]\n  usb id reset")
            return 1

        if sub == "dhcp":
            if len(sys.argv) == 4 and sys.argv[3] in ("start","stop","status"):
                return {"start": usb_dhcp_start, "stop": usb_dhcp_stop, "status": usb_dhcp_status}[sys.argv[3]]()
            print("usage: p4wnctl usb dhcp {start|stop|status}"); return 1

        if sub == "serial":
            if len(sys.argv) == 4 and sys.argv[3] in ("enable","disable","status"):
                return {"enable": usb_serial_enable, "disable": usb_serial_disable, "status": usb_serial_status}[sys.argv[3]]()
            print("usage: p4wnctl usb serial {enable|disable|status}"); return 1

        if sub == "compose":
        # Usage: p4wnctl usb compose --hid=0|1 --net=0|1 --msd=0|1 [--acm=0|1] [--nettype=rndis|ncm|ecm|all]
            def pstr(name, default=None):
                for a in sys.argv[3:]:
                    if a.startswith(f"--{name}="):
                        return a.split("=", 1)[1].strip()
                return default

            def pbool(name):
                v = pstr(name, None)
                if v is None:
                    return None
                v = v.lower()
                return v in ("1", "true", "yes", "on", "y")

            caps = usb_caps_now()  # current active links (hid/net/msd/acm) 

            hid = pbool("hid")
            net = pbool("net")
            msd = pbool("msd")
            acm = pbool("acm")
            nettype = (pstr("nettype", "all") or "all").lower()
            if nettype not in ("all", "rndis", "ncm", "ecm"):
                print("nettype must be one of: rndis|ncm|ecm|all", file=sys.stderr)
                return 1

            return usb_compose_apply(
                caps["hid"] if hid is None else hid,
                caps["net"] if net is None else net,
                caps["msd"] if msd is None else msd,
                caps["acm"] if acm is None else acm,
                nettype=nettype
            )
        
        print(USB_HELP.rstrip()); return 1

    if cmd == "wifi":
        if len(sys.argv) == 2:
            print(WIFI_HELP.rstrip()); return 0
        sub = sys.argv[2].lower()
        if sub == "status":   return wifi_status()
        if sub == "diag":
            return wifi_ap_diag()
        if sub == "driver-reset":
            return wifi_driver_reset()
        if sub == "ap":
            if len(sys.argv) == 4:
                act = sys.argv[3].lower()
                if act == "start":
                    # Safety: refuse if current SSH session is on wlan0 (to avoid cutting ourselves off)
                    ssh_if = current_ssh_iface()
                    if ssh_if == "wlan0" and os.environ.get("P4WN_FORCE_WIFI","0").lower() not in ("1","true","yes","on"):
                        print("[!] Refusing to start Wi-Fi AP while current SSH session is on wlan0.", file=sys.stderr)
                        print("    Reconnect over Ethernet/USB gadget or set P4WN_FORCE_WIFI=1 to override.", file=sys.stderr)
                        return 2
                    return wifi_ap_start()
                if act == "stop":
                    return wifi_ap_stop()
                if act == "status":
                    return wifi_ap_status()
            print("usage: wifi ap start | stop | status"); return 1
        if sub == "set":
            if len(sys.argv) < 5:
                print('usage:\n  wifi set ssid "<str>"\n  wifi set password "<str>"\n  wifi set cidr "<ip/mask>"\n  wifi set hidden <yes|no>\n  wifi set channel <n>')
                return 1
            field = sys.argv[3].lower()
            value = sys.argv[4]
            if   field == "ssid":     return wifi_set_ssid(value)
            elif field == "password": return wifi_set_password(value)
            elif field == "cidr":     return wifi_set_cidr(value)
            elif field == "hidden":   return wifi_set_hidden(value)
            elif field == "channel":  return wifi_set_channel(value)
            elif field == "country":  return wifi_set_country(value)
            else:
                print("[!] Unknown wifi setting. Use: ssid|password|cidr|hidden|channel", file=sys.stderr)
                return 1

        if sub == "config":
            if len(sys.argv) == 4 and sys.argv[3].lower() == "show":
                return wifi_config_show()
            print("usage: wifi config show"); return 1

        if sub == "client":
            if len(sys.argv) >= 4 and sys.argv[3].lower() == "join":
                if len(sys.argv) < 6:
                    print('usage: wifi client join "<ssid>" "<psk>" [--hidden]'); return 1
                ssid = sys.argv[4]; psk = sys.argv[5]
                hidden = any(a.lower() == "--hidden" for a in sys.argv[6:])
                return wifi_client_join(ssid, psk, hidden)
            if len(sys.argv) == 4 and sys.argv[3].lower() == "disconnect":
                return wifi_client_disconnect()
            if len(sys.argv) == 4 and sys.argv[3].lower() == "status":
                return wifi_client_status()
            print(WIFI_HELP.rstrip()); return 1

        if sub == "relay":
            if len(sys.argv) == 4 and sys.argv[3].lower() == "start":
                return wifi_relay_start()
            if len(sys.argv) == 4 and sys.argv[3].lower() == "stop":
                return wifi_relay_stop()
            if len(sys.argv) == 4 and sys.argv[3].lower() == "status":
                return wifi_relay_status()

        if sub == "lure":
            act = sys.argv[3] if len(sys.argv)>3 else ""
            if act == "start": return wifi_lure_start()
            if act == "stop":  return wifi_lure_stop()
            if act == "status":return wifi_lure_status()
            if act == "set":
                what = sys.argv[4] if len(sys.argv)>4 else ""
                if what == "dwell" and len(sys.argv)>5:
                    return wifi_lure_set_dwell(sys.argv[5])
                if what == "list" and len(sys.argv)>5:
                    return wifi_lure_set_list(sys.argv[5])
                print("Usage: wifi lure set dwell <sec> | list <path>"); return 2
            print("Usage: wifi lure start|stop|status|set ..."); return 2

        if sub == "portal":
            act = sys.argv[3] if len(sys.argv) > 3 else ""
            if act == "start":  return portal_start()
            if act == "stop":   return portal_stop()
            if act == "status": return portal_status()
            print("usage: wifi portal start|stop|status"); return 1

        print(WIFI_HELP.rstrip()); return 1

    # payload
    if cmd == "payload":
        if len(sys.argv) == 2:
            print(PAYLOAD_HELP.rstrip()); return 0
        sub = sys.argv[2].lower()

        # payload web (nested submenu)
        if sub == "web":
            # no extra args → help
            if len(sys.argv) == 3:
                print(PAYLOADWEB_HELP.rstrip()); return 0
            action = sys.argv[3].lower()
            if action == "status":  return payloadweb_status()
            if action == "start":   return payloadweb_start()
            if action == "stop":    return payloadweb_stop()
            if action == "restart": return payloadweb_restart()
            if action == "enable":  return payloadweb_enable()
            if action == "disable": return payloadweb_disable()
            if action == "url":     return payloadweb_url()
            if action == "env":     return payloadweb_env()
            if action == "https":
                if len(sys.argv) == 4:
                    print("usage: p4wnctl payload web https {status|start|stop|restart|enable|disable|url|config show|config set --host <ip|auto> --port <int> [--root <path>] [--cert <pem>] [--key <pem>]}"); return 0
                a2 = sys.argv[4].lower()
                if a2 == "status":  return payloadweb_https_status()
                if a2 == "start":   return payloadweb_https_start()
                if a2 == "stop":    return payloadweb_https_stop()
                if a2 == "restart": return payloadweb_https_restart()
                if a2 == "enable":  return payloadweb_https_enable()
                if a2 == "disable": return payloadweb_https_disable()
                if a2 == "url":     return payloadweb_https_url()
                if a2 == "config":
                    if len(sys.argv) == 5 or sys.argv[5].lower() == "show":
                        return payloadweb_https_config_show()
                    if sys.argv[5].lower() == "set":
                        host = None; port = None; root = None; cert = None; key = None
                        args = sys.argv[6:]; i = 0
                        while i < len(args):
                            if args[i] == "--host" and i+1 < len(args): host = args[i+1]; i += 2; continue
                            if args[i] == "--port" and i+1 < len(args):
                                try: port = int(args[i+1]);
                                except ValueError: print("port must be an integer"); return 1
                                i += 2; continue
                            if args[i] == "--root" and i+1 < len(args): root = args[i+1]; i += 2; continue
                            if args[i] == "--cert" and i+1 < len(args): cert = args[i+1]; i += 2; continue
                            if args[i] == "--key"  and i+1 < len(args): key  = args[i+1]; i += 2; continue
                            i += 1
                        if not host or port is None:
                            print("usage: p4wnctl payload web https config set --host <ip|auto> --port <int> [--root <path>] [--cert <pem>] [--key <pem>]"); return 1
                        return payloadweb_https_config_set(host, port, root, cert, key)
                print("usage: p4wnctl payload web https {status|start|stop|restart|enable|disable|url|config ...}"); return 1

            if action == "config":
                if len(sys.argv) == 4:
                    print(PAYLOADWEB_HELP.rstrip()); return 0
                cfg_action = sys.argv[4].lower()
                if cfg_action == "show": return payloadweb_config_show()
                if cfg_action == "set":
                    host = None; port = None; root = None
                    args = sys.argv[5:]; i = 0
                    while i < len(args):
                        if args[i] == "--host" and i+1 < len(args):
                            host = args[i+1]; i += 2; continue
                        if args[i] == "--port" and i+1 < len(args):
                            try: port = int(args[i+1])
                            except ValueError: print("port must be an integer"); return 1
                            i += 2; continue
                        if args[i] == "--root" and i+1 < len(args):
                            root = args[i+1]; i += 2; continue
                        i += 1
                    if not host or port is None:
                        print(PAYLOADWEB_HELP.rstrip()); return 1
                    return payloadweb_config_set(host, port, root)

            if action == "cert":
                # self-signed certificate helper
                cn = "p4wnp1"; days = 3650
                args = sys.argv[4:]
                for i,a in enumerate(args):
                    if a == "--cn"   and i+1 < len(args): cn   = args[i+1]
                    if a == "--days" and i+1 < len(args):
                        try: days = int(args[i+1])
                        except: pass
                return payloadweb_cert_gen(cn=cn, days=days)
            # unknown action
            print(PAYLOADWEB_HELP.rstrip()); return 1

        if sub == "list":   return payload_list()
        if sub == "set":
            if len(sys.argv) < 4: print(PAYLOAD_HELP.rstrip()); return 1
            return payload_set(sys.argv[3])
        if sub == "status":
            if len(sys.argv) == 3:
                print(payload_status_text()); return 0
            if len(sys.argv) == 4 and sys.argv[3] == "all":
                return payload_status_all()
            if len(sys.argv) == 4:
                return payload_status_named(sys.argv[3])
            print(PAYLOAD_HELP.rstrip()); return 1
        if sub == "start":
            if len(sys.argv) < 4:
                print("usage: p4wnctl payload start <name> [-- <args...>]"); return 1
            extra = sys.argv[4:]
            if extra and extra[0] == "--":
                extra = extra[1:]
            return payload_start(sys.argv[3], extra)
        if sub in ("run", "run-now"):
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

    # ble
    if cmd == "bt":
        if len(sys.argv) < 3:
            print("Bluetooth controls\n-------------------\nCommands:\n  bt scan start|stop|status")
            return 0
        sub = sys.argv[2]
        if sub == "scan":
            act = sys.argv[3] if len(sys.argv)>3 else ""
            if act == "start": return bt_scan_start()
            if act == "stop":  return bt_scan_stop()
            if act == "status":return bt_scan_status()
            print("Usage: bt scan start|stop|status"); return 2
        print("Unknown bt command"); return 2

    # net
    if cmd == "net":
        if len(sys.argv) == 2:
            print(NET_HELP); return 0
        sub = sys.argv[2]
        if sub == "share" and len(sys.argv) >= 4:
            rc = usb_dhcp_start()
            if rc != 0: return rc
            return net_share_start(sys.argv[3])
        if sub == "unshare":
            usb_dhcp_stop()
            return net_share_stop()
        if sub == "status":
            usb_dhcp_status()
            # show nft presence
            rc = sh("nft list table inet p4wnp1", check=False)
            print("NAT:", "enabled" if rc.returncode == 0 else "disabled")
            return 0
        print(NET_HELP); return 1

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

    print(MAIN_HELP.rstrip())
    return 1

if __name__ == "__main__":
    sys.exit(main())
