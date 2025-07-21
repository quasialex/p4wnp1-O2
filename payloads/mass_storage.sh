#!/bin/bash
set -euo pipefail

P4WN_HOME="${P4WN_HOME:-/opt/p4wnp1}"
IMAGE="${1:-$P4WN_HOME/images/msd.img}"

[[ -f "$IMAGE" ]] || { echo "Mass‑storage image '$IMAGE' not found" >&2; exit 1; }

echo "[+] Mounting $IMAGE as USB Mass‑Storage gadget …"
modprobe g_mass_storage file="$IMAGE" stall=0 removable=1 ro=0
