#!/bin/bash
set -euo pipefail

# =============================================================
# P4wnP1‑O2 Unified Installer (full‑fat, modular, ~300 lines)
# -------------------------------------------------------------
# Goals:
#  - Keep legacy breadth (USB gadget, OLED, Web UI, Wi‑Fi/portal)
#  - Add recent repo structure updates (systemd units under systemd/, services/portal, etc.)
#  - Robust across Debian/Kali/Raspberry Pi OS variants
#  - Safe defaults, idempotent where sensible
#  - Optional components controllable by flags
# =============================================================

# ------------------- Paths & Constants -------------------
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_ROOT="/opt/p4wnp1"
SYSTEMD_DIR="/etc/systemd/system"

APACHE_SITES="/etc/apache2/sites-available"
APACHE_ENABLED="/etc/apache2/sites-enabled"

P4WNP1_UNIT="p4wnp1.service"
USB_PREP_UNIT="p4wnp1-usb-prep.service"        # optional if present in repo
WIFIAP_UNIT="p4wnp1-wifiap.service"            # optional if present in repo
OLED_UNIT="oledmenu.service"                   # optional
WEBUI_UNIT="p4wnp1-webui.service"              # optional (if you use Flask web)
PORTAL_VHOST="p4wnp1-portal.conf"              # services/portal/conf/p4wnp1-portal.conf

# ------------------- Helpers -------------------
have()      { command -v "$1" >/dev/null 2>&1; }
is_pi()     { [[ -f /proc/device-tree/model ]] && grep -qi 'raspberry pi' /proc/device-tree/model; }
need_root() { if [[ $EUID -ne 0 ]]; then echo "[!] Run as root (sudo)."; exit 2; fi; }

log() { printf "\033[1;36m[*]\033[0m %s\n" "$*"; }
ok()  { printf "\033[1;32m[✓]\033[0m %s\n" "$*"; }
warn(){ printf "\033[1;33m[!]\033[0m %s\n" "$*"; }

# Dry‑run wrapper
DRY_RUN="no"
run() {
  if [[ "$DRY_RUN" == "yes" ]]; then
    printf "[dry-run]"; printf ' %q' "$@"; echo
  else
    "$@"
  fi
}

# OLED auto‑detect (Waveshare 1.3 SH1106 @ 0x3C on I2C‑1 typical)
has_oled() {
  if ! have i2cdetect; then
    run apt-get update -y || true
    run apt-get install -y i2c-tools || true
  fi
  i2cdetect -y 1 2>/dev/null | grep -qi ' 3c'
}

# Python pip flags (Debian 12+)
pip_flags() {
  if pip3 install --help 2>/dev/null | grep -q -- '--break-system-packages'; then
    echo "--break-system-packages"
  else
    echo ""
  fi
}

# /boot config path abstraction
boot_cfg_path() {
  if [[ -f /boot/firmware/config.txt ]]; then
    echo "/boot/firmware/config.txt"
  else
    echo "/boot/config.txt"
  fi
}

# ------------------- Defaults (overridable by flags) -------------------
WITH_USB="yes"          # yes|no
WITH_OLED="auto"        # auto|yes|no
WITH_WEBUI="yes"        # yes|no (Flask-based if present)
WITH_PORTAL="yes"       # yes|no (Apache captive portal vhost if present)
ENABLE_UNITS="yes"      # yes|no (if 'no' => install units but do not enable/start)
TARGET_USER="${SUDO_USER:-}" # for sudoers rules (optional)

WEBUI_HOST="0.0.0.0"
WEBUI_PORT="8080"
WEBUI_TOKEN=""          # optional X-P4WN-Token

# ------------------- CLI -------------------
usage() {
cat <<EOF
Usage: sudo ./install.sh [options]

Components:
  --with-usb yes|no           Install/enable USB core & helpers (default: yes)
  --with-oled auto|yes|no     Install/enable OLED menu (default: auto)
  --with-webui yes|no         Install/enable Flask Web UI if unit present (default: yes)
  --with-portal yes|no        Install Apache captive portal vhost if present (default: yes)
  --no-enable                 Install units but do not enable/start (default: enable)

User/Web UI:
  --sudo-user <name>          Add sudoers (NOPASSWD) for hooks + p4wnctl
  --webui-host <ip>           Web UI bind (default: 0.0.0.0)
  --webui-port <n>            Web UI port (default: 8080)
  --webui-token <str>         Optional header token (X-P4WN-Token)

Other:
  --dry-run                   Print actions only
  -h|--help                   Show this help

Examples:
  USB only (no OLED/web/portal):
      ./install.sh --with-usb yes --with-oled no --with-webui no --with-portal no
  Auto OLED if present:
      ./install.sh --with-oled auto
  Copy units without starting:
      ./install.sh --no-enable
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-usb) shift; WITH_USB="${1:-yes}";;
    --with-oled) shift; WITH_OLED="${1:-auto}";;
    --with-webui) shift; WITH_WEBUI="${1:-yes}";;
    --with-portal) shift; WITH_PORTAL="${1:-yes}";;
    --no-enable) ENABLE_UNITS="no";;
    --sudo-user) shift; TARGET_USER="${1:-}";;
    --webui-host) shift; WEBUI_HOST="${1:-0.0.0.0}";;
    --webui-port) shift; WEBUI_PORT="${1:-8080}";;
    --webui-token) shift; WEBUI_TOKEN="${1:-}";;
    --dry-run) DRY_RUN="yes";;
    -h|--help) usage; exit 0;;
    *) warn "Unknown option: $1"; usage; exit 1;;
  esac
  shift
done

need_root

# ------------------- Package Install -------------------
log "Installing OS dependencies (safe across Debian/Kali/RPiOS) ..."
export DEBIAN_FRONTEND=noninteractive
run apt-get update -y || true
# NOTE: do NOT request 'iptables-nft' (not a valid package). We install iptables+nftables properly.
run apt-get install -y --no-install-recommends \
  python3 python3-pip python3-venv python3-yaml python3-spidev python3-rpi.gpio python3-requests \
  git curl jq tmux rsync \
  iw iproute2 wireless-tools \
  dnsmasq hostapd \
  apache2 apache2-bin \
  openssl ca-certificates \
  nftables iptables iptables-nftables-compat \
  i2c-tools \
  impacket-scripts \
  network-manager || true

# Apache modules useful for portal & CGI
run a2enmod rewrite headers cgi || true

ok "Base packages installed."

# ------------------- Sync Repo to /opt/p4wnp1 -------------------
log "Sync repository to ${DEST_ROOT} ..."
run mkdir -p "$DEST_ROOT"
run rsync -aH --delete \
  --exclude ".git" --exclude ".github" --exclude ".venv" \
  "$REPO_DIR"/ "$DEST_ROOT"/
ok "Files synced."

# ------------------- Python Dependencies -------------------
log "Installing Python dependencies ..."
PIP_FLAGS="$(pip_flags)"
# Always-present libs for tooling + OLED
run pip3 install $PIP_FLAGS netifaces luma.oled flask || true

ok "Python deps installed."

# ------------------- Kernel Overlays (dwc2, i2c, spi + spidev) -------------------
BOOTCFG="$(boot_cfg_path)"
log "Ensuring overlays in ${BOOTCFG} (idempotent) ..."

ensure_line() {
  local key="$1"
  local file="$2"
  grep -q "^${key}\$" "$file" 2>/dev/null || echo "$key" >> "$file"
}

# USB Gadget controller
ensure_line 'dtoverlay=dwc2' "$BOOTCFG"

# I2C and SPI base params
ensure_line 'dtparam=i2c_arm=on' "$BOOTCFG"
ensure_line 'dtparam=spi=on' "$BOOTCFG"

# SPI spidev overlay for /dev/spidev0.0 (Bookworm and later need this)
OVLDIR="/boot/firmware/overlays"
[[ -d /boot/overlays ]] && OVLDIR="/boot/overlays"
if [[ -f "$OVLDIR/spi0-0cs.dtbo" ]]; then
  ensure_line 'dtoverlay=spi0-0cs' "$BOOTCFG"
elif [[ -f "$OVLDIR/spi0-1cs.dtbo" ]]; then
  ensure_line 'dtoverlay=spi0-1cs' "$BOOTCFG"
else
  warn "No spi0-0cs or spi0-1cs overlay found in $OVLDIR; spidev node may not appear"
fi

# Ensure modules load at boot
mkdir -p /etc/modules-load.d
echo i2c-dev | tee /etc/modules-load.d/i2c.conf >/dev/null
{ echo spi_bcm2835; echo spidev; } | tee /etc/modules-load.d/spi.conf >/dev/null

# Try to load modules now (nodes may need reboot for DT to apply)
modprobe i2c-dev 2>/dev/null || true
modprobe spi_bcm2835 2>/dev/null || true
modprobe spidev 2>/dev/null || true

# ------------------- udev Rules (HID gadget friendly perms) -------------------
log "Writing udev rules for HID gadget access ..."
run bash -c 'cat >/etc/udev/rules.d/99-p4wnp1.rules <<EOF
SUBSYSTEM=="hidg", MODE="0666"
KERNEL=="hidg*", MODE="0666"
EOF'
run udevadm control --reload-rules || true
ok "udev rules installed."

# ------------------- Install Systemd Units (from repo if present) -------------------
log "Installing systemd units (if present in repo) ..."

inst_unit() {
  local unit="$1"
  local src=""
  if   [[ -f "$DEST_ROOT/systemd/$unit" ]]; then src="$DEST_ROOT/systemd/$unit"
  elif [[ -f "$DEST_ROOT/$unit" ]]; then src="$DEST_ROOT/$unit"
  else return 0; fi
  run install -m 0644 "$src" "$SYSTEMD_DIR/$unit"
  log "  - Installed $unit"
}

for u in "$P4WNP1_UNIT" "$USB_PREP_UNIT" "$WIFIAP_UNIT" "$OLED_UNIT" "$WEBUI_UNIT"; do
  inst_unit "$u"
done

run systemctl daemon-reload

start_unit() {
  local u="$1"
  [[ ! -f "$SYSTEMD_DIR/$u" ]] && return 0
  if [[ "$ENABLE_UNITS" == "yes" ]]; then
    run systemctl enable "$u" || true
    run systemctl restart "$u" || true
  fi
}

# USB core services
if [[ "$WITH_USB" == "yes" ]]; then
  start_unit "$P4WNP1_UNIT"
  start_unit "$USB_PREP_UNIT"
  log "USB core: $( [[ "$ENABLE_UNITS" == "yes" ]] && echo enabled || echo installed )"
else
  log "USB core: disabled by flag"
fi

# OLED (auto/yes/no)
WANT_OLED="no"
case "$WITH_OLED" in
  yes) WANT_OLED="yes";;
  auto) has_oled && WANT_OLED="yes" || WANT_OLED="no";;
  no) WANT_OLED="no";;
esac
if [[ "$WANT_OLED" == "yes" ]]; then
  start_unit "$OLED_UNIT"
  log "OLED: enabled (${WITH_OLED})"
else
  log "OLED: not enabled (${WITH_OLED})"
fi

# Web UI service
if [[ "$WITH_WEBUI" == "yes" ]]; then
  start_unit "$WEBUI_UNIT"
  log "Web UI: enabled"
else
  log "Web UI: not enabled"
fi

# Wi‑Fi AP helper (installed/enabled if present)
start_unit "$WIFIAP_UNIT"

# ------------------- Apache Captive Portal -------------------
if [[ "$WITH_PORTAL" == "yes" ]]; then
  log "Configuring Apache captive portal (if vhost present) ..."
  if [[ -f "$DEST_ROOT/services/portal/conf/$PORTAL_VHOST" ]]; then
    run install -m 0644 "$DEST_ROOT/services/portal/conf/$PORTAL_VHOST" \
      "$APACHE_SITES/$PORTAL_VHOST"
    # Avoid default vhost clash
    run a2dissite 000-default || true
    run a2ensite "${PORTAL_VHOST%%.conf}" || true
    run systemctl restart apache2 || true
    ok "Apache portal site enabled."
  else
    warn "Portal vhost not found in repo (services/portal/conf/$PORTAL_VHOST) — skipping."
  fi
else
  log "Apache captive portal: disabled by flag"
fi

# ------------------- Permissions & Executables -------------------
log "Ensuring executables ..." 
run chmod +x "$DEST_ROOT"/p4wnctl.py 2>/dev/null || true
run chmod +x "$DEST_ROOT"/hooks/*.sh 2>/dev/null || true
run chmod +x "$DEST_ROOT"/config/usb_gadgets/*.sh 2>/dev/null || true
run chmod +x "$DEST_ROOT"/oled/*.sh 2>/dev/null || true

# ------------------- Sudoers (optional) -------------------
add_sudoers() {
  local user="$1"
  if ! id -u "$user" >/dev/null 2>&1; then
    warn "User '$user' not found; skipping sudoers."
    return 0
  fi
  local tmp="/tmp/p4wnp1-${user}.sudoers"
  local dst="/etc/sudoers.d/p4wnp1-${user}"
  cat >"$tmp" <<'EOF'
# Allow OLED/menu hooks and controller without password
# (adjust as needed for your security model)
EOF
  {
    echo "$user ALL=(root) NOPASSWD: /opt/p4wnp1/p4wnctl.py"
    echo "$user ALL=(root) NOPASSWD: /opt/p4wnp1/hooks/select_gadget.sh"
    echo "$user ALL=(root) NOPASSWD: /opt/p4wnp1/hooks/gadget_reset.sh"
  } >> "$tmp"
  if visudo -cf "$tmp" >/dev/null 2>&1; then
    run install -m 0440 "$tmp" "$dst"
    ok "Sudoers installed for $user at $dst"
  else
    warn "visudo validation failed; not installing sudoers for $user."
  fi
  rm -f "$tmp"
}

if [[ -n "${TARGET_USER:-}" ]]; then
  add_sudoers "$TARGET_USER"
else
  log "Skipping sudoers (no --sudo-user provided)."
fi

# ------------------- Web UI overrides (bind + token) -------------------
if [[ "$WITH_WEBUI" == "yes" && -f "$SYSTEMD_DIR/$WEBUI_UNIT" ]]; then
  log "Configuring Web UI bind + token override ..."
  WEBUI_OVERRIDE_DIR="/etc/systemd/system/${WEBUI_UNIT}.d"
  WEBUI_OVERRIDE_FILE="${WEBUI_OVERRIDE_DIR}/override.conf"
  run mkdir -p "$WEBUI_OVERRIDE_DIR"
  run bash -c "cat >'$WEBUI_OVERRIDE_FILE' <<EOF
[Service]
Environment=\"WEBUI_HOST=${WEBUI_HOST}\" \"WEBUI_PORT=${WEBUI_PORT}\"
$( [[ -n "$WEBUI_TOKEN" ]] && printf 'Environment="WEBUI_TOKEN=%s"\n' "$WEBUI_TOKEN" )
EOF"
  if [[ "$ENABLE_UNITS" == "yes" ]]; then
    run systemctl daemon-reload
    run systemctl restart "$WEBUI_UNIT" || true
  fi
fi

# ------------------- Default Config Skeletons -------------------
log "Ensuring default config skeletons ..." 
run mkdir -p "$DEST_ROOT/config" "$DEST_ROOT/hooks" "$DEST_ROOT/payloads/www" "/var/log/p4wnp1"

if [[ ! -f "$DEST_ROOT/config/ap.json" ]]; then
  run bash -c "cat >'$DEST_ROOT/config/ap.json' <<'JSON'
{
  \"ssid\": \"P4WNP1\",
  \"psk\": \"p4wnp1o2\",
  \"cidr\": \"10.36.1.1/24\",
  \"chan\": 6,
  \"country\": \"ES\",
  \"hidden\": false
}
JSON"
  ok "Created default Wi‑Fi AP config at config/ap.json"
fi

# ------------------- Post‑install Summary -------------------
echo
ok "Install complete -> ${DEST_ROOT}"
echo "  Web UI: $( [[ "$WITH_WEBUI" == "yes" ]] && echo "${WEBUI_HOST}:${WEBUI_PORT} (unit: ${WEBUI_UNIT})" || echo "disabled" )"
if [[ "$WITH_WEBUI" == "yes" ]]; then
  if [[ -n "$WEBUI_TOKEN" ]]; then
    echo "  Web UI token set -> send header: X-P4WN-Token: ${WEBUI_TOKEN}"
  else
    echo "  Web UI token: not set (open access on bound interface)"
  fi
fi
echo "  OLED: ${WITH_OLED} (auto=yes if panel @0x3C detected)"
echo "  USB core: ${WITH_USB}"
echo "  Portal: ${WITH_PORTAL}"
echo
echo "NOTE: Reboot after first install so dwc2/i2c/spi overlays load:"
echo "      sudo reboot"

