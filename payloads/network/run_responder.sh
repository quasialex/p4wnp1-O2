#!/bin/bash
# Launches Responder on usb0 interface
cd /opt/Responder
sudo python3 Responder.py -I usb0 -wrf
