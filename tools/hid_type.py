#!/usr/bin/env python3
import sys
import time

def char_to_hid(c):
    layout = {
        'a': b'\x00\x00\x04\x00\x00\x00\x00\x00',
        'b': b'\x00\x00\x05\x00\x00\x00\x00\x00',
        'c': b'\x00\x00\x06\x00\x00\x00\x00\x00',
        # add more as needed
        'A': b'\x02\x00\x04\x00\x00\x00\x00\x00',
        ' ': b'\x00\x00\x2c\x00\x00\x00\x00\x00',
        '\n': b'\x00\x00\x28\x00\x00\x00\x00\x00'
    }
    return layout.get(c, b'\x00\x00\x2c\x00\x00\x00\x00\x00')

if len(sys.argv) < 2:
    print("Usage: hid_type.py <string>")
    sys.exit(1)

for ch in sys.argv[1]:
    sys.stdout.buffer.write(char_to_hid(ch))
    sys.stdout.buffer.flush()
    time.sleep(0.01)
    sys.stdout.buffer.write(b'\x00\x00\x00\x00\x00\x00\x00\x00')
    sys.stdout.buffer.flush()
    time.sleep(0.01)
