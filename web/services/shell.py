# /opt/p4wnp1/webui/services/shell.py
import subprocess, shlex, os

P4WN = os.environ.get("P4WN_HOME", "/opt/p4wnp1")

def run(cmd: str, timeout=6):
    env = os.environ.copy()
    env["P4WN_HOME"] = P4WN
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout, env=env
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 124, "timeout"
