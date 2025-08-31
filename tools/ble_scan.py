#!/usr/bin/env python3
import os, sys, json, time, subprocess, signal
from datetime import datetime

LOG = os.environ.get("P4WN_BLE_LOG", "/run/p4wnp1/ble_scan.jsonl")
IFACE = os.environ.get("P4WN_BLE_IFACE", "hci0")

# Uses hcitool (BlueZ). Good enough for passive advertising discovery.
# Requires: apt install bluez (already present on RPi OS)
def main():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    # bring up interface
    subprocess.call(["hciconfig", IFACE, "up"])
    # start passive LE scan (duplicates on to see RSSI/name updates)
    p = subprocess.Popen(
        ["stdbuf","-oL","bluetoothctl","--monitor"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    try:
        for line in p.stdout:
            line=line.strip()
            # Format usually: "AA:BB:CC:DD:EE:FF <name or (unknown)>"
            if not line or ":" not in line: 
                continue
            parts = line.split(" ", 1)
            mac = parts[0].strip()
            name = parts[1].strip() if len(parts)>1 else ""
            evt = {"ts": datetime.utcnow().isoformat()+"Z", "mac": mac, "name": name}
            with open(LOG, "a") as f:
                f.write(json.dumps(evt)+"\n")
    except KeyboardInterrupt:
        pass
    finally:
        try:
            p.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    # Allow clean kill
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    main()
