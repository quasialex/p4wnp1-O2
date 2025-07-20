#!/bin/bash

echo "=== [ Step 1: Purging GUI packages ] ==="
sudo apt purge -y kali-desktop-xfce lightdm xfce4* \
  xserver-xorg* x11-common x11-utils x11-xserver-utils \
  gtk* gnome-icon-theme

echo "=== [ Step 2: Removing leftover GUI tools ] ==="
sudo apt purge -y orage parole mousepad thunar* xfconf* \
  gvfs* gnome* xdg-user-dirs* policykit* gksu

echo "=== [ Step 3: Autoremove and clean ] ==="
sudo apt autoremove --purge -y
sudo apt clean

echo "=== [ Step 4: Installing terminal essentials ] ==="
sudo apt update && sudo apt install -y \
  git python3-pip screen tmux build-essential \
  libfreetype-dev libjpeg-dev python3-smbus \
  bettercap mitmproxy responder pipx rustc cargo

echo "=== [ Step 5: Ensuring pipx path ] ==="
pipx ensurepath

echo "=== [ Step 6: Installing impacket from Kali repo ] ==="
sudo apt install -y python3-impacket

# Symlink all Impacket CLI tools to /usr/local/bin
sudo find /usr/share/doc/python3-impacket/examples/ -type f -name "*.py" | while read file; do
  binname=$(basename "$file")
  sudo ln -sf "$file" "/usr/local/bin/$binname"
done

echo "=== [ Step 7: Installing OLED library via pip ] ==="
pip3 install luma.oled --break-system-packages

echo "=== [ Step 8: Set to CLI-only boot ] ==="
sudo systemctl set-default multi-user.target

echo "=== [ DONE ] ==="
echo "You can now reboot into a clean, headless Kali system."
