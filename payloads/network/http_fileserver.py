#!/usr/bin/env python3
import http.server, socketserver, os, sys, pathlib

ROOT = os.environ.get("SERVE_DIR", "/opt/p4wnp1/share")
PORT = int(os.environ.get("SERVE_PORT", "8080"))

def main():
    root = pathlib.Path(ROOT)
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"[http] serving {root} on 0.0.0.0:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0

if __name__ == "__main__":
    sys.exit(main())
