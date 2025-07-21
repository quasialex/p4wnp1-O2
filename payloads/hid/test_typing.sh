#!/bin/bash
# Types "a" via HID (keycode 0x04)
# Send the HID report for the key press
/bin/echo -ne '\0\0\x04\0\0\0\0\0' > /dev/hidg0
# Follow up with an all-zero report to release the key
/bin/echo -ne '\0\0\0\0\0\0\0\0' > /dev/hidg0
sleep 0.1

