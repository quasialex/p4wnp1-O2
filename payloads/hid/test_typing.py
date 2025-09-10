#!/usr/bin/env python3
import sys, time
sys.path.insert(0, "/opt/p4wnp1/tools")
from hid_type import win_r, type_string

def main():
    # Open Notepad via Win+R, then type a single line (benign smoke test)
    win_r()
    time.sleep(0.35)            # let the Run box render
    type_string("notepad\n")    # launch notepad
    time.sleep(0.9)             # let notepad window focus
    type_string("hello from p4wn\n")

if __name__ == "__main__":
    main()

