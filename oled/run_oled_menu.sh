#!/bin/bash
set -e
export P4WN_HOME="${P4WN_HOME:-/opt/p4wnp1}"
exec /usr/bin/env python3 "$P4WN_HOME/hooks/oled_menu.py"
