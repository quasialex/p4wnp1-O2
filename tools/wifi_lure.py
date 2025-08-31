#!/usr/bin/env python3
import os, time, json, signal, sys, subprocess, re
from pathlib import Path

STATE   = Path(os.environ.get("P4WN_LURE_STATE", "/run/p4wnp1/wifi_lure.json"))
LIST    = Path(os.environ.get("P4WN_LURE_LIST",  "/opt/p4wnp1/config/lure_ssids.txt"))
DWELL   = int(os.environ.get("P4WN_LURE_DWELL", "20"))  # seconds between SSID swaps

P4WNCTL = "/opt/p4wnp1/p4wnctl.py"

def read_list():
    if not LIST.exists(): return []
    return [l.strip() for l in LIST.read_text().splitlines() if l.strip()]

def current_ap_off():
    subprocess.call([P4WNCTL, "wifi", "ap", "stop"])

def set_ssid(ssid):
    subprocess.call([P4WNCTL, "wifi", "set", "ssid", ssid])
    # Keep channel/country as previously configured
    subprocess.call([P4WNCTL, "wifi", "ap", "start"])

def main():
    os.makedirs("/run/p4wnp1", exist_ok=True)
    lst = read_list()
    if not lst: 
        print("[!] No SSIDs in list; exiting."); return
    idx = 0
    try:
        while True:
            ssid = lst[idx % len(lst)]
            current_ap_off()
            set_ssid(ssid)
            STATE.write_text(json.dumps({"active_ssid": ssid, "ts": time.time()}))
            time.sleep(DWELL)
            idx += 1
    except KeyboardInterrupt:
        pass
    finally:
        current_ap_off()

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    main()
