#!/bin/bash
# Safely tear down ANY existing gadget at /sys/kernel/config/usb_gadget/p4wnp1
set -euo pipefail

G=/sys/kernel/config/usb_gadget/p4wnp1

[[ -d "$G" ]] || exit 0

# 1) Unbind if currently bound
if [[ -f "$G/UDC" ]]; then
  CUR=$(cat "$G/UDC" || true)
  if [[ -n "${CUR:-}" ]]; then
    echo "" > "$G/UDC" || true
  fi
fi

# 2) Disable os_desc and webusb if present (must set use=0 before removing)
if [[ -d "$G/os_desc" ]]; then
  echo 0 > "$G/os_desc/use" 2>/dev/null || true
fi
if [[ -d "$G/webusb" ]]; then
  echo 0 > "$G/webusb/use" 2>/dev/null || true
fi

# 3) Unlink all function symlinks from each config
for c in "$G"/configs/*; do
  [[ -d "$c" ]] || continue
  find "$c" -maxdepth 1 -type l -exec rm -f {} +
done

# 4) Remove function instances
if [[ -d "$G/functions" ]]; then
  # Remove mass_storage first (it can hold an open file)
  for f in "$G"/functions/mass_storage.*; do
    [[ -e "$f" ]] || continue
    # best effort to detach backing file
    lun="$f"/lun.0/file
    [[ -f "$lun" ]] && echo "" > "$lun" 2>/dev/null || true
    rmdir "$f" 2>/dev/null || rm -rf "$f"
  done
  # Remove the rest (rndis, ecm, hid, etc.)
  for f in "$G"/functions/*; do
    [[ -e "$f" ]] || continue
    rmdir "$f" 2>/dev/null || rm -rf "$f"
  done
fi

# 5) Remove configs (strings then dirs)
for c in "$G"/configs/*; do
  [[ -d "$c" ]] || continue
  rm -rf "$c"/strings 2>/dev/null || true
  rmdir "$c" 2>/dev/null || rm -rf "$c"
done

# 6) Remove strings and top-level files, then gadget dir
rm -rf "$G/strings" "$G/os_desc" "$G/webusb" 2>/dev/null || true
rmdir "$G" 2>/dev/null || rm -rf "$G"
