#!/usr/bin/env python3
"""
Simple event bus with 3 watchers:
 - USB state (uses existing modules.usb.events via import)
 - Interface link status (polls 'ip -br link')
 - Timer (every N seconds)
Actions: run shell commands or call Python entrypoints.
"""
import os, time, subprocess, threading, yaml
from pathlib import Path
from typing import Dict, Any, Callable, List

P4WN_HOME = Path(os.environ.get("P4WN_HOME", "/opt/p4wnp1"))
TRIG_DIR = P4WN_HOME / "config" / "triggers"

def sh(cmd: str):
    subprocess.run(["bash","-lc",cmd], check=False)

def load_all() -> Dict[str, Any]:
    cfg = {}
    if not TRIG_DIR.exists(): return cfg
    for f in TRIG_DIR.glob("*.yml"):
        try:
            data = yaml.safe_load(f.read_text()) or {}
            cfg[f.stem] = data
        except Exception:
            pass
    return cfg

def run_actions(actions: List[Dict[str, Any]]):
    for a in actions or []:
        t = a.get("type","command")
        if t == "command":
            cmd = a.get("run")
            if not cmd: continue
            if isinstance(cmd, list):
                subprocess.run(cmd, check=False)
            else:
                sh(cmd)
        elif t == "python":
            ep = a.get("entrypoint")  # "pkg.module:func"
            if not ep: continue
            mod, fn = ep.split(":")
            mod = __import__(mod, fromlist=[fn])
            getattr(mod, fn)()

class WatcherUSB(threading.Thread):
    def __init__(self, cfg):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.last = None
    def run(self):
        state_file = Path("/sys/class/udc")
        while True:
            # map to configured/unconfigured based on gadget sysfs
            udc = None
            g = Path("/sys/kernel/config/usb_gadget/p4wnp1/UDC")
            if g.exists():
                try:
                    v = g.read_text().strip()
                    if v: udc = v
                except Exception: pass
            st = "not_attached"
            if udc:
                s = Path("/sys/class/udc")/udc/"state"
                try:
                    sv = s.read_text().strip()
                    if sv == "configured": st = "attached"
                    else: st = "not_attached"
                except Exception: pass
            if st != self.last:
                self.last = st
                acts = (self.cfg.get("usb") or {}).get("on_attach" if st=="attached" else "on_detach")
                run_actions(acts)
            time.sleep(0.5)

class WatcherNet(threading.Thread):
    def __init__(self, cfg):
        super().__init__(daemon=True); self.cfg = cfg; self.last = {}
    def run(self):
        while True:
            res = subprocess.run(["bash","-lc","ip -br link"], text=True, capture_output=True)
            now={}
            for line in (res.stdout or "").splitlines():
                parts = line.split()
                if not parts: continue
                iface, state = parts[0], ("UP" in parts[1])
                now[iface]=state
                prev = self.last.get(iface)
                if prev is None: continue
                if prev!=state:
                    key = "net_up" if state else "net_down"
                    acts = (self.cfg.get("net") or {}).get(key)
                    # allow filter 'iface'
                    if acts:
                        acts = [a for a in acts if (not a.get("iface") or a["iface"]==iface)]
                        run_actions(acts)
            self.last = now
            time.sleep(1.0)

class WatcherTimer(threading.Thread):
    def __init__(self, cfg):
        super().__init__(daemon=True); self.cfg = cfg
    def run(self):
        tcfg = self.cfg.get("timer") or {}
        every = int(tcfg.get("every_sec", 0))
        if every<=0: 
            return
        while True:
            time.sleep(every)
            run_actions(tcfg.get("on_tick"))

def serve():
    while True:
        cfg = load_all()
        w1 = WatcherUSB(cfg); w2 = WatcherNet(cfg); w3 = WatcherTimer(cfg)
        w1.start(); w2.start(); w3.start()
        # reload every 10s
        for _ in range(100):
            time.sleep(0.1)
        # threads will exit when function returns; just loop to reload

