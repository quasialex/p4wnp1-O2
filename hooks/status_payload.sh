#!/bin/bash
set -euo pipefail
BASE=/opt/p4wnp1
CFG="$BASE/config/active_payload"

if [[ ! -f "$CFG" ]]; then
  echo "Payload: (none)"
  exit 0
fi

P=$(cat "$CFG" | tr -d '\r')
[[ -z "$P" ]] && { echo "Payload: (none)"; exit 0; }

NAME="$(basename "$P")"
NAME="${NAME%.sh}"

# sanity check if file exists
if [[ -f "$P" ]]; then
  echo "Payload: $NAME"
else
  echo "Payload: $NAME (missing file)"
fi
