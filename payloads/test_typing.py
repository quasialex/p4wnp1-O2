# File: /opt/p4wnp1/payloads/hid/test_typing.py
import time
from tools import hid_type

print("[*] Typing test payload...")
hid_type.type_string("Hello from P4wnP1!")
time.sleep(1)
hid_type.type_string("This is a test typing payload.")
