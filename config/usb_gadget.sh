#!/bin/bash
set -euo pipefail

# === Config ===
GADGET_NAME="p4wnp1"
GADGET_DIR="/sys/kernel/config/usb_gadget/$GADGET_NAME"
SERIAL="1337"
MANUFACTURER="SnowSecOps"
PRODUCT="P4wnP1-Zero2W"
HOST_MAC="42:42:42:42:42:42"
SELF_MAC="de:ad:be:ef:00:00"
UDC_DEVICE=$(ls /sys/class/udc | head -n 1)

echo "[*] Setting up USB Gadget..."

# === Cleanup if already exists ===
if [ -d "$GADGET_DIR" ]; then
  echo "[*] Removing existing gadget..."
  echo "" > "$GADGET_DIR/UDC" || true
  rm -rf "$GADGET_DIR/configs/c.1/"* "$GADGET_DIR/functions/"* || true
  rmdir "$GADGET_DIR" || true
  sleep 0.5
fi

mkdir -p "$GADGET_DIR"
cd "$GADGET_DIR"

echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "$SERIAL" > strings/0x409/serialnumber
echo "$MANUFACTURER" > strings/0x409/manufacturer
echo "$PRODUCT" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "Config 1: ECM + HID" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

# === ECM (USB Network) ===
mkdir -p functions/ecm.usb0
echo "$HOST_MAC" > functions/ecm.usb0/host_addr
echo "$SELF_MAC" > functions/ecm.usb0/dev_addr
ln -s functions/ecm.usb0 configs/c.1/

# === HID Keyboard ===
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
echo -ne '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x01\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x01\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' > functions/hid.usb0/report_desc
ln -s functions/hid.usb0 configs/c.1/

# === Bind to UDC ===
echo "$UDC_DEVICE" > UDC

echo "[+] USB Gadget setup complete"
