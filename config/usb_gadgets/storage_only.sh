#!/bin/bash
# /opt/p4wnp1/config/usb_gadgets/storage_only.sh
set -euo pipefail

G=/sys/kernel/config/usb_gadget/p4wnp1

SERIAL=${SERIAL:-"1337"}
MANUF=${MANUF:-"quasialex"}
PRODUCT=${PRODUCT:-"P4wnP1-O2 MSD"}
ID_VENDOR=${ID_VENDOR:-0x1d6b}
ID_PRODUCT=${ID_PRODUCT:-0x0104}
BCD_DEV=${BCD_DEV:-0x0100}
BCD_USB=${BCD_USB:-0x0200}
BACKING_IMG=${BACKING_IMG:-/opt/p4wnp1/usb_mass_storage.img}

# clean slate
[[ -d "$G" ]] && rm -rf "$G"
mkdir -p "$G"
cd "$G"

echo "$ID_VENDOR"  > idVendor
echo "$ID_PRODUCT" > idProduct
echo "$BCD_DEV"    > bcdDevice
echo "$BCD_USB"    > bcdUSB

mkdir -p strings/0x409
echo "$SERIAL"  > strings/0x409/serialnumber
echo "$MANUF"   > strings/0x409/manufacturer
echo "$PRODUCT" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "Mass Storage" > configs/c.1/strings/0x409/configuration
echo 120 > configs/c.1/MaxPower

mkdir -p functions/mass_storage.usb0
echo 1 > functions/mass_storage.usb0/stall
echo 1 > functions/mass_storage.usb0/removable
echo 0 > functions/mass_storage.usb0/ro

if [[ ! -f "$BACKING_IMG" ]]; then
  echo "[p4wnp1] WARNING: $BACKING_IMG not found; creating 128MB VFAT image..."
  dd if=/dev/zero of="$BACKING_IMG" bs=1M count=128
  mkfs.vfat "$BACKING_IMG"
fi
echo "$BACKING_IMG" > functions/mass_storage.usb0/lun.0/file

ln -s functions/mass_storage.usb0 configs/c.1/ || true

UDC=$(ls /sys/class/udc | head -n1)
echo "$UDC" > UDC

echo "[p4wnp1] Storage-only ready"
