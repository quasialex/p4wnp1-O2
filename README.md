# P4wnP1-Zero2W

A stealthy, modular payload launcher and HID network attack framework for Raspberry Pi Zero 2 W.
Inspired by P4wnP1 A.L.O.A., rebuilt for modern builds with joystick OLED UI and clean payloads.

## ✅ Features
- Modular payloads (network, HID, covert shell, Wi-Fi)
- OLED + joystick menu interface (WIP)
- USB gadget emulation via config templates
- GitHub auto-update support
- Systemd integration

## 📂 Structure
- `/payloads/` — modular attack scripts
- `/hooks/` — OLED/menu logic, startup scripts
- `/tools/` — injectors, Responder/DNS/etc
- `/config/` — USB gadget templates
- `/logs/` — runtime logs (e.g., Responder)

## 🚀 Usage
Clone the repo:
`bash
git clone https://github.com/quasialex/p4wnp1-zero2w.git /opt/p4wnp1
`

Run setup:
`bash
sudo bash /opt/p4wnp1/setup_payloads.sh
`

Run a payload manually:
`bash
sudo bash /opt/p4wnp1/payloads/network/rogue_dhcp_dns.sh
`

## 📡 OLED Menu (WIP)
Joystick-controlled menu to select payload interactively:
`bash
/opt/p4wnp1/hooks/oled_menu.py
`

## ✨ Credits
- Based on P4wnP1 A.L.O.A. by Rogan Dawes
- Raspberry Pi Foundation
- Adafruit CircuitPython for OLED tools
