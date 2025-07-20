#!/bin/bash
# USB Gadget: Mass Storage only (e.g., for exfil via loot.img)

set -e

GADGET_DIR="/sys/kernel/config/usb_gadget/p4wnp1"
STORAGE_IMG="/opt/p4wnp1/tools/loot.img"

modprobe libcomposite
mkdir -p "$GADGET_DIR"
cd "$GADGET_DIR"

echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "0003" > strings/0x409/serialnumber
echo "P4wnP1" > strings/0x409/manufacturer
echo "Zero2W Mass Storage" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "Config 1: Mass Storage only" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

# Mass Storage
mkdir -p functions/mass_storage.usb0
echo 1 > functions/mass_storage.usb0/stall
echo "$STORAGE_IMG" > functions/mass_storage.usb0/lun.0/file
ln -s functions/mass_storage.usb0 configs/c.1/

ls /sys/class/udc > UDC
echo "[+] Mass Storage gadget loaded"
