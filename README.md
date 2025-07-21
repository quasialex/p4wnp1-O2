# P4wnP1-O2

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
```

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

### 🌐 Web Interface

A lightweight Flask-based web UI is included. It lists available payloads and lets you trigger them remotely.

Start the server:

```bash
sudo python3 /opt/p4wnp1/webui/server.py
```

Then browse to `http://<pi-ip>:8080`.

---

### 💻 USB Ethernet Access (`g_ether`) – macOS/Linux

This method allows full SSH access to your Pi Zero 2 W using only a single USB cable — no Wi-Fi or HDMI needed.

#### 🧩 Prerequisites

* Raspberry Pi Zero or Zero 2 W (must support OTG)
* A **data-capable micro-USB cable**
* Raspberry Pi OS Bookworm or Kali Linux (headless CLI build)

#### 🔧 Setup Instructions

1. **Enable USB OTG overlay**
   Edit `/boot/firmware/config.txt` and add:

   ```ini
   dtoverlay=dwc2
   ```

2. **Enable USB Ethernet gadget**
   Edit `/boot/firmware/cmdline.txt` (must be one line), and add after `rootwait`:

   ```text
   modules-load=dwc2,g_ether
   ```

3. **Assign static IP to the Pi's USB interface**
   Create `/etc/network/interfaces.d/usb0`:

   ```ini
   auto usb0
   iface usb0 inet static
       address 192.168.7.2
       netmask 255.255.255.0
   ```

4. **Reboot**, then connect the Pi to your Mac via the USB (data) port.

5. **Configure macOS USB interface:**

   * Go to **System Settings > Network**
   * A new interface should appear (e.g., *RNDIS/Ethernet Gadget*)
   * Set **Manual IP**:

     * IP: `192.168.7.1`
     * Subnet: `255.255.255.0`
     * Router: *(leave blank)*

6. **SSH into the Pi**

   ```bash
   ssh pi@192.168.7.2
   ```

---

#### ⚠️ USB Cable Warning

Many micro-USB cables are **charge-only** and do **not support data transfer**. If the Pi powers up but no new interface appears on macOS:

* Try a cable known to support **file transfer** (e.g., with Android phones)
* Recommended brands: **Anker**, **UGREEN**, **Raspberry Pi Official Cable**
* Avoid cables labeled “Fast Charging Only”

---

## 🛠 Requirements

* Raspberry Pi Zero or Zero 2 W
* Kali Linux ARM image (Zero/Zero2W build)
* USB OTG capability — use the **“USB” port**, not the “PWR” port (supports gadget mode)
* Waveshare 1.3" 128x64 OLED HAT (SH1106, i2c)
* Optional: UPS Hat or custom enclosure for portable/stealth use

---

## ✨ Credits

* Based on **P4wnP1 A.L.O.A.** by Rogan Dawes
* Raspberry Pi Foundation
* Adafruit CircuitPython + Luma.OLED
* Bettercap, Impacket, Responder, and the wider infosec community

---

## 📬 Contact

Feel free to open an issue or PR if you’d like to contribute.
