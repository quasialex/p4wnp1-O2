#!/bin/bash
# Inject keystrokes using HID function

HID_DEV="/dev/hidg0"

function usage() {
  echo "Usage: $0 [inject|type] <text>"
  exit 1
}

if [[ "$#" -lt 2 ]]; then
  usage
fi

MODE="$1"
shift
TEXT="$*"

function send_enter() {
  printf '\x00\x00\x28\x00\x00\x00\x00\x00' > "$HID_DEV"
  sleep 0.1
  printf '\x00\x00\x00\x00\x00\x00\x00\x00' > "$HID_DEV"
}

function type_text() {
  for (( i=0; i<${#TEXT}; i++ )); do
    char="${TEXT:$i:1}"
    /opt/p4wnp1/tools/usbhid-keys/sendchar "$char"
    sleep 0.05
  done
}

case "$MODE" in
  inject)
    case "$TEXT" in
      ENTER) send_enter ;;
      *)
        echo "[!] Unsupported inject key: $TEXT"
        ;;
    esac
    ;;
  type)
    type_text
    ;;
  *)
    usage
    ;;
esac
