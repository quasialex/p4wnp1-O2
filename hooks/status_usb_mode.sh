#!/bin/bash
set -euo pipefail
G=/sys/kernel/config/usb_gadget/p4wnp1

if [[ ! -d "$G" ]]; then
  echo "USB mode: (none)"
  exit 0
fi

# detect which functions exist
HID=0; RNDIS=0; ECM=0; MSD=0
[[ -d "$G/functions" ]] || { echo "USB mode: (none)"; exit 0; }
[[ -d "$G/functions/hid.usb0" ]] && HID=1
[[ -d "$G/functions/rndis.usb0" ]] && RNDIS=1
[[ -d "$G/functions/ecm.usb0" ]] && ECM=1
[[ -d "$G/functions/mass_storage.usb0" ]] && MSD=1

MODE="unknown"
if (( MSD==1 )) && (( HID==1 )) && (( RNDIS==1 || ECM==1 )); then
  MODE="hid_storage_net"
elif (( HID==1 )) && (( RNDIS==1 || ECM==1 )); then
  MODE="hid_net_only"
elif (( MSD==1 )) && (( HID==0 )) && (( RNDIS==0 )) && (( ECM==0 )); then
  MODE="storage_only"
elif (( HID==0 && RNDIS==0 && ECM==0 && MSD==0 )); then
  MODE="(empty gadget)"
fi

# show which configs exist
CFG1_FUNCS=""
CFG2_FUNCS=""
if [[ -d "$G/configs/c.1" ]]; then
  CFG1_FUNCS=$(ls -1 "$G/configs/c.1" 2>/dev/null | grep -E 'hid\.usb0|rndis\.usb0|ecm\.usb0|mass_storage\.usb0' | paste -sd+ - || true)
fi
if [[ -d "$G/configs/c.2" ]]; then
  CFG2_FUNCS=$(ls -1 "$G/configs/c.2" 2>/dev/null | grep -E 'hid\.usb0|rndis\.usb0|ecm\.usb0|mass_storage\.usb0' | paste -sd+ - || true)
fi

# shorten outputs
[[ -z "$CFG1_FUNCS" ]] && CFG1_FUNCS="n/a"
[[ -z "$CFG2_FUNCS" ]] && CFG2_FUNCS="n/a"

echo "USB mode: $MODE
cfg1: $CFG1_FUNCS
cfg2: $CFG2_FUNCS"
