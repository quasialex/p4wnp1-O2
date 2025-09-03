#!/usr/bin/env python3
import os, sys, time, json, signal, subprocess, socket, re
from pathlib import Path

CFG  = Path("/opt/p4wnp1/config/autojoin.json")
P4WN = "/opt/p4wnp1/p4wnctl.py"
RUN  = Path("/run/p4wnp1"); RUN.mkdir(parents=True, exist_ok=True)
PIDF = RUN / "autojoin.pid"
IFACE = "wlan0"

DEFAULT = {"interval": 20, "known": []}  # known: [{ssid:"Home", psk:"secret", hidden:false}, ...]

def load():
    if CFG.exists():
        try: return {**DEFAULT, **json.loads(CFG.read_text())}
        except Exception: pass
    return DEFAULT

def connected():
    out = subprocess.run(f"iw dev {IFACE} link", shell=True, text=True, capture_output=True).stdout
    return "Connected to" in (out or "")

def hostapd_running():
    return (RUN / "hostapd.wlan0.pid").exists()

def net_up():
    # simple internet check
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2).close()
        return True
    except OSError:
        return False

def scan_ssids():
    # Requires managed mode; only called when AP is stopped/not running.
    out = subprocess.run(f"iw dev {IFACE} scan 2>/dev/null", shell=True, text=True, capture_output=True).stdout
    # parse "SSID: ..." and the closest preceding "signal: -xx.x dBm"
    found = []
    sig = None
    for ln in (out or "").splitlines():
        if "signal:" in ln:
            m = re.search(r"signal:\s*(-?\d+\.?\d*)", ln); 
            if m: sig = float(m.group(1))
        if ln.strip().startswith("SSID: "):
            ssid = ln.split("SSID:",1)[1].strip()
            if ssid: found.append((ssid, sig if sig is not None else -999.0))
    return found

def join(ssid, psk, hidden=False):
    args = [P4WN, "wifi", "client", "join", ssid, psk]
    if hidden: args.append("--hidden")
    subprocess.run(args)

def main():
    cfg = load()
    PIDF.write_text(str(os.getpid()))
    try:
        while True:
            if hostapd_running():
                time.sleep(cfg["interval"]); continue
            if connected() and net_up():
                time.sleep(cfg["interval"]); continue

            known = {k["ssid"]: k for k in cfg.get("known", []) if "ssid" in k}
            if not known:
                time.sleep(cfg["interval"]); continue

            seen = scan_ssids()
            # choose strongest known SSID
            candidates = [(ssid, sig, known[ssid]) for (ssid, sig) in seen if ssid in known]
            if candidates:
                candidates.sort(key=lambda t: t[1], reverse=True)
                ssid, _sig, rec = candidates[0]
                join(ssid, rec.get("psk",""), bool(rec.get("hidden", False)))
            time.sleep(cfg["interval"])
    except KeyboardInterrupt:
        pass
    finally:
        try: PIDF.unlink()
        except Exception: pass

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    main()
