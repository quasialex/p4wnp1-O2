#!/usr/bin/env python3
import os, sys, json, time

NAME="win_drop_and_run_stub"

def main():
    dst = os.getenv("P4WN_DROP_DST", "%APPDATA%\\Microsoft\\updater.bin")
    cmd = os.getenv("P4WN_RUN_CMD",  "cmd.exe /c start \"\" \"%APPDATA%\\Microsoft\\updater.bin\"")
    print(json.dumps({
        "name": NAME,
        "ts": int(time.time()),
        "artifact_plan": {
          "destination_hint": dst,
          "run_cmd_hint": cmd,
          "persistence_hint": "Startup|RunKey|ScheduledTask"
        },
        "note": "skeleton only; does not write files or execute"
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(0)

