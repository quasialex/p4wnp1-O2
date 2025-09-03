#!/usr/bin/env python3
import os, sys, json, time

NAME="win_enable_rdp_firewall_stub"
PLAN=[
  "rdp:check_service_state",
  "rdp:check_nla_policy",
  "fw:inbound_rule_probe_3389",
  "policy:allow_rdp_hint"
]

def main():
    print(json.dumps({
        "name": NAME,
        "ts": int(time.time()),
        "plan": PLAN,
        "note": "skeleton only; does not modify services or firewall"
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(0)

