#!/usr/bin/env bash
set -euo pipefail

G=/sys/kernel/config/usb_gadget/p4wnp1
UDCS=/sys/class/udc
P4WN_HOME=${P4WN_HOME:-/opt/p4wnp1}

modprobe libcomposite || true
modprobe dwc2 || true

mkdir -p "$G"

# Unbind if currently bound
if [[ -w "$G/UDC" ]]; then echo "" > "$G/UDC" || true; fi

# Helper: unlink all function links from config c.1 if present
unlink_all() {
  if [[ -d "$G/configs/c.1" ]]; then
    find "$G/configs/c.1" -maxdepth 1 -type l -print -exec unlink {} \; || true
  fi
}

# Helper: remove function dirs if they exist (only after unlink)
rmdir_if() { [[ -d "$1" ]] && rmdir "$1" 2>/dev/null || true; }

unlink_all

# Remove any old functions we don't want in this mode
rmdir_if "$G/functions/mass_storage.usb0" || true

# Remove and recreate network/HID functions fresh
rmdir_if "$G/functions/rndis.usb0" || true
rmdir_if "$G/functions/ecm.usb0"   || true
rmdir_if "$G/functions/hid.usb0"   || true

# ---- Device descriptors (write, don't delete) ----
echo 0x1d6b > "$G/idVendor"      # Linux Foundation (ok for lab/test)
echo 0x0104 > "$G/idProduct"     # Random product id for composite
echo 0x0200 > "$G/bcdUSB"
echo 0x0100 > "$G/bcdDevice"
# Composite class (IAD) so multiple functions are legal
echo 0xEF > "$G/bDeviceClass"
echo 0x02 > "$G/bDeviceSubClass"
echo 0x01 > "$G/bDeviceProtocol"

mkdir -p "$G/strings/0x409"
echo "P4wnP1-O2"                  > "$G/strings/0x409/manufacturer"
echo "P4wnP1-O2 Composite"        > "$G/strings/0x409/product"
echo "$(cat /proc/sys/kernel/random/uuid)" > "$G/strings/0x409/serialnumber"

mkdir -p "$G/configs/c.1/strings/0x409"
echo "Config 1: HID + NET"        > "$G/configs/c.1/strings/0x409/configuration"
echo 250                          > "$G/configs/c.1/MaxPower"   # 500mA

# ---- HID (keyboard) ----
mkdir -p "$G/functions/hid.usb0"
echo 1 > "$G/functions/hid.usb0/protocol"      # keyboard
echo 1 > "$G/functions/hid.usb0/subclass"      # boot interface
echo 8 > "$G/functions/hid.usb0/report_length"

# Boot keyboard report descriptor
# (printf with hex escapes avoids shell mangling)
printf '\x05\x01\x09\x06\xA1\x01\x05\x07\x19\xE0\x29\xE7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x01\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xC0' \
  > "$G/functions/hid.usb0/report_desc"

# ---- ECM (Linux/Mac) ----
mkdir -p "$G/functions/ecm.usb0"
echo "02:00:00:00:00:01" > "$G/functions/ecm.usb0/dev_addr"
echo "02:00:00:00:00:02" > "$G/functions/ecm.usb0/host_addr"
echo  "usb0"             > "$G/functions/ecm.usb0/ifname"
echo  4                  > "$G/functions/ecm.usb0/qmult"

# ---- RNDIS (Windows) ----
mkdir -p "$G/functions/rndis.usb0"
echo "02:00:00:00:00:03" > "$G/functions/rndis.usb0/dev_addr"
echo "02:00:00:00:00:04" > "$G/functions/rndis.usb0/host_addr"
echo  "rndis0"           > "$G/functions/rndis.usb0/ifname"
echo  4                  > "$G/functions/rndis.usb0/qmult"

# ---- Link functions into config ----
ln -s "$G/functions/hid.usb0"   "$G/configs/c.1/"
ln -s "$G/functions/ecm.usb0"   "$G/configs/c.1/"
ln -s "$G/functions/rndis.usb0" "$G/configs/c.1/"

# ---- Bind to a UDC ----
UDC=$(ls -1 "$UDCS" | head -n1 || true)
if [[ -z "${UDC}" ]]; then
  echo "[!] No UDC present under $UDCS; check dwc2 overlay & reboot." >&2
  exit 3
fi
echo "$UDC" > "$G/UDC"
echo "[+] HID + NET up on UDC: $UDC"
