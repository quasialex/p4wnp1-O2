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
for f in mass_storage.usb0 rndis.usb0 ecm.usb0 hid.usb0; do
  rmdir_if "$G/functions/$f" || true
done

# Descriptors / strings
echo 0x1d6b > "$G/idVendor"
echo 0x0104 > "$G/idProduct"
echo 0x0200 > "$G/bcdUSB"
echo 0x0100 > "$G/bcdDevice"
echo 0xEF   > "$G/bDeviceClass"
echo 0x02   > "$G/bDeviceSubClass"
echo 0x01   > "$G/bDeviceProtocol"

mkdir -p "$G/strings/0x409"
echo "P4wnP1-O2"                           > "$G/strings/0x409/manufacturer"
echo "P4wnP1-O2 HID+NET+MSD"               > "$G/strings/0x409/product"
echo "$(cat /proc/sys/kernel/random/uuid)" > "$G/strings/0x409/serialnumber"

mkdir -p "$G/configs/c.1/strings/0x409"
echo "Config 1: HID + NET + MSD"           > "$G/configs/c.1/strings/0x409/configuration"
echo 250                                    > "$G/configs/c.1/MaxPower"

# HID
mkdir -p "$G/functions/hid.usb0"
echo 1 > "$G/functions/hid.usb0/protocol"
echo 1 > "$G/functions/hid.usb0/subclass"
echo 8 > "$G/functions/hid.usb0/report_length"
printf '\x05\x01\x09\x06\xA1\x01\x05\x07\x19\xE0\x29\xE7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x01\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xC0' \
  > "$G/functions/hid.usb0/report_desc"

# ECM
mkdir -p "$G/functions/ecm.usb0"
echo "02:00:00:00:00:01" > "$G/functions/ecm.usb0/dev_addr"
echo "02:00:00:00:00:02" > "$G/functions/ecm.usb0/host_addr"
echo  "usb0"             > "$G/functions/ecm.usb0/ifname"
echo  4                  > "$G/functions/ecm.usb0/qmult"

# RNDIS
mkdir -p "$G/functions/rndis.usb0"
echo "02:00:00:00:00:03" > "$G/functions/rndis.usb0/dev_addr"
echo "02:00:00:00:00:04" > "$G/functions/rndis.usb0/host_addr"
echo  "rndis0"           > "$G/functions/rndis.usb0/ifname"
echo  4                  > "$G/functions/rndis.usb0/qmult"

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

# Link all
ln -s "$G/functions/hid.usb0"            "$G/configs/c.1/"
ln -s "$G/functions/ecm.usb0"            "$G/configs/c.1/"
ln -s "$G/functions/rndis.usb0"          "$G/configs/c.1/"
ln -s "$G/functions/mass_storage.usb0"   "$G/configs/c.1/"

UDC=$(ls -1 "$UDCS" | head -n1 || true)
[[ -z "$UDC" ]] && { echo "[!] No UDC present."; exit 3; }
echo "$UDC" > "$G/UDC"
echo "[+] HID + NET + MSD up on UDC: $UDC"
