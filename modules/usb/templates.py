#!/usr/bin/env python3
# /opt/p4wnp1/modules/usb/templates.py
import json
import os
from pathlib import Path
from typing import Dict, Any
from .gadget import USBGadget, TEMPLATES_DIR, DEFAULT_GADGET_NAME

P4WN_HOME = Path(os.environ.get("P4WN_HOME", "/opt/p4wnp1"))

SCHEMA_HINT = {
  "name": "hid_net_cdrom",
  "idVendor": "0x1d6b",
  "idProduct": "0x0104",
  "bcdUSB": "0x0200",
  "bcdDevice": "0x0100",
  "manufacturer": "P4wnP1-O2",
  "product": "P4wnP1 O2",
  "serial": "deadbeef",
  "configuration": "Config 1",
  "MaxPower": 250,
  "udc": None,
  "functions": {
    "hid": [
      {"name":"hid.kbd","protocol":1,"subclass":1,"report_length":8,"report_desc_hex": None}
    ],
    "mouse": [],
    "ecm": [
      {"name":"ecm.usb0","host_addr":"12:34:56:78:9a:bc","dev_addr":"02:00:00:00:00:01"}
    ],
    "rndis": [],
    "acm": [],
    "mass_storage": [
      {"name":"msd.0","file":"/opt/p4wnp1/images/cd.iso","ro":True,"cdrom":True,"removable":False,"stall":False}
    ]
  }
}

def ensure_dirs():
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    (P4WN_HOME / "images").mkdir(parents=True, exist_ok=True)

def save(name: str, template: Dict[str, Any]):
    ensure_dirs()
    path = TEMPLATES_DIR / f"{name}.json"
    with open(path, "w") as f:
        json.dump(template, f, indent=2)

def load(name: str) -> Dict[str, Any]:
    path = TEMPLATES_DIR / f"{name}.json"
    with open(path, "r") as f:
        return json.load(f)

def apply(name: str, gadget_name: str = DEFAULT_GADGET_NAME, auto_bind: bool = True):
    t = load(name)
    g = USBGadget(gadget_name)
    g.apply_template(t, auto_bind=auto_bind)
    return g.state()

def list_all():
    ensure_dirs()
    return sorted([p.stem for p in TEMPLATES_DIR.glob("*.json")])

def delete(name: str):
    path = TEMPLATES_DIR / f"{name}.json"
    if path.exists():
        path.unlink()

def schema_hint() -> Dict[str, Any]:
    return SCHEMA_HINT

