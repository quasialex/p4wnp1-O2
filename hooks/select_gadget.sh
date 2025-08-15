# /opt/p4wnp1/hooks/select_gadget.sh
#!/bin/bash
set -euo pipefail

# ---- Config ----
BASE=/opt/p4wnp1
GADGET=/sys/kernel/config/usb_gadget/p4wnp1

usage(){ echo "Usage: $0 {hid_net_only|hid_storage_net|storage_only}"; exit 1; }
[[ $# -eq 1 ]] || usage
MODE="$1"

case "$MODE" in
  hid_net_only)     SCRIPT="$BASE/config/usb_gadgets/hid_net_only.sh" ;;
  hid_storage_net)  SCRIPT="$BASE/config/usb_gadgets/hid_storage_net.sh" ;;
  storage_only)     SCRIPT="$BASE/config/usb_gadgets/storage_only.sh" ;;
  *) usage ;;
esac

# ---- Root check (OLED calls through sudo; still, be explicit) ----
if [[ $EUID -ne 0 ]]; then
  echo "This must run as root (sudo)." >&2
  exit 2
fi

# ---- Kernel modules & configfs mount ----
# Ensure configfs is mounted
if ! mount | grep -q "on /sys/kernel/config type configfs"; then
  modprobe configfs 2>/dev/null || true
  mount -t configfs none /sys/kernel/config || true
fi

# USB device controller (dwc2) & libcomposite for gadgets
modprobe dwc2 2>/dev/null || true
modprobe libcomposite 2>/dev/null || true

# Sanity check: do we have a UDC?
if [[ ! -d /sys/class/udc ]] || [[ -z "$(ls -1 /sys/class/udc 2>/dev/null)" ]]; then
  cat >&2 <<'EOF'
[!] No USB Device Controller detected under /sys/class/udc.
    Make sure the Pi has dwc2 enabled. Add to /boot/config.txt:
      dtoverlay=dwc2
    Then reboot.
EOF
  exit 3
fi

# ---- Clean any previous gadget safely ----
"$BASE/hooks/gadget_reset.sh" || true

# ---- Verify target script exists & is executable ----
if [[ ! -x "$SCRIPT" ]]; then
  echo "ERROR: gadget script missing or not executable: $SCRIPT" >&2
  exit 4
fi

# ---- Run selected gadget script ----
exec "$SCRIPT"
