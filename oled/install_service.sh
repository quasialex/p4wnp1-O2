#!/bin/bash
sudo cp oledmenu.service /etc/systemd/system/
sudo systemctl daemon-reexec
sudo systemctl enable oledmenu.service
sudo systemctl start oledmenu.service
echo "OLED menu service installed and started."
