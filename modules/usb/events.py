#!/usr/bin/env python3
# /opt/p4wnp1/modules/usb/events.py
# Polls the active UDC state and runs trigger actions on attach/detach.
import os
import time
import subprocess
import yaml
from pathlib import Path
from typing import Callable, Optional

P4WN_HOME = Path(os.environ.get("P4WN_HOME", "/opt/p4wnp1"))
CFGFS = Path("/sys/kernel/config/usb_gadget")
TRIGGERS_FILE = P4WN_HOME / "config" / "triggers" / "usb.yml"
DEFAULT_GADGET_NAME = "p4wnp1"

def _load_triggers():
    if not TRIGGERS_FILE.exists():
        return {}
    with open(TRIGGERS_FILE, "r") as f:
        return yaml.safe_load(f) or {}

def _udc_name(gadget_name: str) -> Optional[str]:
    p = CFGFS / gadget_name / "UDC"
    if not p.exists():
        return None
    try:
        with open(p, "r") as f:
            v = f.read().strip()
            return v if v else None
    except FileNotFoundError:
        return None

def _udc_state(udc: str) -> str:
    s = Path("/sys/class/udc") / udc / "state"
    try:
        with open(s, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "unknown"

def _run_action(action: dict):
    t = action.get("type", "command")
    if t == "command":
        cmd = action.get("run")
        if not cmd:
            return
        if isinstance(cmd, str):
            cmd = ["bash", "-lc", cmd]
        try:
            subprocess.run(cmd, check=False)
        except Exception:
            pass

def _handle(event: str, triggers: dict):
    key = "on_attach" if event == "configured" else "on_detach"
    for action in (triggers.get(key) or []):
        _run_action(action)

def watch(gadget_name: str = DEFAULT_GADGET_NAME, poll_interval: float = 0.5):
    last = None
    while True:
        udc = _udc_name(gadget_name)
        if not udc:
            # Unbound gadget; treat as detached
            if last != "not attached":
                triggers = _load_triggers()
                _handle("not attached", triggers)
                last = "not attached"
            time.sleep(poll_interval)
            continue

        st = _udc_state(udc)
        if st != last:
            triggers = _load_triggers()
            if st == "configured":
                _handle("configured", triggers)
            elif st in ("not attached", "attached", "powered", "unknown"):
                _handle("not attached", triggers)
            last = st
        time.sleep(poll_interval)

