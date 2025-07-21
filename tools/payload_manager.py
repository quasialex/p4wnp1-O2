#!/usr/bin/env python3
"""Simple payload management helper."""
import json
import os
import argparse

P4WN_HOME = os.getenv("P4WN_HOME", "/opt/p4wnp1")
CONFIG_PATH = os.path.join(P4WN_HOME, "config/payload.json")


def load_payloads():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def list_payloads():
    payloads = load_payloads()
    for name, meta in payloads.items():
        status = "enabled" if meta.get("enabled", False) else "disabled"
        ptype = meta.get("type", "?")
        path = meta.get("path", "")
        print(f"{name}\t{ptype}\t{status}\t{path}")


def main():
    parser = argparse.ArgumentParser(description="P4wnP1 payload manager")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="List available payloads")

    args = parser.parse_args()
    if args.cmd == "list":
        list_payloads()


if __name__ == "__main__":
    main()
