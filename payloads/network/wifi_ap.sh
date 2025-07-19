#!/bin/bash
# Starts a Wi-Fi Access Point using hostapd and dnsmasq

SSID="P4wnP1_AP"
IFACE="wlan0"

cat << EOC > /tmp/hostapd.conf
interface=$IFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=6
wmm_enabled=0
auth_algs=1
ignore_broadcast_ssid=0
EOC

cat << EOD > /tmp/dnsmasq-ap.conf
interface=$IFACE
dhcp-range=192.168.4.10,192.168.4.100,255.255.255.0,12h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
EOD

ip link set $IFACE down
ip addr flush dev $IFACE
ip addr add 192.168.4.1/24 dev $IFACE
ip link set $IFACE up

pkill dnsmasq
pkill hostapd
sleep 1

hostapd /tmp/hostapd.conf &
dnsmasq -C /tmp/dnsmasq-ap.conf -d
