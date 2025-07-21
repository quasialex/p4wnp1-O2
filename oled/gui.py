#!/usr/bin/env python3
# oled/gui.py
import json
import os
import subprocess
import time

BASE_DIR = os.getenv("P4WN_HOME", "/opt/p4wnp1")

try:
    import RPi.GPIO as GPIO
    from luma.core.interface.serial import spi
    from luma.oled.device import ssd1306
    from luma.core.render import canvas
    from PIL import ImageFont
    from luma.core.error import DeviceNotFoundError
    HARDWARE_AVAILABLE = True
except ImportError:
    print("[INFO] Running in mock mode (no GPIO/luma.oled)")
    HARDWARE_AVAILABLE = False

MENU_FILE = os.path.join(os.path.dirname(__file__), 'menu_config.json')
BUTTONS = {'UP': 6, 'DOWN': 19, 'SELECT': 13}  # customize for your GPIO

class OLEDMenu:
    def __init__(self):
        self.menu_items = self.load_menu()
        self.selected = 0

        if HARDWARE_AVAILABLE:
            try:
                self.serial = spi(device=0, port=0)
                self.device = ssd1306(self.serial)
                self.font = ImageFont.load_default()
                self.setup_gpio()
            except DeviceNotFoundError:
                print("[ERROR] OLED device not found. Falling back to mock mode.")
                self.device = None
                HARDWARE_AVAILABLE = False
        else:
            self.device = None

    def load_menu(self):
        with open(MENU_FILE) as f:
            return json.load(f)

    def setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        for pin in BUTTONS.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def wait_for_input(self):
        while True:
            if not HARDWARE_AVAILABLE:
                print("\n[Mock] Selected:", self.menu_items[self.selected]['name'])
                time.sleep(1)
                return True

            try:
                if GPIO.input(BUTTONS['UP']) == 0:
                    self.selected = (self.selected - 1) % len(self.menu_items)
                    return False
                elif GPIO.input(BUTTONS['DOWN']) == 0:
                    self.selected = (self.selected + 1) % len(self.menu_items)
                    return False
                elif GPIO.input(BUTTONS['SELECT']) == 0:
                    return True
            except RuntimeError as e:
                print("[GPIO Error]", e)

            time.sleep(0.1)

    def draw_menu(self):
        if not self.device:
            print("[Mock Display] Menu:")
            for idx, item in enumerate(self.menu_items):
                prefix = "> " if idx == self.selected else "  "
                print(prefix + item['name'])
            return

        with canvas(self.device) as draw:
            for idx, item in enumerate(self.menu_items):
                y = idx * 12
                prefix = "> " if idx == self.selected else "  "
                draw.text((0, y), prefix + item['name'], font=self.font, fill=255)

    def run_selected(self):
        cmd = self.menu_items[self.selected]['script']
        print("[INFO] Running:", cmd)
        subprocess.Popen(['/bin/bash', '-c', cmd])

    def run(self):
        while True:
            self.draw_menu()
            if self.wait_for_input():
                self.run_selected()
                break

if __name__ == '__main__':
    menu = OLEDMenu()
    menu.run()
