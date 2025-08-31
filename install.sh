#!/bin/bash
set -euo pipefail

# ===================================
# P4wnP1-O2 Install Script (modular)
# ===================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_ROOT="/opt/p4wnp1"
SYSTEMD_DIR="/etc/systemd/system"
APACHE_SITES="/etc/apache2/sites-available"
APACHE_ENABLED="/etc/apache2/sites-enabled"

need_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "[!] Run as root." >&2
    exit 2
  fi
}

pkg_install() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y || true
  apt-get install -y --no-install-recommends \
    python3 python3-venv python3-yaml \
    git curl jq tmux \
    iw iproute2 wireless-tools \
    dnsmasq hostapd \
    nftables iptables-nft \
    apache2 apache2-bin \
    openssl
}

sync_repo() {
  mkdir -p "$DEST_ROOT"
  rsync -a --delete \
    --exclude ".git" \
    --exclude ".github" \
    "$REPO_DIR"/ "$DEST_ROOT"/
}

install_units() {
  # Only the consolidated services you actually use
  for unit in p4wnp1.service p4wnp1-wifiap.service oledmenu.service; do
    if [[ -f "$DEST_ROOT/systemd/$unit" ]]; then
      install -m 0644 "$DEST_ROOT/systemd/$unit" "$SYSTEMD_DIR/$unit"
    fi
  done
  systemctl daemon-reload
  systemctl enable p4wnp1.service || true
  # Wi-Fi AP service is installed and enabled; it won’t bring up AP unless invoked by p4wnctl
  systemctl enable p4wnp1-wifiap.service || true
  # OLED is optional; enable if present
  if [[ -f "$SYSTEMD_DIR/oledmenu.service" ]]; then
    systemctl enable oledmenu.service || true
  fi
}

apache_portal_setup() {
  # Enable useful modules
  a2enmod rewrite headers cgi || true

  # Place (or update) the vhost from services/portal/conf/
  if [[ -f "$DEST_ROOT/services/portal/conf/p4wnp1-portal.conf" ]]; then
    install -m 0644 "$DEST_ROOT/services/portal/conf/p4wnp1-portal.conf" \
      "$APACHE_SITES/p4wnp1-portal.conf"
    # Disable default site to avoid clashes on :80
    a2dissite 000-default || true
    a2ensite p4wnp1-portal || true
  fi

  # Web root & log dir the portal expects
  mkdir -p /var/log/p4wnp1
  chown root:adm /var/log/p4wnp1 || true

  systemctl restart apache2 || true
}

udev_rules() {
  # Make HID gadget nodes convenient (optional; you also have `usb fixperms`)
  cat >/etc/udev/rules.d/99-p4wnp1.rules <<'EOF'
SUBSYSTEM=="hidg", MODE="0666"
KERNEL=="hidg*", MODE="0666"
EOF
  udevadm control --reload-rules || true
}

config_skeleton() {
  mkdir -p "$DEST_ROOT/config" "$DEST_ROOT/hooks" "$DEST_ROOT/payloads/www"
  # Default AP settings if missing
  if [[ ! -f "$DEST_ROOT/config/ap.json" ]]; then
    cat >"$DEST_ROOT/config/ap.json" <<'JSON'
{
  "ssid": "P4WNP1",
  "psk": "p4wnp1o2",
  "cidr": "10.36.1.1/24",
  "chan": 6,
  "country": "ES",
  "hidden": false
}
JSON
  fi
}

post_notes() {
  echo
  echo "[+] Installed to $DEST_ROOT"
  echo "[+] Units:"
  systemctl is-enabled p4wnp1.service || true
  systemctl is-enabled p4wnp1-wifiap.service || true
  [[ -f "$SYSTEMD_DIR/oledmenu.service" ]] && systemctl is-enabled oledmenu.service || true
  echo
  echo "Useful commands:"
  echo "  $DEST_ROOT/p4wnctl.py web status"
  echo "  $DEST_ROOT/p4wnctl.py wifi status"
  echo "  $DEST_ROOT/p4wnctl.py payload web status"
  echo
  echo "Captive portal:"
  echo "  $DEST_ROOT/p4wnctl.py wifi portal start|stop|status"
}

main() {
  need_root
  pkg_install
  sync_repo
  install_units
  apache_portal_setup
  udev_rules
  config_skeleton
  systemctl restart p4wnp1.service || true
  post_notes
}
main "$@"
