#!/bin/bash
set -euo pipefail

# --- Paths ---
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/opt/p4wnp1"

# --- Require root ---
if [[ $EUID -ne 0 ]]; then
  echo "[!] Run as root: sudo ./install.sh"
  exit 1
fi

echo "[*] Installing to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
rsync -aH --delete "$REPO_DIR"/ "$INSTALL_DIR"/

echo "[*] Installing OS deps ..."
apt update
DEBIAN_FRONTEND=noninteractive apt install -y python3-pip dnsmasq hostapd rsync

echo "[*] Python deps ..."
pip3 install --break-system-packages flask netifaces luma.oled

echo "[*] Enable dwc2 (USB device) ..."
BOOTCFG="/boot/config.txt"
if ! grep -q '^dtoverlay=dwc2' "$BOOTCFG" 2>/dev/null; then
  echo 'dtoverlay=dwc2' >> "$BOOTCFG"
  echo "    - added dtoverlay=dwc2 to $BOOTCFG"
else
  echo "    - dwc2 already enabled"
fi

echo "[*] Systemd units ..."
cp "$INSTALL_DIR/p4wnp1.service" /etc/systemd/system/
cp "$INSTALL_DIR/oledmenu.service" /etc/systemd/system/
cp "$INSTALL_DIR/p4wnp1-webui.service" /etc/systemd/system/ 2>/dev/null || true

systemctl daemon-reload

# Start on boot
systemctl enable p4wnp1.service
systemctl enable oledmenu.service
systemctl enable p4wnp1-webui.service 2>/dev/null || true

# Start now
systemctl restart p4wnp1.service || true
systemctl restart oledmenu.service || true
systemctl restart p4wnp1-webui.service 2>/dev/null || true

echo "[*] Ensure gadget scripts executable ..."
chmod +x "$INSTALL_DIR"/config/usb_gadgets/*.sh || true
chmod +x "$INSTALL_DIR"/hooks/*.sh || true
chmod +x "$INSTALL_DIR"/oled/run_oled_menu.sh || true

# Create mass‑storage backing image if missing
MSD="$INSTALL_DIR/usb_mass_storage.img"
if [[ ! -f "$MSD" ]]; then
  echo "[*] Creating 128MB VFAT mass‑storage image ..."
  dd if=/dev/zero of="$MSD" bs=1M count=128
  mkfs.vfat "$MSD"
fi

# Optional: allow OLED menu to call selector/reset without password (if OLED runs as non-root)
if id -u kali &>/dev/null; then
  echo "[*] Adding sudoers rule for user 'kali' (no password for selector/reset) ..."
  cat >/etc/sudoers.d/p4wnp1-oled <<'EOF'
kali ALL=(root) NOPASSWD: /opt/p4wnp1/hooks/select_gadget.sh
kali ALL=(root) NOPASSWD: /opt/p4wnp1/hooks/gadget_reset.sh
EOF
  chmod 440 /etc/sudoers.d/p4wnp1-oled
fi

echo
echo "[✓] Install complete."
echo "    If this is your first install, reboot to load dwc2: sudo reboot"
