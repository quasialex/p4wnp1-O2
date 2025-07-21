#!/bin/bash
set -euo pipefail

# Base directory for all payloads (override with env‑var if you like)
P4WN_HOME="${P4WN_HOME:-/opt/p4wnp1}"
PAYLOAD_DIR="$P4WN_HOME/payloads"

usage() {
  echo "Usage: $(basename "$0") [payload]"
  echo "If no payload is given, an interactive menu is shown."
}

list_payloads() {
  find "$PAYLOAD_DIR" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' | sort
}

run_payload() {
  local name="$1"
  local script="$PAYLOAD_DIR/$name/run.sh"
  if [[ ! -x "$script" ]]; then
    echo "Payload '$name' not found or not executable" >&2
    exit 1
  fi
  echo "[+] Launching payload: $name"
  exec "$script"
}

# ── argument / help handling ────────────────────────────────────────────
if [[ ${1:-} =~ ^(-h|--help)$ ]]; then
  usage; exit 0
fi

if [[ $# -eq 1 ]]; then
  run_payload "$1"
  exit 0
fi

# ── interactive menu ───────────────────────────────────────────────────
PS3=$'Select payload > '
select PAYLOAD in $(list_payloads); do
  [[ -n "${PAYLOAD:-}" ]] && break
  echo "Invalid selection" >&2
done
run_payload "$PAYLOAD"
