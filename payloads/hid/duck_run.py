#!/usr/bin/env python3
import os, sys, subprocess, shlex
from pathlib import Path

P4WN = Path("/opt/p4wnp1")
DUCK = P4WN / "tools/ducky.py"

def sh(cmd): return subprocess.run(cmd, shell=True)

def main():
    script = sys.argv[1] if len(sys.argv) > 1 else str(P4WN / "payloads/hid/sample.duck")
    if not Path(script).exists():
        print(f"[!] DuckyScript not found: {script}", file=sys.stderr); return 2
    return sh(f"/usr/bin/env python3 {shlex.quote(str(DUCK))} {shlex.quote(script)}").returncode

if __name__ == "__main__":
    sys.exit(main())
