#!/usr/bin/env bash
set -euo pipefail

# Headless conversion for Kali: remove XFCE + LightDM + Xorg and boot to CLI
# Tested on ARM builds (Raspberry Pi).

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
APT="apt-get -y --allow-remove-essential -o Dpkg::Options::=--force-confnew -o Dpkg::Options::=--force-confdef"

echo "=== [ Prep: refresh package lists ] ==="
apt-get update

echo "=== [ Step 1: Purge desktop metas, DM, and Xorg ] ==="
# Desktop meta packages
$APT purge \
  kali-desktop-xfce \
  kali-desktop-core \
  kali-system-gui || true

# Display manager / XFCE
$APT purge \
  lightdm* \
  xfce4*  \
  xserver-xorg* \
  x11-* \
  gtk* \
  gnome-icon-theme orage thunar* xfconf* \
  gvfs* gnome* xdg-user-dirs* policykit* gksu || true

# File manager + default GUI apps
$APT purge \
  thunar \
  thunar-archive-plugin \
  thunar-volman \
  ristretto \
  parole \
  mousepad || true


echo "=== [ Step 2: Autoremove and clean ] ==="
$APT autoremove --purge || true
apt-get clean

echo "=== [ Step 3: Boot to CLI (no graphical.target) ] ==="
systemctl set-default multi-user.target

echo "=== [ Step 4: Terminal essentials & System upgrade ] ==="
apt install -y \
  git python3-pip python3-mitmproxy-rs screen tmux build-essential \
  libfreetype-dev libjpeg-dev python3-smbus \
  bettercap responder rustc cargo

apt-get -y upgrade

echo "=== [ DONE ] ==="
echo "Rebooting ..."

reboot
