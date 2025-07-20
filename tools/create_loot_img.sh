#!/bin/bash
# Create a mountable loot.img file

IMG_PATH="/opt/p4wnp1/tools/loot.img"
MOUNT_DIR="/mnt/loot_img"
SIZE_MB=64

echo "[*] Creating ${SIZE_MB}MB FAT32 image at $IMG_PATH..."
dd if=/dev/zero of="$IMG_PATH" bs=1M count=$SIZE_MB
mkfs.vfat "$IMG_PATH"

mkdir -p "$MOUNT_DIR"
mount -o loop "$IMG_PATH" "$MOUNT_DIR"

echo "[+] loot.img created and mounted at $MOUNT_DIR"
echo "→ You can copy phishing pages or output files here."
