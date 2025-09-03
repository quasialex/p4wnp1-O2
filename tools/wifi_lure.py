#!/usr/bin/env python3
import os, time, json, signal, sys, subprocess, re
from pathlib import Path

STATE = Path(os.environ.get("P4WN_LURE_STATE", "/run/p4wnp1/wifi_lure.json"))
LIST  = Path(os.environ.get("P4WN_LURE_LIST",  "/opt/p4wnp1/config/lure_ssids.txt"))
DWELL = int(os.environ.get("P4WN_LURE_DWELL", "20"))

HOSTAPD_CONF = Path("/etc/hostapd/hostapd-p4wnp1.conf")
SSID_RE = re.compile(r"^ssid\s*=\s*(.*)$", flags=re.M)

def sh(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def read_list():
    if not LIST.exists(): return []
    ssids = []
    for l in LIST.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = l.strip()
        if s and not s.startswith("#"):
            ssids.append(s[:32])
    return ssids

def hostapd_running():
    return sh("pgrep -af '^hostapd(\\s|$)'").returncode == 0

def set_ssid(new_ssid):
    txt = HOSTAPD_CONF.read_text(encoding="utf-8", errors="ignore")
    if SSID_RE.search(txt):
        txt = SSID_RE.sub(f"ssid={new_ssid}", txt)
    else:
        txt = txt.strip() + f"\nssid={new_ssid}\n"
    HOSTAPD_CONF.write_text(txt, encoding="utf-8")
    # ctrl path matches how p4wnctl writes hostapd conf (ctrl_interface=/run/hostapd)
    sh("hostapd_cli -p /run/hostapd reconfigure >/dev/null 2>&1")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"active_ssid": new_ssid, "ts": time.time()}))

def main():
    if not hostapd_running():
        print("[!] hostapd not running. Start AP first: p4wnctl wifi ap start", file=sys.stderr)
        return 2
    if not HOSTAPD_CONF.exists():
        print(f"[!] Missing {HOSTAPD_CONF}", file=sys.stderr); return 2

    ssids = read_list()
    if not ssids:
        print(f"[!] No SSIDs in list {LIST}", file=sys.stderr); return 2

    original = None
    try:
        # remember current SSID to restore on exit
        t = HOSTAPD_CONF.read_text(encoding="utf-8", errors="ignore")
        m = SSID_RE.search(t)
        original = m.group(1).strip() if m else None

        i = 0
        while True:
            ssid = ssids[i % len(ssids)]
            set_ssid(ssid)
            time.sleep(DWELL)
            i += 1
    except KeyboardInterrupt:
        pass
    finally:
        if original:
            try: set_ssid(original)
            except Exception: pass

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    sys.exit(main())
