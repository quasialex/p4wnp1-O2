#!/usr/bin/env python3

import json
import subprocess
import os
import time
import threading
import RPi.GPIO as GPIO
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
# === GPIO Exit Setup ===
EXIT_PIN = 20  # GPIO20 (joystick center press)
GPIO.setmode(GPIO.BCM)
GPIO.setup(EXIT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

exit_flag = threading.Event()

def monitor_exit_button():
    pressed_time = 0
    while not exit_flag.is_set():
        if GPIO.input(EXIT_PIN) == GPIO.LOW:
            pressed_time += 0.1
            if pressed_time >= 2:
                show("Exiting OLED...", 2)
                exit_flag.set()
                break
        else:
            pressed_time = 0
        time.sleep(0.1)

serial = i2c(port=1, address=0x3C)
device = sh1106(serial)

# === Utils ===
def show(text, duration=0):
    with canvas(device) as draw:
        draw.text((0, 0), text, font=FONT, fill=255)
    if duration > 0:
        time.sleep(duration)

threading.Thread(target=monitor_exit_button, daemon=True).start()

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

MENU_MTIME = os.path.getmtime(MENU_CONFIG)

def check_menu_reload():
    global MENU_MTIME
    try:
        new_mtime = os.path.getmtime(MENU_CONFIG)
        if new_mtime != MENU_MTIME:
            MENU_MTIME = new_mtime
            return read_menu()
    except Exception as e:
        show(f"Menu reload error:\n{str(e)}", 2)
    return None

def read_menu():
    def validate_items(items):
        valid = []
        for item in items:
            if "submenu" in item:
                sub = validate_items(item["submenu"])
                if sub:
                    item["submenu"] = sub
                    valid.append(item)
            elif "script" in item and os.path.exists(item["script"]):
                valid.append(item)
            elif "action" in item and (
                item["action"].startswith("sudo") or os.path.exists(item["action"])
            ):
                valid.append(item)
        return valid

    with open(MENU_CONFIG, 'r') as f:
        raw_menu = json.load(f)
    return validate_items(raw_menu)

def menu_loop(menu_stack):
    index = 0
    while not exit_flag.is_set():
        updated_menu = check_menu_reload()
        if updated_menu:
            menu_stack[-1] = updated_menu
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
            GPIO.cleanup()
            break

# === Start
try:
    top_menu = read_menu()
    menu_loop([top_menu])
except Exception as e:
    show(f"Fatal error:\n{str(e)}", 3)
    GPIO.cleanup()
