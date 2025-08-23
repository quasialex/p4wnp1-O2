#!/usr/bin/env python3
import os, sys, subprocess, time, shlex

def sh(cmd): return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def main():
    # free the port if getty/modemmanager grab it
    sh("systemctl stop serial-getty@ttyGS0.service || true")
    sh("systemctl stop ModemManager.service || true")

    # Try to bring up pppd server side
    # Provide simple /etc/ppp/options.ttyGS0 if missing
    opt = "/etc/ppp/options.ttyGS0"
    if not os.path.exists(opt):
        open(opt, "w").write("""115200
local
debug
noauth
proxyarp
+ipv6
ms-dns 10.13.37.1
192.168.203.1:192.168.203.2
""")
    # kill any old pppd on GS0
    sh("pkill -f 'pppd /dev/ttyGS0' || true")

    print("[+] Starting pppd on /dev/ttyGS0")
    # foreground; systemd-run wraps us
    cmd = "/usr/sbin/pppd /dev/ttyGS0 115200 nodetach local debug passive"
    p = subprocess.Popen(cmd, shell=True)
    p.wait()
    return p.returncode

if __name__ == "__main__":
    sys.exit(main())
