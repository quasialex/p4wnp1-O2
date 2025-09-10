#!/usr/bin/env python3
import subprocess, time

def sh(cmd): return subprocess.run(["bash","-lc",cmd], check=False)

def main():
    # Power on, discoverable, pairable
    sh('bluetoothctl <<EOF\npower on\nagent NoInputNoOutput\ndefault-agent\ndiscoverable on\npairable on\nEOF')
    # Start NAP on pan0
    sh("bt-network -s nap pan0 &")
    # Give it a moment, bring interface up and DHCP/NAT like usb0
    time.sleep(2)
    sh("ip link set pan0 up || true")
    sh("ip addr add 10.98.0.1/24 dev pan0 || true")
    # ad-hoc dnsmasq config
    cfg="/opt/p4wnp1/config/net/dnsmasq-pan0.conf"
    with open(cfg,"w") as f:
        f.write("interface=pan0\nbind-interfaces\ndhcp-range=10.98.0.10,10.98.0.200,255.255.255.0,12h\n"
                "dhcp-option=3,10.98.0.1\ndhcp-option=6,10.98.0.1\n")
    subprocess.run(["systemctl","enable","--now","p4wnp1-dnsmasq@pan0.service"], check=False)

if __name__=="__main__":
    main()

