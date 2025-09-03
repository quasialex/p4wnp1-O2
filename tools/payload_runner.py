#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
payload_runner.py — glue runner for payloads (framework only)

Directory convention (per payload <name>):
  payloads/custom/<name>/manifest.json
  payloads/custom/<name>/main.py

manifest.json fields (all optional):
{
  "name": "win_rdp_enable",
  "desc": "Enable RDP + open firewall",
  "env": { "P4WN_LHOST": "__AUTO__", "P4WN_LPORT": "4444" },
  "timeout_sec": 120
}
- __AUTO__ for P4WN_LHOST resolves to the device primary IP via p4wnctl (or fallback)

Runner:
  payload_runner.py run <name>            # executes payloads/custom/<name>/main.py
  payload_runner.py list                  # lists custom payloads
  payload_runner.py describe <name>       # prints manifest
"""
import os, sys, json, time, subprocess, shlex
from pathlib import Path

P4WN   = Path(os.environ.get("P4WN_HOME","/opt/p4wnp1"))
BASE   = P4WN / "payloads" / "custom"
LOGDIR = Path("/var/log/p4wnp1/payloads"); LOGDIR.mkdir(parents=True, exist_ok=True)

def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True, **kw)

def primary_ip():
    # Ask p4wnctl (already knows how you pick primary). Fallback to usb0 then wlan0.
    try:
        cp = sh(f"{P4WN}/p4wnctl.py ip primary"); 
        out = (cp.stdout or "").strip().split()
        return out[-1] if out else ""
    except Exception:
        pass
    for dev in ("usb0","wlan0"):
        cp = sh(f"ip -4 -o addr show {dev} | awk '{{print $4}}' | cut -d/ -f1")
        if cp.stdout.strip(): return cp.stdout.strip()
    return "127.0.0.1"

def list_payloads():
    out = []
    if BASE.exists():
        for d in sorted(BASE.iterdir()):
            if d.is_dir() and (d / "main.py").exists():
                out.append(d.name)
    return out

def load_manifest(name):
    mf = BASE / name / "manifest.json"
    if not mf.exists(): return {"name": name, "desc": "", "env": {}, "timeout_sec": 0}
    return json.loads(mf.read_text())

def describe(name):
    m = load_manifest(name); print(json.dumps(m, indent=2))

def inject_env(env):
    # Resolve __AUTO__
    env = dict(env or {})
    for k, v in list(env.items()):
        if isinstance(v, str) and v == "__AUTO__":
            if k in ("P4WN_LHOST","LHOST"): env[k] = primary_ip()
    # Map into os.environ without clobbering user overrides
    for k, v in env.items():
        os.environ.setdefault(k, str(v))

def run_payload(name):
    pdir = BASE / name
    main = pdir / "main.py"
    if not main.exists(): 
        print(f"[!] payload '{name}' not found at {main}", file=sys.stderr)
        return 2
    m = load_manifest(name)
    inject_env(m.get("env", {}))
    timeout = int(m.get("timeout_sec", 0) or 0)
    logf = LOGDIR / f"{name}.log"
    with open(logf, "a", encoding="utf-8") as lf:
        lf.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} RUN {name} ---\n")
        try:
            cp = subprocess.run([sys.executable, str(main)], text=True,
                                capture_output=True, timeout=(timeout or None))
            if cp.stdout: lf.write(cp.stdout)
            if cp.stderr: lf.write(cp.stderr)
            lf.write(f"\n[exit] {cp.returncode}\n")
            print(f"[*] Payload '{name}' exit={cp.returncode}. Log: {logf}")
            return cp.returncode
        except subprocess.TimeoutExpired:
            lf.write("\n[timeout]\n")
            print(f"[!] Payload '{name}' timed out after {timeout}s. Log: {logf}")
            return 124

def usage():
    print("payload_runner.py run <name> | list | describe <name>")

def main():
    if len(sys.argv) < 2: return usage() or 1
    cmd = sys.argv[1]
    if cmd == "list":
        for n in list_payloads(): print(n); return 0
    if cmd == "describe":
        if len(sys.argv) < 3: return usage() or 1
        return describe(sys.argv[2]) or 0
    if cmd == "run":
        if len(sys.argv) < 3: return usage() or 1
        return run_payload(sys.argv[2])
    return usage() or 1

if __name__ == "__main__":
    sys.exit(main())
