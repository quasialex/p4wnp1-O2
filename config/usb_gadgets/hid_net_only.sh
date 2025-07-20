#!/bin/bash
# USB Gadget: HID Keyboard + RNDIS Network only

set -e

GADGET_DIR="/sys/kernel/config/usb_gadget/p4wnp1"

modprobe libcomposite
mkdir -p "$GADGET_DIR"
cd "$GADGET_DIR"

echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "0002" > strings/0x409/serialnumber
echo "P4wnP1" > strings/0x409/manufacturer
echo "Zero2W Net+HID" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "Config 1: HID+RNDIS" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

# HID
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
echo -ne \\x05\\x01\\x09\\x06\\xA1\\x01\\x05\\x07\\x19\\xE0\\x29\\xE7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x01\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x01\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xC0 > functions/hid.usb0/report_desc
ln -s functions/hid.usb0 configs/c.1/

# RNDIS
mkdir -p functions/rndis.usb0
ln -s functions/rndis.usb0 configs/c.1/

ls /sys/class/udc > UDC
echo "[+] HID + RNDIS gadget loaded"
