#!/usr/bin/env python3
import os, subprocess, signal

PID="/run/p4wnp1-responder.pid"
LOG="/var/log/p4wnp1-responder.log"

def _running():
    try:
        if os.path.exists(PID):
            with open(PID) as f: pid=int(f.read().strip())
            os.kill(pid,0)
            return pid
    except Exception: pass
    return None

def start():
    if _running(): print("Responder already running"); return 0
    iface=os.getenv("IFACE", os.getenv("P4WN_NET_IFACE","usb0"))
    args=["responder","-I",iface,"-wrfPd"]
    with open(LOG,"ab", buffering=0) as lf:
        p=subprocess.Popen(args, stdout=lf, stderr=lf, preexec_fn=os.setsid)
        with open(PID,"w") as f: f.write(str(p.pid))
    print(f"Responder started on {iface} (pid {p.pid})"); return 0

def stop():
    pid=_running()
    if not pid: print("Responder not running"); return 0
    try: os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError: pass
    try: os.remove(PID)
    except FileNotFoundError: pass
    print("Responder stopped"); return 0

def status():
    print("running" if _running() else "stopped"); return 0
