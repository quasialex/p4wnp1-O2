#!/usr/bin/env python3
import json
import os
import time

CONFIG = "/opt/p4wnp1/config/payload.json"
ACTIVE = "/opt/p4wnp1/config/active_payload"

# Placeholder joystick interface
class Joystick:
    def __init__(self):
        self.index = 0
    def read_input(self):
        # Stub: Replace with actual GPIO input
        key = input("[W/S] Up/Down | [Enter] Select > ").lower()
        return key

def load_payloads():
    with open(CONFIG, 'r') as f:
        data = json.load(f)
        return [key for key in data if data[key].get("enabled")]

def select_payload(payloads):
    js = Joystick()
    while True:
        os.system('clear')
        print("=== P4wnP1 Payload Menu ===")
        for i, p in enumerate(payloads):
            print(f"{'→' if i == js.index else ' '} {p}")
        key = js.read_input()
        if key == 'w':
            js.index = (js.index - 1) % len(payloads)
        elif key == 's':
            js.index = (js.index + 1) % len(payloads)
        elif key == '':  # Enter key
            return payloads[js.index]

def main():
    payloads = load_payloads()
    if not payloads:
        print("[!] No enabled payloads in config.")
        return
    chosen = select_payload(payloads)
    with open(ACTIVE, 'w') as f:
        f.write(chosen)
    print(f"[+] Selected payload: {chosen}")

if __name__ == '__main__':
    main()
