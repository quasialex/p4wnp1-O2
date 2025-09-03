#!/usr/bin/env python3
import os, sys, json, time

NAME="win_sam_hive_copy_stub"
TARGETS=[
  "%WINDIR%\\System32\\config\\SAM",
  "%WINDIR%\\System32\\config\\SYSTEM",
  "%WINDIR%\\System32\\config\\SECURITY"
]

def main():
    print(json.dumps({
        "name": NAME,
        "ts": int(time.time()),
        "targets": TARGETS,
        "plan": [
          "context:need_admin_or_volume_shadow",
          "shadow:plan_create_snapshot",
          "exfil:path_plan"
        ],
        "note": "skeleton only; no filesystem or VSS interaction"
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(0)

