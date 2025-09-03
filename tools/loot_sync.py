#!/usr/bin/env python3
import os, sys, time, json, signal, socket, subprocess
from pathlib import Path

CFG  = Path("/opt/p4wnp1/config/sync.json")
RUN  = Path("/run/p4wnp1"); RUN.mkdir(parents=True, exist_ok=True)
PIDF = RUN / "sync.pid"

DEFAULT = {
  "interval": 30,
  "host": "192.168.1.100",
  "user": "p4wn",
  "dest": "/srv/p4wnp1",
  "key": "/opt/p4wnp1/config/sync_id_ed25519",
  "paths": ["/opt/p4wnp1/loot", "/var/log/p4wnp1", "/run/p4wnp1/ble_scan.jsonl"]
}

def load():
    if CFG.exists():
        try: return {**DEFAULT, **json.loads(CFG.read_text())}
        except Exception: pass
    return DEFAULT

def reachable(host, port=22):
    try:
        socket.create_connection((host, port), timeout=2).close()
        return True
    except OSError:
        return False

def sync(cfg):
    paths = [p for p in cfg["paths"] if Path(p).exists()]
    if not paths: return
    ssh = f'ssh -i {cfg["key"]} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
    cmd = ["rsync","-a","--partial","--mkpath","--ignore-missing-args","-e",ssh] + paths + [f'{cfg["user"]}@{cfg["host"]}:{cfg["dest"]}/']
    subprocess.run(cmd)

def main():
    cfg = load()
    PIDF.write_text(str(os.getpid()))
    try:
        while True:
            if reachable(cfg["host"], 22):
                sync(cfg)
            time.sleep(cfg["interval"])
    except KeyboardInterrupt:
        pass
    finally:
        try: PIDF.unlink()
        except Exception: pass

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    main()
