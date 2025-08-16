# File: /opt/p4wnp1/payloads/hid/lockpicker.py
from tools import hid_type

print("[*] Unlocking target machine via HID")
cmds = [
    "powershell -Command \"Add-Type -AssemblyName PresentationFramework;"
    "[System.Windows.MessageBox]::Show('Security Update Installed. Please Restart.')\""
]
for cmd in cmds:
    hid_type.type_string(cmd)
