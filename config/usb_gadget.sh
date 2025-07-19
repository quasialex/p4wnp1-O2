#!/bin/bash
GADGET_DIR=/sys/kernel/config/usb_gadget/p4wnp1
mkdir -p $GADGET_DIR
cd $GADGET_DIR

echo 0x1d6b > idVendor  # Linux Foundation
echo 0x0104 > idProduct # Multifunction Composite Gadget
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "1337" > strings/0x409/serialnumber
echo "SnowSecOps" > strings/0x409/manufacturer
echo "P4wnP1-Zero2W" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "Config 1: ECM network + HID" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

# ECM (USB Ethernet)
mkdir -p functions/ecm.usb0
HOST="42:42:42:42:42:42"
SELF="de:ad:be:ef:00:00"
echo $HOST > functions/ecm.usb0/host_addr
echo $SELF > functions/ecm.usb0/dev_addr
ln -s functions/ecm.usb0 configs/c.1/

# HID Keyboard
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
echo -ne \\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x01\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x01\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0 > functions/hid.usb0/report_desc
ln -s functions/hid.usb0 configs/c.1/

mkdir -p /dev/gadget
ls /sys/class/udc > UDC
