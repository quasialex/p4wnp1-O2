import os
import json

PAYLOAD_DIR = '/home/pi/payloads'
entries = []

for folder in os.listdir(PAYLOAD_DIR):
    meta_path = os.path.join(PAYLOAD_DIR, folder, 'metadata.json')
    if os.path.isfile(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
            entries.append({
                "name": meta['name'],
                "script": meta['script']
            })

with open('/home/pi/oled/menu_config.json', 'w') as f:
    json.dump(entries, f, indent=2)

print("[+] Menu config regenerated with", len(entries), "entries.")
