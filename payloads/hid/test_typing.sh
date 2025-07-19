#!/bin/bash
# Injects simple keystrokes via HID
echo -ne '\0\0\x04\0\0\0\0\0' > /dev/hidg0  # Types 'a'
sleep 0.2
