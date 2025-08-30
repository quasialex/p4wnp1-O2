#!/usr/bin/env python3
import os, socket, sys, time

HOST = os.environ.get("LISTEN_ADDR", "0.0.0.0")
PORT = int(os.environ.get("LISTEN_PORT", "4444"))

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(5)
    print(f"[listener] reverse shell listener on {HOST}:{PORT}")
    while True:
        conn, addr = s.accept()
        print(f"[listener] connection from {addr[0]}:{addr[1]}")
        try:
            # Just keep the socket open; journalctl will record connections.
            # Operator can attach with socat if needed (separate operator action).
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            break
        finally:
            try: conn.close()
            except: pass

if __name__ == "__main__":
    sys.exit(main())
