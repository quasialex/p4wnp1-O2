#!/usr/bin/env python3

import json
import subprocess
import os
import time
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from luma.core.render import canvas
from PIL import ImageFont

# === Config ===
MENU_CONFIG = '/opt/p4wnp1-o2/oled/menu_config.json'
LOG_DIR = '/opt/p4wnp1-o2/logs/'
FONT = ImageFont.load_default()
DELAY_AFTER_RUN = 3  # seconds

# === OLED Init ===
serial = i2c(port=1, address=0x3C)
device = sh1106(serial)

# === Utils ===
def show(text, duration=0):
    with canvas(device) as draw:
        draw.text((0, 0), text, font=FONT, fill=255)
    if duration > 0:
        time.sleep(duration)

def run_command(cmd, label="output"):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        log_file = os.path.join(LOG_DIR, f"{label}.log")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        with open(log_file, 'w') as f:
            f.write(result.stdout + "\n" + result.stderr)

        status = "✓ Success" if result.returncode == 0 else "✗ Failed"
        last_lines = (result.stdout + result.stderr).strip().splitlines()[-2:]
        feedback = f"{status}\n" + "\n".join(last_lines[-2:])
        return feedback
    except Exception as e:
        return f"✗ Error\n{str(e)}"

def read_menu():
    with open(MENU_CONFIG, 'r') as f:
        return json.load(f)

def menu_loop(menu_stack):
    index = 0
    while True:
        menu = menu_stack[-1]
        item = menu[index]
        name = item.get("name", "Unnamed")

        show(f"> {name}")
        time.sleep(1)

        try:
            if "submenu" in item:
                submenu = item["submenu"] + [{"name": "← Back"}]
                menu_stack.append(submenu)
                index = 0
                continue

            if "action" in item:
                show("Running...\n" + name)
                result = run_command(item["action"], label=name.replace(" ", "_"))
                show(result, DELAY_AFTER_RUN)

            elif "script" in item:
                script_path = item["script"]
                if not os.path.exists(script_path):
                    show(f"✗ Not found\n{script_path}", 2)
                    continue
                show("Running...\n" + name)
                result = run_command(f"bash {script_path}", label=name.replace(" ", "_"))
                show(result, DELAY_AFTER_RUN)

            index = (index + 1) % len(menu)

        except KeyboardInterrupt:
            if len(menu_stack) > 1 and index == len(menu) - 1:
                menu_stack.pop()
                index = 0
                continue
            show("Exiting...")
            break

# === Start
try:
    top_menu = read_menu()
    menu_loop([top_menu])
except Exception as e:
    show(f"Fatal error:\n{str(e)}", 3)
