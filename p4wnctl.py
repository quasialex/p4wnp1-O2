#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import curses
import socket
import subprocess
from pathlib import Path
from textwrap import dedent
from string import Template

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

LAST_MODE_FILE = CONFIG / "usb.last_mode"

# Known units for Services submenu (optional convenience)
SERVICE_UNITS = [
    ("Core", "p4wnp1.service"),
    ("OLED Menu", "oledmenu.service"),
]

USB_CHOICES = [
    ("HID only", "hid"),
    ("Storage only", "storage"),
    ("Serial only", "serial"),
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

# Defaults for gadget network and MSg
AP_SSID   = os.environ.get("P4WN_AP_SSID", "P4WNP1")
AP_PSK    = os.environ.get("P4WN_AP_PSK", "p4wnp1o2")  # 8+ chars
AP_CIDR   = os.environ.get("P4WN_AP_CIDR", "172.24.0.1/24")
AP_NET    = "172.24.0.0/24"
AP_CHAN   = int(os.environ.get("P4WN_AP_CHAN", "6"))
AP_COUNTRY= os.environ.get("P4WN_AP_COUNTRY", "US")    # set to your locale if needed
USB_NET_DEVADDR = os.environ.get("P4WN_USB_DEVADDR", "02:1A:11:00:00:01")
USB_NET_HOSTADDR = os.environ.get("P4WN_USB_HOSTADDR", "02:1A:11:00:00:02")
USB0_CIDR = os.environ.get("P4WN_USB0_CIDR", "10.13.37.1/24")
MSD_IMAGE = Path(os.environ.get("P4WN_MSD_IMAGE", str(CONFIG / "mass_storage.img")))
MSD_SIZE_MB = int(os.environ.get("P4WN_MSD_SIZE_MB", "128"))

# ======= Small helpers =======
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
    _write(USB_GADGET / "idVendor", "0x1d6b")
    _write(USB_GADGET / "idProduct", "0x0104")
    _write(USB_GADGET / "bcdDevice", "0x0100")
    _write(USB_GADGET / "bcdUSB", "0x0200")
    _write(USB_GADGET / "bDeviceClass",    "0xEF") 
    _write(USB_GADGET / "bDeviceSubClass", "0x02")
    _write(USB_GADGET / "bDeviceProtocol", "0x01")
    s = USB_GADGET / "strings/0x409"
    _write(s / "serialnumber", "P4wnP1-O2")
    _write(s / "manufacturer", "quasialex")
    _write(s / "product", "P4wnP1-O2 Gadget")
    cfg = USB_GADGET / "configs/c.1"
    _write(cfg / "MaxPower", "250")
    _write(USB_GADGET / "configs/c.1/strings/0x409/configuration", "Config 1")
    # MS OS descriptors (global)
    osd = USB_GADGET / "os_desc"
    try:
        _write(osd / "b_vendor_code", "0xcd")   # any non-zero vendor-specific code
        _write(osd / "qw_sign", "MSFT100")
        _write(osd / "use", "1")
    except Exception:
        pass

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
    # -----------------------------------------------------------------------

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

# ===== USB0 DHCP + NAT helpers =====

RUN_DIR      = Path("/run/p4wnp1")
DNSMASQ_PID  = RUN_DIR / "dnsmasq.usb0.pid"
DNSMASQ_CONF = RUN_DIR / "dnsmasq.usb0.conf"

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
    _gadget_common_init()
    cfg = USB_GADGET / "configs/c.1"
    usb_teardown()
    _gadget_common_init()

    if mode == "hid_net":
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)
        _link(_func_rndis(), cfg)
    elif mode == "hid_acm":
        _link(_func_hid(), cfg)
        _link(_func_acm(), cfg)
    elif mode == "hid_rndis":
        _set_vid_pid("0x1d6b", "0x0104")
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
        _set_vid_pid("0x1d6b", "0x0104")
        _link(_func_hid(), cfg)
        _link(_func_rndis(), cfg)
        _link(_func_msd(), cfg) 
    elif mode == "hid_net_acm":
        _link(_func_hid(), cfg)
        _link(_func_ecm(), cfg)
        _link(_func_rndis(), cfg)
        _link(_func_acm(), cfg)
    elif mode == "hid_rndis_acm":
        _set_vid_pid("0x1d6b", "0x0104")
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

# --- Wi-Fi AP (hostapd + dnsmasq), pure Python --------------------------------

def _hostapd_conf() -> str:
    return f"""\
    interface=wlan0
    driver=nl80211
    ssid={AP_SSID}
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
    """

def _dnsmasq_conf() -> str:
    # hand out 172.24.0.100..172.24.0.200, router 172.24.0.1
    return f"""\
    interface=wlan0
    bind-interfaces
    domain-needed
    bogus-priv
    dhcp-range=172.24.0.100,172.24.0.200,255.255.255.0,12h
    dhcp-option=3,172.24.0.1
    dhcp-option=6,8.8.8.8,1.1.1.1
    log-queries
    log-dhcp
    """

def _write_ap_configs():
    need_root()
    hp = Path("/etc/hostapd/hostapd-p4wnp1.conf")
    dp = Path("/etc/dnsmasq.d/p4wnp1.conf")
    hp.parent.mkdir(parents=True, exist_ok=True)
    dp.parent.mkdir(parents=True, exist_ok=True)
    hp.write_text(_hostapd_conf())
    dp.write_text(_dnsmasq_conf())
    return str(hp), str(dp)

def wifi_ap_start() -> int:
    need_root()
    # sanity: tools present?
    if not which("hostapd"):
        print("[!] hostapd not installed", file=sys.stderr); return 2
    if not which("dnsmasq"):
        print("[!] dnsmasq not installed", file=sys.stderr); return 2

    # stop client supplicant if it’s holding wlan0
    sh("systemctl stop wpa_supplicant@wlan0.service 2>/dev/null || true", check=False)

    # unblock and bring wlan0 up with static IP
    sh("rfkill unblock wifi || true", check=False)
    ip = which("ip") or "/sbin/ip"
    sh(f"{ip} link set wlan0 down || true", check=False)
    sh(f"{ip} addr flush dev wlan0 || true", check=False)
    sh(f"{ip} addr add {AP_CIDR} dev wlan0", check=False)
    sh(f"{ip} link set wlan0 up", check=False)

    # write configs
    hostapd_conf, dnsmasq_conf = _write_ap_configs()

    # point hostapd to our config and start services
    # use transient systemd units so we don't ship static files
    sh(f"systemctl stop hostapd dnsmasq 2>/dev/null || true", check=False)

    # hostapd
    sh(f"systemctl start hostapd", check=False)
    # ensure it reads our file
    Path("/etc/default/hostapd").write_text(f'DAEMON_CONF="{hostapd_conf}"\n')

    # dnsmasq uses drop-in in /etc/dnsmasq.d/, just restart
    sh("systemctl restart dnsmasq", check=False)

    # quick up-check
    h = sh("systemctl is-active hostapd", check=False).stdout.strip()
    d = sh("systemctl is-active dnsmasq", check=False).stdout.strip()
    print(f"AP: hostapd={h or 'unknown'}, dnsmasq={d or 'unknown'}")
    print(f"SSID: {AP_SSID} / PSK: {AP_PSK} / CIDR: {AP_CIDR}")
    return 0

def wifi_ap_stop() -> int:
    need_root()
    sh("systemctl stop hostapd 2>/dev/null || true", check=False)
    sh("systemctl stop dnsmasq 2>/dev/null || true", check=False)
    # leave wlan0 as-is; client mode can reclaim it
    print("AP: stopped")
    return 0

def wifi_status() -> int:
    ip = which("ip") or "/sbin/ip"
    ss = sh(f"{ip} -4 addr show wlan0", check=False).stdout or ""
    h = sh("systemctl is-active hostapd", check=False).stdout.strip()
    d = sh("systemctl is-active dnsmasq", check=False).stdout.strip()
    print(f"Wi-Fi: wlan0\n{ss.strip()}\nServices: hostapd={h or 'unknown'}, dnsmasq={d or 'unknown'}")
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
  wifi ap start
  wifi ap stop

Environment overrides:
  P4WN_AP_SSID, P4WN_AP_PSK, P4WN_AP_CIDR, P4WN_AP_CHAN, P4WN_AP_COUNTRY
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

NET_HELP = dedent("""\
Network share
-------------
Commands:
  net share <uplink>     # enable DHCP on usb0 + NAT out via <uplink> (e.g. wlan0)
  net unshare            # stop NAT/DHCP
  net status             # show NAT/DHCP status
""")

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
        if sub == "prep":     return usb_prep()
        if sub == "replug":   return usb_replug()
        if sub == "fixperms":  return usb_fixperms()
        if sub == "replug":   return usb_replug()
        if sub == "auto":     return usb_auto()

        if sub == "set":
            if len(sys.argv) < 4:
                print(USB_HELP.rstrip()); return 1
            return usb_set(sys.argv[3])
        
        if sub == "inf":
            if len(sys.argv) == 4 and sys.argv[3] == "write":
                return usb_inf_write()
                print("usage: p4wnctl usb inf write"); return 1

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

            caps = usb_caps_now()  # current active links (hid/net/msd/acm) :contentReference[oaicite:0]{index=0}

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
        if sub == "ap":
            if len(sys.argv) == 4 and sys.argv[3].lower() == "start":
                return wifi_ap_start()
            if len(sys.argv) == 4 and sys.argv[3].lower() == "stop":
                return wifi_ap_stop()
            print(WIFI_HELP.rstrip()); return 1
        print(WIFI_HELP.rstrip()); return 1

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
