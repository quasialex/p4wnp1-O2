#!/bin/bash
# Blink LED to signal payload execution

LED="/sys/class/leds/led0/brightness"
count=$1
[ -z "$count" ] && count=3

echo "[+] Blinking LED $count times..."
for i in $(seq 1 $count); do
  echo 1 > $LED
  sleep 0.2
  echo 0 > $LED
  sleep 0.2
done
