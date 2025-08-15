#!/bin/bash
# /opt/p4wnp1/config/usb_gadgets/hid_storage_net.sh
set -euo pipefail

G=/sys/kernel/config/usb_gadget/p4wnp1

SERIAL=${SERIAL:-"1337"}
MANUF=${MANUF:-"quasialex"}
PRODUCT=${PRODUCT:-"P4wnP1-O2 HID+NET+MSD"}
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

# HID keyboard
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
cat > functions/hid.usb0/report_desc <<'EOF'
\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02
\x95\x01\x75\x08\x81\x01\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03
\x91\x01\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0
EOF

# RNDIS config
mkdir -p configs/c.1/strings/0x409
echo "HID+RNDIS+MSD" > configs/c.1/strings/0x409/configuration
echo 120 > configs/c.1/MaxPower

mkdir -p functions/rndis.usb0
echo "RNDIS"    > functions/rndis.usb0/os_desc/interface.rndis/compatible_id
echo "5162001"  > functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id

ln -s functions/hid.usb0   configs/c.1/ || true
ln -s functions/rndis.usb0 configs/c.1/ || true

# ECM config
mkdir -p configs/c.2/strings/0x409
echo "HID+ECM+MSD" > configs/c.2/strings/0x409/configuration
echo 120 > configs/c.2/MaxPower

mkdir -p functions/ecm.usb0
echo "02:13:37:00:00:01" > functions/ecm.usb0/dev_addr
echo "02:13:37:00:00:02" > functions/ecm.usb0/host_addr

ln -s functions/hid.usb0 configs/c.2/ || true
ln -s functions/ecm.usb0 configs/c.2/ || true

# Mass storage (added to BOTH configs)
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
ln -s functions/mass_storage.usb0 configs/c.2/ || true

# Bind & bring up usb0
UDC=$(ls /sys/class/udc | head -n1)
echo "$UDC" > UDC

if ip link show usb0 &>/dev/null; then
  ip link set usb0 up || true
  ip addr add 10.13.37.1/24 dev usb0 2>/dev/null || true
fi

echo "[p4wnp1] HID+NET+MSD ready (RNDIS cfg#1, ECM cfg#2)"
