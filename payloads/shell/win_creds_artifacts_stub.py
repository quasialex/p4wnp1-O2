#!/usr/bin/env python3
import os, sys, json, time

NAME="win_creds_artifacts_stub"
ARTIFACTS=[
  "%LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default\\Login Data",
  "%LOCALAPPDATA%\\Microsoft\\Edge\\User Data\\Default\\Login Data",
  "%APPDATA%\\Mozilla\\Firefox\\Profiles\\*\\logins.json",
  "%APPDATA%\\Mozilla\\Firefox\\Profiles\\*\\key4.db",
  "%USERPROFILE%\\AppData\\Local\\Microsoft\\Credentials\\*",
  "%WINDIR%\\System32\\config\\SAM",
  "%WINDIR%\\System32\\config\\SYSTEM",
  "%WINDIR%\\System32\\config\\SECURITY"
]

def main():
    print(json.dumps({
        "name": NAME,
        "ts": int(time.time()),
        "artifact_catalog": ARTIFACTS,
        "note": "catalog only; no access attempted"
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(0)

