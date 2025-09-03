#!/usr/bin/env python3
import os, sys, json, time

NAME="win_registry_persistence_stub"
TARGETS=[
  r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
  r"HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce",
  r"HKLM\Software\Microsoft\Windows\CurrentVersion\Run",
  r"HKLM\Software\Microsoft\Windows\CurrentVersion\RunOnce",
  "ScheduledTask:UserLogon"
]

def main():
    out = {
        "name": NAME,
        "ts": int(time.time()),
        "persistence_candidates": TARGETS,
        "artifact_plan": {
          "drop_path_hint": "%APPDATA%\\Microsoft\\<name>.exe",
          "task_name_hint": "Updater_<name>"
        },
        "note": "skeleton only; no registry writes performed"
    }
    print(json.dumps(out, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(0)

