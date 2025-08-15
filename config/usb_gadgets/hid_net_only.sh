#!/bin/bash
# /opt/p4wnp1/config/usb_gadgets/hid_net_only.sh
set -euo pipefail

G=/sys/kernel/config/usb_gadget/p4wnp1

SERIAL=${SERIAL:-"1337"}
MANUF=${MANUF:-"quasialex"}
PRODUCT=${PRODUCT:-"P4wnP1-O2 HID+NET"}
ID_VENDOR=${ID_VENDOR:-0x1d6b}   # Linux Foundation (safe default for testing)
ID_PRODUCT=${ID_PRODUCT:-0x0104}
BCD_DEV=${BCD_DEV:-0x0100}
BCD_USB=${BCD_USB:-0x0200}

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

# HID keyboard (boot)
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
cat > functions/hid.usb0/report_desc <<'EOF'
\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02
\x95\x01\x75\x08\x81\x01\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03
\x91\x01\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0
EOF

# Config 1: RNDIS (Windows)
mkdir -p configs/c.1/strings/0x409
echo "HID + RNDIS" > configs/c.1/strings/0x409/configuration
echo 120 > configs/c.1/MaxPower

mkdir -p functions/rndis.usb0
echo "RNDIS"    > functions/rndis.usb0/os_desc/interface.rndis/compatible_id
echo "5162001"  > functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id

ln -s functions/hid.usb0   configs/c.1/ || true
ln -s functions/rndis.usb0 configs/c.1/ || true

# Config 2: ECM (macOS/Linux)
mkdir -p configs/c.2/strings/0x409
echo "HID + ECM" > configs/c.2/strings/0x409/configuration
echo 120 > configs/c.2/MaxPower

mkdir -p functions/ecm.usb0
# deterministic locally-administered MACs
echo "02:13:37:00:00:01" > functions/ecm.usb0/dev_addr
echo "02:13:37:00:00:02" > functions/ecm.usb0/host_addr

ln -s functions/hid.usb0 configs/c.2/ || true
ln -s functions/ecm.usb0 configs/c.2/ || true

# Bind to first available UDC
UDC=$(ls /sys/class/udc | head -n1)
echo "$UDC" > UDC

# Bring up usb0 with static IP
if ip link show usb0 &>/dev/null; then
  ip link set usb0 up || true
  ip addr add 10.13.37.1/24 dev usb0 2>/dev/null || true
fi

echo "[p4wnp1] HID+NET ready (RNDIS cfg#1, ECM cfg#2)"
