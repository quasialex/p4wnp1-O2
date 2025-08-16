#!/usr/bin/env python3
import os, sys, importlib.util
from pathlib import Path

P4WN_HOME = Path(os.environ.get("P4WN_HOME", "/opt/p4wnp1")).resolve()

def load_impl():
    impl = P4WN_HOME / "payloads" / "_private" / "responder_impl.py"
    if not impl.exists():
        print("[i] No private implementation found at payloads/_private/responder_impl.py", file=sys.stderr)
        return None
    spec = importlib.util.spec_from_file_location("responder_impl", impl)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    if not hasattr(mod, "run"):
        print("[!] responder_impl.py must define run(iface: str)", file=sys.stderr)
        return None
    return mod

def main():
    iface = os.getenv("IFACE", "usb0")  # allow override via manifest/env
    print(f"[*] Responder (stub) — target iface: {iface}")
    if not lab_guard():
        sys.exit(2)
    mod = load_impl()
    if not mod:
        print("[i] Stub only. Provide responder_impl.py with run(iface) to enable in your lab.")
        sys.exit(0)
    # Hand-off to your private code
    return int(bool(mod.run(iface)))  # expect 0/False for success

if __name__ == "__main__":
    sys.exit(main())
