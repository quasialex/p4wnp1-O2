#!/bin/bash
# Select and load a USB gadget mode: HID+Storage+RNDIS, HID+RNDIS, or Storage Only

GADGET_CONFIG_DIR="/opt/p4wnp1/config/usb_gadgets"

echo "[*] Available USB gadget modes:"
echo "1) HID + Storage + RNDIS"
echo "2) HID + RNDIS"
echo "3) Storage Only"
echo -n "Select gadget mode [1-3]: "
read MODE

case "$MODE" in
  1)
    echo "[+] Loading HID + Storage + RNDIS..."
    sudo bash "$GADGET_CONFIG_DIR/hid_storage_net.sh"
    ;;
  2)
    echo "[+] Loading HID + RNDIS..."
    sudo bash "$GADGET_CONFIG_DIR/hid_net_only.sh"
    ;;
  3)
    echo "[+] Loading Storage Only..."
    sudo bash "$GADGET_CONFIG_DIR/storage_only.sh"
    ;;
  *)
    echo "[!] Invalid selection."
    exit 1
    ;;
esac

echo "[✓] Gadget configuration applied."
