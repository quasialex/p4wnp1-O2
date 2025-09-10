#!/usr/bin/env python3
# /opt/p4wnp1/modules/usb/gadget.py
# ConfigFS gadget manager for P4wnP1-O2 (robust Mass Storage + loop fallback)

import os
import json
import stat as pystat
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

P4WN_HOME = Path(os.environ.get("P4WN_HOME", "/opt/p4wnp1"))
CFGFS = Path("/sys/kernel/config/usb_gadget")
DEFAULT_GADGET_NAME = "p4wnp1"
TEMPLATES_DIR = P4WN_HOME / "config" / "usb_templates"

# ---------- helpers ----------

def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def _write(path: Path, data: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(data)

def _write_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

def _symlink(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if dst.exists() or dst.is_symlink():
            dst.unlink()
    except Exception:
        pass
    os.symlink(src, dst)

def _read(path: Path) -> str:
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def _list_udc() -> List[str]:
    cl = Path("/sys/class/udc")
    if not cl.exists():
        return []
    return [p.name for p in cl.iterdir() if p.is_dir()]

def _is_block_device(p: Path) -> bool:
    try:
        return pystat.S_ISBLK(os.stat(str(p)).st_mode)
    except FileNotFoundError:
        return False

def _setup_loop_ro(backing_file: Path) -> Optional[Path]:
    """
    Attach backing_file to a read-only loop device and return /dev/loopX, or None on failure.
    """
    subprocess.run(["modprobe", "loop"], check=False)
    res = subprocess.run(
        ["bash", "-lc", f"losetup -f --show -r {backing_file!s}"],
        text=True, capture_output=True
    )
    if res.returncode == 0:
        dev = res.stdout.strip()
        return Path(dev)
    return None

def require_root():
    if os.geteuid() != 0:
        raise SystemExit("This operation requires root (sudo).")

# ---------- default HID descriptors ----------

KB_REPORT_DESC = bytes.fromhex(
    "05010906A101050719E029E71500250175019508810295017508810195057501050819"
    "01290591029501750181039506750815002565050719002965"
    "8103"
)

MOUSE_REPORT_DESC = bytes.fromhex(
    "05010902A1010901A10005090901A10095017505810195017503810105010930"
    "093109381581257F750895038106C0C0"
)

# ---------- core class ----------

class USBGadget:
    """
    Minimal, robust gadget manager with HID, ECM/ACM, Mass Storage, and RNDIS.
    """

    def __init__(self, name: str = DEFAULT_GADGET_NAME):
        self.name = name
        self.root = CFGFS / name

    # ---- lifecycle ----

    def present(self) -> bool:
        return self.root.exists()

    def create(self, ids: Dict[str, str], strings: Dict[str, str]):
        _ensure_dir(self.root)
        # IDs
        _write(self.root / "idVendor", ids.get("idVendor", "0x1d6b"))
        _write(self.root / "idProduct", ids.get("idProduct", "0x0104"))
        _write(self.root / "bcdUSB", ids.get("bcdUSB", "0x0200"))
        _write(self.root / "bcdDevice", ids.get("bcdDevice", "0x0100"))
        # Strings
        s = self.root / "strings" / "0x409"
        _ensure_dir(s)
        _write(s / "manufacturer", strings.get("manufacturer", "P4wnP1-O2"))
        _write(s / "product", strings.get("product", "P4wnP1 Gadget"))
        _write(s / "serialnumber", strings.get("serial", "deadbeef"))
        # Configuration
        c = self.root / "configs" / "c.1"
        _ensure_dir(c)
        cs = c / "strings" / "0x409"
        _ensure_dir(cs)
        _write(cs / "configuration", strings.get("configuration", "Config 1"))
        _write(c / "MaxPower", str(strings.get("MaxPower", "250")))

    def remove(self):
        # Unbind first
        if (self.root / "UDC").exists():
            try:
                self.unbind()
            except Exception:
                pass
        # Detach any loop devices we used as LUN file
        try:
            fdir = self.root / "functions"
            if fdir.exists():
                for fn in fdir.glob("mass_storage.*"):
                    lunf = fn / "lun.0" / "file"
                    p = _read(lunf)
                    if p.startswith("/dev/loop"):
                        subprocess.run(["losetup", "-d", p], check=False)
        except Exception:
            pass
        # Best-effort recursive remove
        if self.root.exists():
            for path in sorted(self.root.rglob("*"), reverse=True):
                try:
                    if path.is_symlink() or path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        path.rmdir()
                except Exception:
                    pass
            try:
                self.root.rmdir()
            except Exception:
                pass

    # ---- binding ----

    def bind(self, udc: Optional[str] = None):
        if udc is None:
            udcs = _list_udc()
            if not udcs:
                raise RuntimeError("No UDC available. Is dwc2 loaded? Is ConfigFS mounted?")
            udc = udcs[0]
        _write(self.root / "UDC", udc)

    def unbind(self):
        _write(self.root / "UDC", "")

    def state(self) -> str:
        udc = _read(self.root / "UDC")
        if not udc:
            return "unbound"
        st = Path("/sys/class/udc") / udc / "state"
        return _read(st) or "unknown"

    # ---- functions ----

    def add_hid(self, name="hid.kbd", report_desc: bytes = KB_REPORT_DESC,
                protocol=1, subclass=1, report_length=8):
        fn = self.root / "functions" / f"hid.{name}"
        _ensure_dir(fn)
        _write(fn / "protocol", str(protocol))
        _write(fn / "subclass", str(subclass))
        _write(fn / "report_length", str(report_length))
        _write_bytes(fn / "report_desc", report_desc)
        self._link_to_config(fn)

    def add_mouse(self, name="hid.mouse", report_desc: bytes = MOUSE_REPORT_DESC,
                  protocol=0, subclass=1, report_length=4):
        fn = self.root / "functions" / f"hid.{name}"
        _ensure_dir(fn)
        _write(fn / "protocol", str(protocol))
        _write(fn / "subclass", str(subclass))
        _write(fn / "report_length", str(report_length))
        _write_bytes(fn / "report_desc", report_desc)
        self._link_to_config(fn)

    def add_ecm(self, name="ecm.usb0", host="12:34:56:78:9a:bc", dev="02:00:00:00:00:01"):
        fn = self.root / "functions" / f"ecm.{name}"
        _ensure_dir(fn)
        _write(fn / "host_addr", host)
        _write(fn / "dev_addr", dev)
        self._link_to_config(fn)

    def add_acm(self, name="acm.tty0"):
        fn = self.root / "functions" / f"acm.{name}"
        _ensure_dir(fn)
        self._link_to_config(fn)

    def add_mass_storage(self, name="msd.0", backing_file="/opt/p4wnp1/images/cd.iso",
                         ro=True, cdrom=True, removable=False, stall=False):
        """
        Robust Mass Storage:
          - if cdrom and 'backing_file' is a regular file, auto-attach as read-only loop
          - attempt flags → file; on EBUSY, do file → flags (best-effort)
        """
        fn = self.root / "functions" / f"mass_storage.{name}"
        _ensure_dir(fn)
        _write(fn / "stall", "1" if stall else "0")

        bf = Path(backing_file)
        if not bf.exists():
            raise SystemExit(
                f"Mass Storage backing file not found: {backing_file}\n"
                f"→ Build it first with:\n"
                f"   sudo /opt/p4wnp1/bin/usbctl.py cdrom "
                f"/opt/p4wnp1/payloads/web/captive /opt/p4wnp1/images/cd.iso --label P4WN-O2\n"
                f"Or use the 'hid_net_only' template instead."
            )

        lun = fn / "lun.0"
        _ensure_dir(lun)

        # Choose path (loop if needed)
        use_path = bf
        if cdrom and not _is_block_device(bf):
            loop = _setup_loop_ro(bf)
            if loop:
                use_path = loop

        def write_flags():
            _write(lun / "ro", "1" if ro else "0")
            _write(lun / "removable", "1" if removable else "0")
            _write(lun / "cdrom", "1" if cdrom else "0")

        # Try flags → file first
        try:
            write_flags()
            _write(lun / "file", str(use_path))
        except OSError:
            # Fallback: file → flags (best-effort)
            _write(lun / "file", str(use_path))
            try:
                write_flags()
            except OSError:
                # If flags still EBUSY, proceed; device will still work (loop is RO)
                pass

        self._link_to_config(fn)

    def add_rndis(self, name="rndis.usb0", host="12:34:56:78:9a:bd", dev="02:00:00:00:00:02"):
        fn = self.root / "functions" / f"rndis.{name}"
        _ensure_dir(fn)
        _write(fn / "host_addr", host)
        _write(fn / "dev_addr", dev)
        osd = self.root / "os_desc"
        _ensure_dir(osd)
        _write(osd / "use", "1")
        _write(osd / "b_vendor_code", "0xcd")
        _write(osd / "qw_sign", "MSFT100")
        ifn = fn / "os_desc" / "interface.rndis"
        _ensure_dir(ifn)
        _write(ifn / "compatible_id", "RNDIS")
        _write(ifn / "sub_compatible_id", "5162001")
        cfg = self.root / "configs" / "c.1"
        _symlink(cfg, osd / "c.1")
        self._link_to_config(fn)

    def _link_to_config(self, function_path: Path):
        cfg = self.root / "configs" / "c.1"
        link = cfg / function_path.name
        _symlink(function_path, link)

    # ---- templates ----

    def apply_template(self, t: Dict[str, Any], auto_bind: bool = True):
        require_root()
        if self.present():
            self.remove()

        ids = {
            "idVendor": t.get("idVendor", "0x1d6b"),
            "idProduct": t.get("idProduct", "0x0104"),
            "bcdUSB": t.get("bcdUSB", "0x0200"),
            "bcdDevice": t.get("bcdDevice", "0x0100"),
        }
        strings = {
            "manufacturer": t.get("manufacturer", "P4wnP1-O2"),
            "product": t.get("product", "P4wnP1 Gadget"),
            "serial": t.get("serial", "deadbeef"),
            "configuration": t.get("configuration", "Config 1"),
            "MaxPower": str(t.get("MaxPower", "250")),
        }
        self.create(ids, strings)

        fns = t.get("functions", {})
        for hid in fns.get("hid", []):
            rd = hid.get("report_desc_hex")
            report = bytes.fromhex(rd) if rd else KB_REPORT_DESC
            self.add_hid(name=hid.get("name", "hid.kbd"),
                         report_desc=report,
                         protocol=int(hid.get("protocol", 1)),
                         subclass=int(hid.get("subclass", 1)),
                         report_length=int(hid.get("report_length", 8)))
        for mouse in fns.get("mouse", []):
            rd = mouse.get("report_desc_hex")
            report = bytes.fromhex(rd) if rd else MOUSE_REPORT_DESC
            self.add_mouse(name=mouse.get("name", "hid.mouse"),
                           report_desc=report,
                           protocol=int(mouse.get("protocol", 0)),
                           subclass=int(mouse.get("subclass", 1)),
                           report_length=int(mouse.get("report_length", 4)))
        for ecm in fns.get("ecm", []):
            self.add_ecm(name=ecm.get("name", "ecm.usb0"),
                         host=ecm.get("host_addr", "12:34:56:78:9a:bc"),
                         dev=ecm.get("dev_addr", "02:00:00:00:00:01"))
        for acm in fns.get("acm", []):
            self.add_acm(name=acm.get("name", "acm.tty0"))
        for ms in fns.get("mass_storage", []):
            self.add_mass_storage(name=ms.get("name", "msd.0"),
                                  backing_file=ms.get("file", "/opt/p4wnp1/images/cd.iso"),
                                  ro=bool(ms.get("ro", True)),
                                  cdrom=bool(ms.get("cdrom", True)),
                                  removable=bool(ms.get("removable", False)),
                                  stall=bool(ms.get("stall", False)))
        for rnd in fns.get("rndis", []):
            self.add_rndis(name=rnd.get("name", "rndis.usb0"),
                           host=rnd.get("host_addr", "12:34:56:78:9a:bd"),
                           dev=rnd.get("dev_addr", "02:00:00:00:00:02"))

        if auto_bind:
            self.bind(udc=t.get("udc"))

    # ---- template I/O ----

    @staticmethod
    def load_template_file(path: Path) -> Dict[str, Any]:
        with open(path, "r") as f:
            return json.load(f)

    @staticmethod
    def save_template_file(path: Path, t: Dict[str, Any]):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(t, f, indent=2)

    @staticmethod
    def list_templates() -> List[str]:
        if not TEMPLATES_DIR.exists():
            return []
        return sorted([p.stem for p in TEMPLATES_DIR.glob("*.json")])

    @staticmethod
    def template_path(name: str) -> Path:
        return TEMPLATES_DIR / f"{name}.json"

