#!/usr/bin/env python3
# /opt/p4wnp1/bin/usbctl.py
# USB helper for templates/UDC/CD-ROM with repo-path bootstrap + recovery helpers + ISO padding.

import argparse
import os
import sys
import subprocess
from pathlib import Path

# --- repo path bootstrap so "modules" imports always work ---
REPO_ROOT = Path(__file__).resolve().parents[1]  # -> /opt/p4wnp1
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.usb.gadget import USBGadget, TEMPLATES_DIR  # noqa: E402
from modules.usb import templates as tmpl  # noqa: E402

P4WN_HOME = Path(os.environ.get("P4WN_HOME", "/opt/p4wnp1"))
CFGFS = Path("/sys/kernel/config/usb_gadget")

def sh(cmd: str, capture: bool = False):
    if capture:
        return subprocess.run(["bash", "-lc", cmd], text=True, capture_output=True)
    return subprocess.run(["bash", "-lc", cmd])

# ------------------- template commands -------------------

def cmd_templates(args):
    if args.action == "list":
        for n in tmpl.list_all():
            print(n)
    elif args.action == "save":
        src = Path(args.file)
        data = src.read_text()
        name = args.name or src.stem
        import json
        tmpl.save(name, json.loads(data))
        print(f"Saved template '{name}' to {TEMPLATES_DIR}/{name}.json")
    elif args.action == "delete":
        tmpl.delete(args.name)
        print(f"Deleted template '{args.name}'")
    elif args.action == "schema":
        import json
        print(json.dumps(tmpl.schema_hint(), indent=2))
    elif args.action == "apply":
        st = tmpl.apply(args.name, auto_bind=not args.no_bind)
        print(f"Applied '{args.name}'. State: {st}")

# ------------------- UDC commands -------------------

def _gadgets():
    if not CFGFS.exists():
        return []
    return [p for p in CFGFS.iterdir() if p.is_dir()]

def _read(p: Path) -> str:
    try:
        return p.read_text().strip()
    except Exception:
        return ""

def cmd_udc(args):
    if args.action == "state":
        g = USBGadget(args.gadget)
        print(g.state())
    elif args.action == "bind":
        g = USBGadget(args.gadget)
        g.bind(udc=args.udc)
        print("bound")
    elif args.action == "unbind":
        g = USBGadget(args.gadget)
        g.unbind()
        print("unbound")
    elif args.action == "remove":
        g = USBGadget(args.gadget)
        g.remove()
        print("removed")
    elif args.action == "who":
        for gdir in _gadgets():
            udc = _read(gdir / "UDC")
            print(f"{gdir.name}\t{udc if udc else '-'}")
    elif args.action == "force-reset":
        for gdir in _gadgets():
            try:
                (gdir / "UDC").write_text("")
                print(f"Unbound {gdir.name}")
            except Exception:
                pass
        mods = ["g_multi","g_ether","g_serial","g_mass_storage","g_hid",
                "g_acm","g_midi","g_audio","g_ncm","g_rndis","gadgetfs"]
        for m in mods:
            sh(f"modprobe -r {m} 2>/dev/null || true")
        print("UDC force-reset done")

# ------------------- CD-ROM (ISO) -------------------

def cmd_cdrom(args):
    """
    Build an ISO (read-only) from a folder.
    Requires genisoimage or xorriso.
    Pads the ISO to --pad-mib MiB (default 16) to satisfy picky kernels.
    """
    src = Path(args.src).resolve()
    out = Path(args.out).resolve()
    if not src.exists() or not src.is_dir():
        raise SystemExit(f"Source folder not found: {src}\n"
                         f"Create it and add at least one file, e.g.:\n"
                         f"  sudo mkdir -p {src}\n"
                         f"  echo 'hi' | sudo tee {src}/index.html")

    out.parent.mkdir(parents=True, exist_ok=True)

    def has(cmd):
        return subprocess.call(["bash", "-lc", f"command -v {cmd} >/dev/null 2>&1"]) == 0

    if has("genisoimage"):
        cmd = f'genisoimage -J -r -V "{args.label}" -o "{out}" "{src}"'
    elif has("xorriso"):
        cmd = f'xorriso -as mkisofs -J -r -V "{args.label}" -o "{out}" "{src}"'
    else:
        raise SystemExit("Neither genisoimage nor xorriso found. Install one of them.")

    res = sh(cmd, capture=True)
    if res.returncode != 0:
        msg = (res.stdout or "") + (res.stderr or "")
        raise SystemExit(f"ISO build failed (exit {res.returncode}).\n{msg}")

    # Pad ISO to N MiB unless disabled
    if args.pad_mib and args.pad_mib > 0:
        sz = args.pad_mib * 1024 * 1024
        sh(f"truncate -s {sz} '{out}'")
    print(f"ISO created: {out}")

# ------------------- parser & main -------------------

def build_parser():
    ap = argparse.ArgumentParser(description="P4wnP1-O2 USB helper")
    sub = ap.add_subparsers(dest="cmd")

    t = sub.add_parser("template", help="manage USB templates")
    tsub = t.add_subparsers(dest="action")
    tsub.add_parser("list")
    p_save = tsub.add_parser("save"); p_save.add_argument("file"); p_save.add_argument("--name")
    p_del = tsub.add_parser("delete"); p_del.add_argument("name")
    tsub.add_parser("schema")
    p_app = tsub.add_parser("apply"); p_app.add_argument("name"); p_app.add_argument("--no-bind", action="store_true")

    u = sub.add_parser("udc", help="bind/unbind/state/remove gadget")
    usub = u.add_subparsers(dest="action")
    p_state = usub.add_parser("state"); p_state.add_argument("--gadget", default="p4wnp1")
    p_bind  = usub.add_parser("bind");  p_bind.add_argument("--gadget", default="p4wnp1"); p_bind.add_argument("--udc")
    p_unb   = usub.add_parser("unbind");p_unb.add_argument("--gadget", default="p4wnp1")
    p_rm    = usub.add_parser("remove");p_rm.add_argument("--gadget", default="p4wnp1")
    usub.add_parser("who")
    usub.add_parser("force-reset")

    c = sub.add_parser("cdrom", help="create ISO from folder")
    c.add_argument("src"); c.add_argument("out"); c.add_argument("--label", default="P4WN-O2")
    c.add_argument("--pad-mib", type=int, default=16, help="Pad ISO to MiB (default: 16, 0=disable)")

    return ap

def main():
    ap = build_parser()
    args = ap.parse_args()
    if args.cmd == "template":
        cmd_templates(args)
    elif args.cmd == "udc":
        cmd_udc(args)
    elif args.cmd == "cdrom":
        cmd_cdrom(args)
    else:
        ap.print_help()

if __name__ == "__main__":
    main()

