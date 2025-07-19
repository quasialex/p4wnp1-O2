#!/bin/bash
# Listens for reverse shell on TCP port 4444

PORT=4444
echo "[+] Listening on port $PORT for reverse shell..."
sudo nc -lvnp $PORT
