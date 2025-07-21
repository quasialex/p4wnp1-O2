#!/usr/bin/env python3

import json
import os
import subprocess
import threading
import time

import RPi.GPIO as GPIO
from luma.core.error import DeviceNotFoundError
from luma.core.interface.serial import i2c, spi
from luma.core.render import canvas
from luma.oled.device import sh1106, ssd1306
from PIL import ImageFont

# === Config ===
P4WN_HOME = os.getenv("P4WN_HOME", "/opt/p4wnp1")
MENU_CONFIG = os.path.join(P4WN_HOME, "oled/menu_config.json")
LOG_DIR = os.path.join(P4WN_HOME, "logs/")
FONT = ImageFont.load_default()
DELAY_AFTER_RUN = 3  # seconds

# Replace {P4WN_HOME} tokens in menu entries
def replace_tokens(data):
    if isinstance(data, dict):
        return {k: replace_tokens(v) for k, v in data.items()}
    if isinstance(data, list):
        return [replace_tokens(v) for v in data]
    if isinstance(data, str):
        return data.replace("{P4WN_HOME}", P4WN_HOME)
    return data

# === OLED Init ===
# GPIO pin mappings taken from FuocomanSap/P4wnp1-ALOA-Menu-Reworked
UP_PIN = 6
DOWN_PIN = 19
LEFT_PIN = 5
RIGHT_PIN = 26
SELECT_PIN = 13
EXIT_PIN = 20  # dedicated exit/back button

GPIO.setmode(GPIO.BCM)
for pin in (UP_PIN, DOWN_PIN, LEFT_PIN, RIGHT_PIN, SELECT_PIN, EXIT_PIN):
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

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

def get_button():
    if GPIO.input(UP_PIN) == GPIO.LOW:
        return 'up'
    if GPIO.input(DOWN_PIN) == GPIO.LOW:
        return 'down'
    if GPIO.input(LEFT_PIN) == GPIO.LOW:
        return 'left'
    if GPIO.input(RIGHT_PIN) == GPIO.LOW:
        return 'right'
    if GPIO.input(SELECT_PIN) == GPIO.LOW:
        return 'select'
    return None

try:
    serial = i2c(port=1, address=0x3C)
    device = sh1106(serial)
except DeviceNotFoundError:
    serial = spi(device=0, port=0)
    device = ssd1306(serial)

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
    raw_menu = replace_tokens(raw_menu)
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

        btn = None
        while not btn and not exit_flag.is_set():
            btn = get_button()
            time.sleep(0.1)

        if exit_flag.is_set():
            break

        try:
            if btn == 'up':
                index = (index - 1) % len(menu)
                continue
            if btn == 'down':
                index = (index + 1) % len(menu)
                continue
            if btn == 'left':
                if len(menu_stack) > 1:
                    menu_stack.pop()
                    index = 0
                continue
            if btn in ('right', 'select'):
                if 'submenu' in item:
                    submenu = item['submenu'] + [{"name": "← Back"}]
                    menu_stack.append(submenu)
                    index = 0
                    continue
                if 'action' in item:
                    show("Running...\n" + name)
                    result = run_command(item['action'], label=name.replace(" ", "_"))
                    show(result, DELAY_AFTER_RUN)
                elif 'script' in item:
                    script_path = item['script']
                    if not os.path.exists(script_path):
                        show(f"✗ Not found\n{script_path}", 2)
                        continue
                    show("Running...\n" + name)
                    result = run_command(f"bash {script_path}", label=name.replace(" ", "_"))
                    show(result, DELAY_AFTER_RUN)

        except KeyboardInterrupt:
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
