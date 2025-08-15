# /opt/p4wnp1/hooks/select_gadget.sh
#!/bin/bash
set -euo pipefail

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

# Ensure prerequisites
modprobe libcomposite 2>/dev/null || true
if ! lsmod | grep -q dwc2; then
  # dwc2 is usually loaded via dtoverlay at boot, but try now:
  modprobe dwc2 2>/dev/null || true
fi

# If an old gadget exists, tear it down cleanly
if [[ -d "$GADGET" ]]; then
  "$BASE/hooks/gadget_reset.sh"
fi

# Run the selected mode script
exec "$SCRIPT"
