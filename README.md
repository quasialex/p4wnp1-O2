# P4wnP1-O2 (draft)

A stealthy, modular payload launcher and HID/network attack framework for Raspberry Pi Zero / Zero 2 W. Inspired by **P4wnP1 A.L.O.A.**, rebuilt for modern builds with optional OLED UI, USB-gadget scripts, and clean payloads.

> ⚠️ Education & research only. Many payloads have legal/ethical implications. You are responsible for what you run.

---

## ✅ Features

* **Modular payloads**: HID, network, reverse shells, etc.
* **USB gadget** modes via **configfs** scripts (HID / RNDIS/ECM / Mass Storage)
* **OLED menu** (Waveshare 1.3″ SH1106) — optional, can be installed/uninstalled from the device itself
* **Web UI** (Flask) — optional, runs via systemd unit
* **Systemd** integration; services live in `systemd/`
* **Headless-friendly** CLI (`p4wnctl.py`) + a simple curses TUI (`p4wnctl.py menu`)

---

## Hardware

* Raspberry Pi Zero or Zero 2 W
* microSD (≥ 4 GB)
* (Optional) Waveshare 1.3″ OLED HAT (SH1106 on I²C `0x3C`)
* (Optional) USB-A gadget board/shim

**OS:** tested on **Kali Linux (Raspberry Pi)** (2025.x).  
Expected to work on Raspberry Pi OS Bookworm; not formally tested here.

---

## Repository layout

```
.
├─ install.sh                     # modular installer (USB / OLED / WebUI)
├─ p4wnctl.py                     # CLI (USB, payloads, web, services, IP, TUI)
├─ systemd/                       # unit files (source of truth)
│  ├─ p4wnp1.service              # core supervisor
│  ├─ p4wnp1-usb-prep.service     # configfs pre-flight (optional)
│  ├─ oledmenu.service            # OLED menu (optional)
│  └─ p4wnp1-webui.service        # Web UI (optional)
├─ oled/
│  ├─ oled_menu.py                # OLED app (reads menu_config.json)
│  └─ menu_config.json            # menu entries (actions/submenus)
├─ webui/                         # Flask app (optional)
│  ├─ app.py  sse.py  services/  templates/
├─ hooks/
│  ├─ select_gadget.sh            # switch USB mode via configfs
│  └─ gadget_reset.sh             # clean up dangling gadget state
├─ config/
│  ├─ active_payload              # path/name of current payload
│  ├─ reverse_shell.conf          # settings used by some payloads
│  └─ usb_gadgets/
│     ├─ hid_net_only.sh
│     ├─ hid_storage_net.sh
│     └─ storage_only.sh
└─ payloads/
   ├─ hid/   network/   listeners/   shell/
   └─ (your .sh payloads)
```

---

## Install (modular)

`install.sh` copies files into `/opt/p4wnp1`, installs dependencies, writes systemd units from `systemd/`, and (optionally) enables them.

```bash
git clone https://github.com/<you>/p4wnp1-o2-draft.git
cd p4wnp1-o2-draft
sudo ./install.sh [options]
# Reboot on first install so the dwc2 overlay takes effect
sudo reboot
```

### Options

* `--with-usb yes|no` *(default: yes)*
* `--with-oled auto|yes|no` *(default: auto; detects SH1106 at 0x3C)*
* `--with-webui yes|no` *(default: yes)*
* `--no-enable` *(copy units but don’t enable/start them)*
* `--sudo-user <name>` *(write sudoers for OLED menu/CLI actions)*
* `--webui-host <ip>` `--webui-port <n>` `--webui-token <str>` *(env override for Web UI)*

### Examples

**USB-only (no OLED, no Web UI):**

```bash
sudo ./install.sh --with-usb yes --with-oled no --with-webui no
```

**Auto-enable OLED if present; install Web UI but don’t start anything:**

```bash
sudo ./install.sh --with-oled auto --with-webui yes --no-enable
```

**Full stack:**

```bash
sudo ./install.sh --with-usb yes --with-oled yes --with-webui yes
```

> The installer also creates a 128 MB VFAT `usb_mass_storage.img` if missing.

---

## Managing services

You can use **systemd** directly or the **CLI**.

### systemd

```bash
# USB core
sudo systemctl status p4wnp1.service
sudo systemctl status p4wnp1-usb-prep.service

# OLED
sudo systemctl enable --now oledmenu.service
sudo systemctl disable --now oledmenu.service
sudo systemctl status oledmenu.service

# Web UI
sudo systemctl restart p4wnp1-webui.service
sudo systemctl status p4wnp1-webui.service
```

### CLI (`p4wnctl.py`) — service manager

```bash
# status (no sudo needed)
 /opt/p4wnp1/p4wnctl.py service status p4wnp1.service

# install from repo → copy to /etc/systemd/system, enable + start
sudo /opt/p4wnp1/p4wnctl.py service install oledmenu.service

# control
sudo /opt/p4wnp1/p4wnctl.py service restart p4wnp1.service
sudo /opt/p4wnp1/p4wnctl.py service uninstall p4wnp1-webui.service

# optional TUI (arrow keys)
 /opt/p4wnp1/p4wnctl.py menu
```

---

## OLED menu

* App: `oled/oled_menu.py`
* Config: `oled/menu_config.json`

You can add entries that call either the CLI or `systemctl`. Example **Services** submenu:

```json
{
  "title": "Services",
  "submenu": [
    { "title": "USB: Status",   "action": "python3 /opt/p4wnp1/p4wnctl.py service status p4wnp1.service" },
    { "title": "USB: Restart",  "action": "sudo python3 /opt/p4wnp1/p4wnctl.py service restart p4wnp1.service" },
    { "title": "OLED: Install", "action": "sudo python3 /opt/p4wnp1/p4wnctl.py service install oledmenu.service" },
    { "title": "OLED: Uninstall", "action": "sudo python3 /opt/p4wnp1/p4wnctl.py service uninstall oledmenu.service" },
    { "title": "Web: Status",   "action": "python3 /opt/p4wnp1/p4wnctl.py service status p4wnp1-webui.service" }
  ]
}
```

**I²C note:** auto-detect expects I²C enabled. Ensure `dtparam=i2c_arm=on` is present in `/boot/config.txt` (or `/boot/firmware/config.txt` on Bookworm). If you run OLED unprivileged, add your user to the `i2c` group:

```bash
sudo usermod -aG i2c $USER
```

---

## USB gadget modes

Predefined configfs scripts (under `config/usb_gadgets/`):

* `hid_net_only.sh` — HID + RNDIS/ECM
* `hid_storage_net.sh` — HID + NET + Mass Storage
* `storage_only.sh` — Mass Storage only

Set them via CLI:

```bash
# show current mode (reads configfs)
 /opt/p4wnp1/p4wnctl.py usb status

# set mode (requires sudo)
sudo /opt/p4wnp1/p4wnctl.py usb set hid_net_only
sudo /opt/p4wnp1/p4wnctl.py usb set hid_storage_net
sudo /opt/p4wnp1/p4wnctl.py usb set storage_only
```

---

## Payloads

* Place payload scripts in `payloads/` or subfolders (`hid/`, `network/`, `listeners/`, `shell/`).
* The **active payload** pointer lives in `config/active_payload` (stores a path or a short name resolved by the CLI).

```bash
# list candidates
 /opt/p4wnp1/p4wnctl.py payload list

# set active payload
sudo /opt/p4wnp1/p4wnctl.py payload set reverse_shell
sudo /opt/p4wnp1/p4wnctl.py payload set payloads/hid/autorun_powershell.sh

# check
 /opt/p4wnp1/p4wnctl.py payload status
```

Some payloads read `config/reverse_shell.conf` for defaults.

---

## Web UI (optional)

Folder: `webui/` (`app.py`, `sse.py`, `services/`, `templates/`).

* The installer writes a systemd override containing `WEBUI_HOST`, `WEBUI_PORT` (and optional `WEBUI_TOKEN`).
* Change them by re-running `install.sh` with `--webui-*` flags **or** by editing:

  ```
  /etc/systemd/system/p4wnp1-webui.service.d/override.conf
  ```

  then:

  ```bash
  sudo systemctl daemon-reload
  sudo systemctl restart p4wnp1-webui.service
  ```

> Note: the old `webui/server.py` flow is removed. The unit runs `webui/app.py`.

---

## Sudoers (optional convenience)

If you pass `--sudo-user <name>`, the installer writes a minimal sudoers policy to let the menu/CLI perform privileged actions without repeated password prompts:

```
/opt/p4wnp1/hooks/select_gadget.sh
/opt/p4wnp1/hooks/gadget_reset.sh
/opt/p4wnp1/p4wnctl.py
```

---

## Troubleshooting

* **No USB controller found**
  `p4wnctl.py usb status` prints “No USB Device Controller”.
  → Ensure `dtoverlay=dwc2` is present in `/boot/config.txt` (or `/boot/firmware/config.txt`) and **reboot**.
  Modules should load: `dwc2`, `libcomposite`, `configfs`.

* **OLED not detected (auto mode)**

  ```bash
  sudo apt install -y i2c-tools
  i2cdetect -y 1
  ```

  Expect to see `0x3C`. Otherwise, use `--with-oled yes` or run OLED without auto-detect.

* **Service won’t start**

  ```bash
  sudo systemctl status <unit> --no-pager
  journalctl -u <unit> -n 100 --no-pager
  ```

* **Mass Storage image missing**
  The installer creates `usb_mass_storage.img` (128 MB VFAT) if absent. Replace it with your own if desired.

---

## Uninstall (units only)

```bash
sudo systemctl disable --now p4wnp1.service p4wnp1-usb-prep.service p4wnp1-webui.service oledmenu.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/{p4wnp1.service,p4wnp1-usb-prep.service,p4wnp1-webui.service,oledmenu.service}
sudo systemctl daemon-reload
```

> To remove files entirely, delete `/opt/p4wnp1` after stopping services.

---

## Credits

* Based on **P4wnP1 A.L.O.A.** (Rogan Dawes)
* Raspberry Pi Foundation
* Luma.OLED, Bettercap, Impacket, Responder, and the wider infosec community

---

## Sanity checklist (pre-release)

* [ ] `systemd/` contains the four units; `install.sh` installs from **systemd/** first.
* [ ] `install.sh` flags work (`--with-usb|oled|webui`, `--no-enable`, `--sudo-user`).
* [ ] `p4wnctl.py` can run `usb status`, `payload list`, `ip`, and `service status <unit>`.
* [ ] OLED menu entries point to `p4wnctl.py service …` **or** `systemctl …` and succeed.
* [ ] `hooks/select_gadget.sh` + `hooks/gadget_reset.sh` are executable.
* [ ] `config/usb_gadgets/*.sh` are executable.
* [ ] (Optional) Web UI reachable at your `WEBUI_HOST:WEBUI_PORT`.
