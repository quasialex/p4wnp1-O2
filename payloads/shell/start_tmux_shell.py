#!/usr/bin/env python3

import subprocess
import os

def start_tmux_shell():
    socket_path = "/tmp/p4wnp1_shell"
    print(f"[+] Launching tmux shell on socket: {socket_path}")

    os.environ["TMUX_TMPDIR"] = "/tmp"
    try:
        subprocess.Popen(["tmux", "-S", socket_path, "new-session", "-d", "/bin/bash"])
        subprocess.Popen(["tmux", "-S", socket_path, "attach-session"])
    except Exception as e:
        print(f"[!] Error launching tmux shell: {e}")

if __name__ == "__main__":
    start_tmux_shell()
