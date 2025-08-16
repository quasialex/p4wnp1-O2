# /opt/p4wnp1/hooks/gadget_reset.sh
#!/bin/bash
set -euo pipefail

G=/sys/kernel/config/usb_gadget/p4wnp1

# Nothing to do if gadget doesn't exist
[[ -d "$G" ]] || exit 0

# 1) Unbind if currently bound
if [[ -f "$G/UDC" ]]; then
  CUR="$(cat "$G/UDC" 2>/dev/null || true)"
  [[ -n "${CUR:-}" ]] && echo "" > "$G/UDC" || true
fi

# 2) Disable os_desc and webusb if present
[[ -d "$G/os_desc" ]] && echo 0 > "$G/os_desc/use" 2>/dev/null || true
[[ -d "$G/webusb"  ]] && echo 0 > "$G/webusb/use"  2>/dev/null || true

# 3) Unlink functions from configs
for c in "$G"/configs/*; do
  [[ -d "$c" ]] || continue
  find "$c" -maxdepth 1 -type l -exec rm -f {} +
done

# 4) Remove functions (detach MSD backing file first)
if [[ -d "$G/functions" ]]; then
  for f in "$G"/functions/mass_storage.*; do
    [[ -e "$f" ]] || continue
    [[ -f "$f/lun.0/file" ]] && echo "" > "$f/lun.0/file" 2>/dev/null || true
    rmdir "$f" 2>/dev/null || rm -rf "$f"
  done
  for f in "$G"/functions/*; do
    [[ -e "$f" ]] || continue
    rmdir "$f" 2>/dev/null || rm -rf "$f"
  done
fi

# 5) Remove configs/strings and gadget dir
rm -rf "$G/configs" "$G/strings" "$G/os_desc" "$G/webusb" 2>/dev/null || true
rmdir "$G" 2>/dev/null || rm -rf "$G"
echo "[p4wnp1] gadget reset complete"
