# P4wnP1-Zero2W

A stealthy, modular payload launcher and HID/network attack framework for Raspberry Pi Zero 2 W.  
Inspired by P4wnP1 A.L.O.A., rebuilt for modern builds with joystick OLED UI, USB gadget scripts, and clean payloads.

---

## ✅ Features

- Modular payloads (network, HID, covert shell, Wi-Fi)
- OLED + joystick menu interface (WIP)
- USB gadget emulation via config templates
- GitHub auto-update support
- Systemd integration
- Fully headless CLI Kali setup (no XFCE bloat)

---

## 📂 Project Structure

- `/payloads/` — modular attack scripts
- `/hooks/` — OLED/menu logic, startup scripts
- `/tools/` — injectors, Responder/DNS/etc
- `/config/` — USB gadget templates
- `/logs/` — runtime logs (e.g., Responder)

---

## 🧹 Setup: Headless Kali Linux on Pi Zero 2 W

To remove XFCE GUI and prep a clean, fast Kali headless build:

```bash
curl -sSL https://raw.githubusercontent.com/quasialex/p4wnp1-zero2w/main/scripts/setup_headless_kali.sh | bash
````

> ⚠️ Or run manually:
> `sudo bash scripts/setup_headless_kali.sh`

What it does:

* Purges XFCE GUI and display manager
* Installs core tools (git, tmux, python, bettercap, etc.)
* Sets system to boot into CLI (multi-user.target)
* Installs `pipx` and installs `impacket` cleanly
* Installs `luma.oled` via `pip3 --break-system-packages` for OLED support

---

## 🚀 Usage

Clone the repo:

```bash
git clone https://github.com/quasialex/p4wnp1-zero2w.git /opt/p4wnp1
```

Run setup:

```bash
sudo bash /opt/p4wnp1/setup_payloads.sh
```

Run a payload manually:

```bash
sudo bash /opt/p4wnp1/payloads/network/rogue_dhcp_dns.sh
```

---

## 📡 OLED Menu (WIP)

Joystick-controlled menu to select payload interactively:

```bash
sudo python3 /opt/p4wnp1/hooks/oled_menu.py
```

> Requires: `luma.oled`, joystick/button GPIO mapping, and Waveshare 1.3" OLED setup.

---

## 🛠 Requirements

* Raspberry Pi Zero 2 W
* Kali Linux ARM image (Zero/Zero2W build)
* USB OTG port (USB gadget support enabled)
* Waveshare 1.3" 128x64 OLED HAT
* Optional: UPS Hat or custom enclosure for mobile rigs

---

## ✨ Credits

* Based on **P4wnP1 A.L.O.A.** by Rogan Dawes
* Raspberry Pi Foundation
* Adafruit CircuitPython + Luma.OLED
* Bettercap, Impacket, Responder, and the wider infosec community

---

## 📬 Contact

Feel free to open an issue or PR if you’d like to contribute.
