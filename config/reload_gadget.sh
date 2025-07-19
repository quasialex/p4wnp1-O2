#!/bin/bash
# Reload USB gadget from template

GADGET_DIR=/sys/kernel/config/usb_gadget/p4wnp1

echo "[+] Unloading USB gadget..."
if [ -e "$GADGET_DIR" ]; then
  cd $GADGET_DIR
  echo "" > UDC
  sleep 0.5
  rm -rf configs/c.1/* functions/*
  cd /sys/kernel/config/usb_gadget
  rmdir p4wnp1
fi

TEMPLATE=$1
if [ -z "$TEMPLATE" ]; then
  TEMPLATE="usb_ecm_hid.sh"
fi

echo "[+] Loading gadget template: $TEMPLATE"
bash "/opt/p4wnp1/config/gadgets/$TEMPLATE"
