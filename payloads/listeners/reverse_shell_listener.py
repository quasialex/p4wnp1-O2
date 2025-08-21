#!/usr/bin/env python3
import os, sys, shutil, subprocess, time
from pathlib import Path

P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
LOG_DIR   = Path(P4WN_HOME) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

PORT = int(os.environ.get("RSHELL_PORT", "4444"))
NAME = os.environ.get("RSHELL_NAME", "rshell")

def have(cmd): return shutil.which(cmd) is not None

def start_tmux():
    sess = f"p4wnp1_{NAME}"
    cmd = f'rlwrap nc -lvnp {PORT}'
    if not have("tmux"):
        return False, "tmux missing; falling back to systemd-run"
    # kill existing
    subprocess.run(f"tmux has-session -t {sess}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(f"tmux kill-session -t {sess}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # start detached
    rc = subprocess.call(f'tmux new-session -d -s {sess} "{cmd}"', shell=True, cwd=P4WN_HOME)
    return (rc == 0), f"tmux session: {sess} (attach with: tmux attach -t {sess})"

def start_systemd():
    if not have("systemd-run"):
        return False, "systemd-run not found"
    log = (LOG_DIR / f"{NAME}.log").as_posix()
    unit = f"p4wnp1-{NAME}"
    scmd = f'systemd-run --unit={unit} --collect --property=StandardOutput=append:{log} ' \
           f'--property=StandardError=append:{log} -- bash -lc "rlwrap nc -lvnp {PORT}"'
    rc = subprocess.call(scmd, shell=True, cwd=P4WN_HOME)
    return (rc == 0), f"systemd unit: {unit} (log: {log})"

def main():
    ok, msg = start_tmux()
    if not ok:
        ok, msg = start_systemd()
    print(("✓ " if ok else "✗ ") + msg)

if __name__ == "__main__":
    sys.exit(0 if main() is None else 0)
