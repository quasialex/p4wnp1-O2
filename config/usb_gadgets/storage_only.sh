#!/usr/bin/env bash
set -euo pipefail

G=/sys/kernel/config/usb_gadget/p4wnp1
UDCS=/sys/class/udc
P4WN_HOME=${P4WN_HOME:-/opt/p4wnp1}
MS_IMG="${P4WN_HOME}/usb_mass_storage.img"

modprobe libcomposite || true
modprobe dwc2 || true

mkdir -p "$G"
[[ -w "$G/UDC" ]] && echo "" > "$G/UDC" || true

unlink_all() {
  if [[ -d "$G/configs/c.1" ]]; then
    find "$G/configs/c.1" -maxdepth 1 -type l -print -exec unlink {} \; || true
  fi
}
rmdir_if() { [[ -d "$1" ]] && rmdir "$1" 2>/dev/null || true; }

unlink_all
for f in hid.usb0 ecm.usb0 rndis.usb0; do
  rmdir_if "$G/functions/$f" || true
done
rmdir_if "$G/functions/mass_storage.usb0" || true

# Descriptors / strings
echo 0x1d6b > "$G/idVendor"
echo 0x0104 > "$G/idProduct"
echo 0x0200 > "$G/bcdUSB"
echo 0x0100 > "$G/bcdDevice"
echo 0x00   > "$G/bDeviceClass"
echo 0x00   > "$G/bDeviceSubClass"
echo 0x00   > "$G/bDeviceProtocol"

mkdir -p "$G/strings/0x409"
echo "P4wnP1-O2"                           > "$G/strings/0x409/manufacturer"
echo "P4wnP1-O2 Mass Storage"              > "$G/strings/0x409/product"
echo "$(cat /proc/sys/kernel/random/uuid)" > "$G/strings/0x409/serialnumber"

mkdir -p "$G/configs/c.1/strings/0x409"
echo "Config 1: Mass Storage"              > "$G/configs/c.1/strings/0x409/configuration"
echo 250                                    > "$G/configs/c.1/MaxPower"

# Mass Storage
if [[ ! -f "$MS_IMG" ]]; then
  echo "[*] Creating 128MB VFAT image at $MS_IMG ..."
  dd if=/dev/zero of="$MS_IMG" bs=1M count=128
  mkfs.vfat "$MS_IMG"
fi
mkdir -p "$G/functions/mass_storage.usb0"
echo 1           > "$G/functions/mass_storage.usb0/stall"
echo 0           > "$G/functions/mass_storage.usb0/ro"
echo 1           > "$G/functions/mass_storage.usb0/removable"
echo "$MS_IMG"   > "$G/functions/mass_storage.usb0/lun.0/file"

ln -s "$G/functions/mass_storage.usb0" "$G/configs/c.1/"

UDC=$(ls -1 "$UDCS" | head -n1 || true)
[[ -z "$UDC" ]] && { echo "[!] No UDC present."; exit 3; }
echo "$UDC" > "$G/UDC"
echo "[+] MSD up on UDC: $UDC"
