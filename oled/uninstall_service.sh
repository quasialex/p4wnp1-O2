#!/bin/bash
sudo systemctl stop oledmenu.service
sudo systemctl disable oledmenu.service
sudo rm /etc/systemd/system/oledmenu.service
sudo systemctl daemon-reexec
echo "OLED menu service removed."
