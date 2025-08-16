#!/bin/bash
set -euo pipefail

# ===================================
# P4wnP1-O2 Install Script (clean)
# ===================================

# --- Paths ---
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/opt/p4wnp1"

# Systemd units expected to be present in the repo:
#   p4wnp1.service
#   oledmenu.service
#   p4wnp1-webui.service
WEBUI_UNIT="p4wnp1-webui.service"
WEBUI_OVERRIDE_DIR="/etc/systemd/system/${WEBUI_UNIT}.d"
WEBUI_OVERRIDE_FILE="${WEBUI_OVERRIDE_DIR}/override.conf"

# --- Helpers ---
need_root() { if [[ $EUID -ne 0 ]]; then echo "[!] Run as root: sudo ./install.sh [options]"; exit 1; fi; }
have() { command -v "$1" >/dev/null 2>&1; }

# --- Defaults (CLI flags override) ---
WEBUI_HOST="0.0.0.0"
WEBUI_PORT="8080"
WEBUI_TOKEN=""         # optional; empty = no auth gate
TARGET_USER=""

# --- Parse args ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sudo-user)   shift; TARGET_USER="${1:-}";;
    --webui-host)  shift; WEBUI_HOST="${1:-}";;
    --webui-port)  shift; WEBUI_PORT="${1:-}";;
    --webui-token) shift; WEBUI_TOKEN="${1:-}";;
    *)
      echo "[!] Unknown option: $1"
      echo "Usage: sudo ./install.sh [--sudo-user <name>] [--webui-host 0.0.0.0] [--webui-port 8080] [--webui-token <string>]"
      exit 1;;
  esac
  shift
done

need_root

echo "[*] Installing to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
if ! have rsync; then apt update && apt install -y rsync; fi
rsync -aH --delete "$REPO_DIR"/ "$INSTALL_DIR"/

echo "[*] Installing OS deps ..."
apt update
DEBIAN_FRONTEND=noninteractive apt install -y python3 python3-pip dnsmasq hostapd

echo "[*] Python deps ..."
PIP_FLAGS=""
if pip3 install --help 2>/dev/null | grep -q -- '--break-system-packages'; then
  PIP_FLAGS="--break-system-packages"
fi
pip3 install $PIP_FLAGS flask netifaces luma.oled

# --- Enable dwc2 overlay for USB gadget ---
BOOTCFG="/boot/config.txt"
[[ -f /boot/firmware/config.txt ]] && BOOTCFG="/boot/firmware/config.txt"
if ! grep -q '^dtoverlay=dwc2' "$BOOTCFG" 2>/dev/null; then
  echo 'dtoverlay=dwc2' >> "$BOOTCFG"
  echo "[*] Added dtoverlay=dwc2 to $BOOTCFG"
else
  echo "[*] dwc2 already enabled"
fi

# --- Install systemd units from repo (NO auto-generation here) ---
echo "[*] Installing systemd units from repo ..."
install -m 0644 "$INSTALL_DIR/p4wnp1.service" /etc/systemd/system/
install -m 0644 "$INSTALL_DIR/oledmenu.service" /etc/systemd/system/ || true
install -m 0644 "$INSTALL_DIR/p4wnp1-webui.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable p4wnp1.service || true
systemctl enable oledmenu.service 2>/dev/null || true
systemctl enable "$WEBUI_UNIT"

# --- Ensure executables ---
chmod +x "$INSTALL_DIR"/config/usb_gadgets/*.sh 2>/dev/null || true
chmod +x "$INSTALL_DIR"/hooks/*.sh 2>/dev/null || true
chmod +x "$INSTALL_DIR"/oled/run_oled_menu.sh 2>/dev/null || true
[ -f "$INSTALL_DIR/p4wnctl.py" ] && chmod +x "$INSTALL_DIR/p4wnctl.py"

# --- Create mass-storage file if missing ---
MSD="$INSTALL_DIR/usb_mass_storage.img"
if [[ ! -f "$MSD" ]]; then
  echo "[*] Creating 128MB VFAT mass-storage image ..."
  dd if=/dev/zero of="$MSD" bs=1M count=128
  mkfs.vfat "$MSD"
fi

# --- Optional: sudoers for OLED/CLI (if your OLED service runs under a user) ---
add_sudoers() {
  local user="$1"
  if ! id -u "$user" >/dev/null 2>&1; then
    echo "[!] User '$user' does not exist; skipping sudoers."; return 0
  fi
  local tmp="/tmp/p4wnp1-oled-${user}.sudoers"
  local dst="/etc/sudoers.d/p4wnp1-oled-${user}"
  cat >"$tmp" <<EOF
$user ALL=(root) NOPASSWD: /opt/p4wnp1/hooks/select_gadget.sh
$user ALL=(root) NOPASSWD: /opt/p4wnp1/hooks/gadget_reset.sh
$user ALL=(root) NOPASSWD: /opt/p4wnp1/p4wnctl.py
EOF
  if visudo -cf "$tmp" >/dev/null 2>&1; then
    install -m 0440 "$tmp" "$dst"
    echo "[*] Sudoers configured for '$user' at $dst"
  else
    echo "[!] visudo validation failed; not installing sudoers for '$user'."
  fi
  rm -f "$tmp"
}

if [[ -z "$TARGET_USER" && -n "${SUDO_USER:-}" ]]; then TARGET_USER="$SUDO_USER"; fi
if [[ -z "$TARGET_USER" && -t 0 ]]; then read -r -p "[?] Add sudoers rule for which user (leave empty to skip)? " TARGET_USER; fi
if [[ -n "$TARGET_USER" ]]; then add_sudoers "$TARGET_USER"; else echo "[*] Skipping sudoers setup."; fi

# --- Web UI bind + auth token (systemd override ONLY; units are not modified) ---
echo "[*] Configuring Web UI bind and token ..."
mkdir -p "$WEBUI_OVERRIDE_DIR"
{
  echo "[Service]"
  echo "Environment=\"WEBUI_HOST=${WEBUI_HOST}\" \"WEBUI_PORT=${WEBUI_PORT}\""
  # Optional header token (checked by app.py if implemented)
  if [[ -n "$WEBUI_TOKEN" ]]; then
    echo "Environment=\"WEBUI_TOKEN=${WEBUI_TOKEN}\""
  fi
} > "$WEBUI_OVERRIDE_FILE"

systemctl daemon-reload
systemctl restart "$WEBUI_UNIT" || true

# --- Clean up legacy files if present (safe no-ops) ---
for f in \
  config/usb_gadget.sh \
  config/reload_gadget.sh \
  config/gadgets/usb_ecm_hid.sh \
  config/setup_net.sh \
  logs/.keep \
  www
do
  if [ -e "$INSTALL_DIR/$f" ]; then
    echo "[*] Removing legacy $f"
    rm -rf "$INSTALL_DIR/$f"
  fi
done

echo
echo "[✓] Install complete."
echo "    Web UI: ${WEBUI_HOST}:${WEBUI_PORT}  (service: ${WEBUI_UNIT})"
if [[ -n "$WEBUI_TOKEN" ]]; then
  echo "    Web UI token set. Clients must send header:  X-P4WN-Token: ${WEBUI_TOKEN}"
else
  echo "    No Web UI token set (open access on the bound interface)."
fi
echo "    Reboot on first install so dwc2 loads: sudo reboot"
