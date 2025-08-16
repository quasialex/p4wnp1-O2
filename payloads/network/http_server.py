# File: payloads/network/http_server.py
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
import os

PORT = 8080
DIRECTORY = "/opt/p4wnp1/loot"

os.chdir(DIRECTORY)
print(f"[*] Starting HTTP server on port {PORT}, serving {DIRECTORY}")

with TCPServer(("", PORT), SimpleHTTPRequestHandler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[*] Server stopped.")
