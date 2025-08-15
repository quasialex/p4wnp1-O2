#!/bin/bash
# /opt/p4wnp1/config/usb_gadgets/storage_only.sh
set -euo pipefail

G=/sys/kernel/config/usb_gadget/p4wnp1
SERIAL=${SERIAL:-"1337"}
MANUF=${MANUF:-"quasialex"}
PRODUCT=${PRODUCT:-"P4wnP1-O2 MSD"}
ID_VENDOR=${ID_VENDOR:-0x1d6b}
ID_PRODUCT=${ID_PRODUCT:-0x0104}
BACKING_IMG=${BACKING_IMG:-/opt/p4wnp1/usb_mass_storage.img}

unbind_if_bound() { [[ -d "$G" && -f "$G/UDC" ]] && echo "" > "$G/UDC" || true; }
reset_tree() { [[ -d "$G" ]] && rm -rf "$G"; mkdir -p "$G"; }

main() {
  modprobe libcomposite
  unbind_if_bound
  reset_tree

  cd "$G"
  echo "$ID_VENDOR"  > idVendor
  echo "$ID_PRODUCT" > idProduct
  echo 0x0100       > bcdDevice
  echo 0x0200       > bcdUSB

  mkdir -p strings/0x409
  echo "$SERIAL"  > strings/0x409/serialnumber
  echo "$MANUF"   > strings/0x409/manufacturer
  echo "$PRODUCT" > strings/0x409/product

  mkdir -p configs/c.1/strings/0x409
  echo "Mass Storage" > configs/c.1/strings/0x409/configuration
  echo 120 > configs/c.1/MaxPower

  if [[ ! -f "$BACKING_IMG" ]]; then
    echo "[p4wnp1] WARNING: $BACKING_IMG missing."
    echo "Create it: sudo dd if=/dev/zero of=$BACKING_IMG bs=1M count=128 && sudo mkfs.vfat $BACKING_IMG"
  fi

  mkdir -p functions/mass_storage.usb0
  echo 1 > functions/mass_storage.usb0/stall
  echo 1 > functions/mass_storage.usb0/removable
  echo 0 > functions/mass_storage.usb0/ro
  echo "$BACKING_IMG" > functions/mass_storage.usb0/lun.0/file

  ln -s functions/mass_storage.usb0 configs/c.1/ || true

  local UDC=$(ls /sys/class/udc | head -n1)
  echo "$UDC" > UDC
  echo "[p4wnp1] Storage-only ready"
}
main
