#!/bin/bash
# Types "a" via HID (keycode 0x04)
/bin/echo -ne '\0\0\x04\0\0\0\0\0' > /dev/hidg0
sleep 0.1
