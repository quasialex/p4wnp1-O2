#!/usr/bin/env python3
import json
import os
import time

CONFIG = "/opt/p4wnp1/config/payload.json"
ACTIVE = "/opt/p4wnp1/config/active_payload"

# Load payload list
def load_payloads():
    with open(CONFIG, 'r') as f:
        data = json.load(f)
        return [key for key in data if data[key].get("enabled")]

# Simple CLI scroll selector (no OLED yet)
def select_payload(payloads):
    index = 0
    while True:
        os.system('clear')
        print("P4wnP1 Payload Menu")
        for i, p in enumerate(payloads):
            prefix = "> " if i == index else "  "
            print(f"{prefix}{p}")

        print("\nUse W/S to move, Enter to select")
        key = input().lower()
        if key == 'w':
            index = (index - 1) % len(payloads)
        elif key == 's':
            index = (index + 1) % len(payloads)
        elif key == '':
            return payloads[index]

# Main logic
if __name__ == '__main__':
    payloads = load_payloads()
    chosen = select_payload(payloads)
    with open(ACTIVE, 'w') as f:
        f.write(chosen)
    print(f"[+] Payload set to: {chosen}")
