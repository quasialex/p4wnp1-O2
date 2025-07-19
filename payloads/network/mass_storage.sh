#!/bin/bash
# Simulate USB mass storage using a backing file

IMG=/opt/p4wnp1/data/usb.img
SIZE_MB=16
MOUNTPOINT=/mnt/usb

echo "[+] Creating storage image..."
mkdir -p /opt/p4wnp1/data
[ ! -f "$IMG" ] && dd if=/dev/zero of=$IMG bs=1M count=$SIZE_MB && mkdosfs $IMG

echo "[+] Loading mass storage gadget..."
modprobe g_mass_storage file=$IMG stall=0 removable=1
