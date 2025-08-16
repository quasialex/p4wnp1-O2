#!/bin/bash
set -euo pipefail

# ===================================
# P4wnP1-O2 Install Script (modular)
# ===================================

# --- Paths ---
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/opt/p4wnp1"

# Systemd unit names (installed if present in repo)
P4WNP1_UNIT="p4wnp1.service"
USB_PREP_UNIT="p4wnp1-usb-prep.service"     # optional
OLED_UNIT="oledmenu.service"                # optional
WEBUI_UNIT="p4wnp1-webui.service"           # optional

WEBUI_OVERRIDE_DIR="/etc/systemd/system/${WEBUI_UNIT}.d"
WEBUI_OVERRIDE_FILE="${WEBUI_OVERRIDE_DIR}/override.conf"

# --- Helpers ---
need_root() { if [[ $EUID -ne 0 ]]; then echo "[!] Run as root: sudo ./install.sh [options]"; exit 1; fi; }
have() { command -v "$1" >/dev/null 2>&1; }

# OLED auto-detect helper (Waveshare 1.3 SH1106 @ 0x3C on I2C-1)
has_oled() {
  if ! have i2cdetect; then
    apt-get update -y && apt-get install -y i2c-tools || true
  fi
  i2cdetect -y 1 2>/dev/null | grep -qi ' 3c'
}

# --- Defaults (CLI flags override) ---
WEBUI_HOST="0.0.0.0"
WEBUI_PORT="8080"
WEBUI_TOKEN=""         # optional; empty = no auth gate
TARGET_USER=""

WITH_USB="yes"         # yes|no
WITH_OLED="auto"       # auto|yes|no
WITH_WEBUI="yes"       # yes|no
ENABLE_SERVICES="yes"  # yes|no (copy units but don't enable/start when 'no')

# --- Parse args ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sudo-user)   shift; TARGET_USER="${1:-}";;
    --webui-host)  shift; WEBUI_HOST="${1:-}";;
    --webui-port)  shift; WEBUI_PORT="${1:-}";;
    --webui-token) shift; WEBUI_TOKEN="${1:-}";;

    --with-usb)    shift; WITH_USB="${1:-yes}";;
    --with-oled)   shift; WITH_OLED="${1:-auto}";;
    --with-webui)  shift; WITH_WEBUI="${1:-yes}";;

    --no-enable)   ENABLE_SERVICES="no";;
    -h|--help)
      cat <<EOF
Usage: sudo ./install.sh [options]

User / WebUI:
  --sudo-user <name>              Add sudoers rules for this user (p4wnctl + hooks)
  --webui-host <ip>               Web UI bind (default: 0.0.0.0)
  --webui-port <n>                Web UI port (default: 8080)
  --webui-token <string>          Optional header token (X-P4WN-Token)

Modular services:
  --with-usb yes|no               Install/enable USB core units (default: yes)
  --with-oled auto|yes|no         Install/enable OLED (default: auto)
  --with-webui yes|no             Install/enable Web UI (default: yes)
  --no-enable                     Copy unit files but don't enable/start any

Examples:
  USB only (no OLED/web):      --with-usb yes --with-oled no --with-webui no
  Auto OLED if present:        --with-oled auto
  Copy units only (no start):  --no-enable
EOF
      exit 0;;
    *)
      echo "[!] Unknown option: $1"
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
# Always needed:
pip3 install $PIP_FLAGS netifaces luma.oled
# Flask only if WebUI requested:
if [[ "$WITH_WEBUI" == "yes" ]]; then
  pip3 install $PIP_FLAGS flask
fi

# --- Enable dwc2 overlay for USB gadget ---
BOOTCFG="/boot/config.txt"
[[ -f /boot/firmware/config.txt ]] && BOOTCFG="/boot/firmware/config.txt"
if ! grep -q '^dtoverlay=dwc2' "$BOOTCFG" 2>/dev/null; then
  echo 'dtoverlay=dwc2' >> "$BOOTCFG"
  echo "[*] Added dtoverlay=dwc2 to $BOOTCFG"
else
  echo "[*] dwc2 already enabled"
fi

# --- Install systemd units from repo (copy if present) ---
echo "[*] Installing systemd units from repo ..."
inst_unit() {
  local name="$1"
  local src=""
  if   [[ -f "$INSTALL_DIR/systemd/$name" ]]; then src="$INSTALL_DIR/systemd/$name"
  elif [[ -f "$INSTALL_DIR/$name" ]]; then       src="$INSTALL_DIR/$name"
  else
    return 0
  fi
  install -m 0644 "$src" "/etc/systemd/system/$name"
  echo "  - installed $name (from $(realpath "$src" 2>/dev/null || echo "$src"))"
}
inst_unit "$P4WNP1_UNIT"
inst_unit "$USB_PREP_UNIT"
inst_unit "$OLED_UNIT"
inst_unit "$WEBUI_UNIT"

systemctl daemon-reload

# --- Enable/Start selected services ---
start_unit() {
  local u="$1"
  systemctl enable "$u" 2>/dev/null || true
  systemctl restart "$u" 2>/dev/null || true
}

# USB core (p4wnp1 + optional usb-prep)
if [[ "$WITH_USB" == "yes" ]]; then
  if [[ "$ENABLE_SERVICES" == "yes" ]]; then
    [[ -f "/etc/systemd/system/$P4WNP1_UNIT" ]] && start_unit "$P4WNP1_UNIT"
    [[ -f "/etc/systemd/system/$USB_PREP_UNIT" ]] && start_unit "$USB_PREP_UNIT"
  fi
  echo "[*] USB services: $( [[ "$ENABLE_SERVICES" == "yes" ]] && echo 'enabled' || echo 'installed (disabled)')"
else
  echo "[*] USB services: disabled by flag"
fi

# OLED menu (auto/yes/no)
WANT_OLED="no"
case "$WITH_OLED" in
  yes)  WANT_OLED="yes" ;;
  auto) has_oled && WANT_OLED="yes" || WANT_OLED="no" ;;
  no)   WANT_OLED="no" ;;
esac

if [[ "$WANT_OLED" == "yes" ]]; then
  if [[ -f "/etc/systemd/system/$OLED_UNIT" && "$ENABLE_SERVICES" == "yes" ]]; then
    start_unit "$OLED_UNIT"
  fi
  echo "[*] OLED: enabled (${WITH_OLED})"
else
  echo "[*] OLED: not enabled (${WITH_OLED})"
fi

# Web UI (yes/no)
if [[ "$WITH_WEBUI" == "yes" ]]; then
  if [[ -f "/etc/systemd/system/$WEBUI_UNIT" && "$ENABLE_SERVICES" == "yes" ]]; then
    start_unit "$WEBUI_UNIT"
  fi
  echo "[*] WebUI: enabled"
else
  echo "[*] WebUI: not enabled"
fi

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
if [[ "$WITH_WEBUI" == "yes" ]]; then
  echo "[*] Configuring Web UI bind and token ..."
  mkdir -p "$WEBUI_OVERRIDE_DIR"
  {
    echo "[Service]"
    echo "Environment=\"WEBUI_HOST=${WEBUI_HOST}\" \"WEBUI_PORT=${WEBUI_PORT}\""
    if [[ -n "$WEBUI_TOKEN" ]]; then
      echo "Environment=\"WEBUI_TOKEN=${WEBUI_TOKEN}\""
    fi
  } > "$WEBUI_OVERRIDE_FILE"

  if [[ "$ENABLE_SERVICES" == "yes" ]]; then
    systemctl daemon-reload
    systemctl restart "$WEBUI_UNIT" || true
  fi
fi

# --- Clean up legacy files if present (safe no-ops) ---
for f in \
  config/usb_gadget.sh \
  config/reload_gadget.sh \
  config/gadgets/usb_ecm_hid.sh \
  config/setup_net.sh \
  logs/.keep \
  www
do
  if [[ -e "$INSTALL_DIR/$f" ]]; then
    echo "[*] Removing legacy $f"
    rm -rf "$INSTALL_DIR/$f"
  fi
done

echo
echo "[✓] Install complete."
if [[ "$WITH_WEBUI" == "yes" ]]; then
  echo "    Web UI: ${WEBUI_HOST}:${WEBUI_PORT}  (service: ${WEBUI_UNIT})"
else
  echo "    Web UI: disabled"
fi
if [[ -n "$WEBUI_TOKEN" ]]; then
  echo "    Web UI token set. Clients must send header:  X-P4WN-Token: ${WEBUI_TOKEN}"
else
  echo "    No Web UI token set (open access on the bound interface)."
fi
echo "    Reboot on first install so dwc2 loads: sudo reboot"
