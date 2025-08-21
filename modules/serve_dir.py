#!/usr/bin/env python3
import argparse, http.server, socketserver, os
ap = argparse.ArgumentParser(description="Serve a directory over HTTP")
ap.add_argument("--dir", default="/opt/p4wnp1/loot", help="Directory to serve")
ap.add_argument("--port", type=int, default=8000)
args = ap.parse_args()
os.chdir(args.dir)
with socketserver.TCPServer(("0.0.0.0", args.port), http.server.SimpleHTTPRequestHandler) as httpd:
    print(f"Serving {args.dir} on :{args.port}")
    httpd.serve_forever()
