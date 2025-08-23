#!/usr/bin/env python3
import sys, time, glob, os

# Map US layout (extend as needed)
KEY = {
 'a':(0,0x04),'b':(0,0x05),'c':(0,0x06),'d':(0,0x07),'e':(0,0x08),'f':(0,0x09),
 'g':(0,0x0a),'h':(0,0x0b),'i':(0,0x0c),'j':(0,0x0d),'k':(0,0x0e),'l':(0,0x0f),
 'm':(0,0x10),'n':(0,0x11),'o':(0,0x12),'p':(0,0x13),'q':(0,0x14),'r':(0,0x15),
 's':(0,0x16),'t':(0,0x17),'u':(0,0x18),'v':(0,0x19),'w':(0,0x1a),'x':(0,0x1b),
 'y':(0,0x1c),'z':(0,0x1d),
 '1':(0,0x1e),'2':(0,0x1f),'3':(0,0x20),'4':(0,0x21),'5':(0,0x22),
 '6':(0,0x23),'7':(0,0x24),'8':(0,0x25),'9':(0,0x26),'0':(0,0x27),
 ' ':(0,0x2c), '\n':(0,0x28), '\t':(0,0x2b),
 '-':(0,0x2d),'=':(0,0x2e),'[':(0,0x2f),']':(0,0x30),'\\':(0,0x31),
 ';':(0,0x33), "'":(0,0x34), '`':(0,0x35), ',':(0,0x36), '.':(0,0x37), '/':(0,0x38),
 '!':(0x02,0x1e),'@':(0x02,0x1f),'#':(0x02,0x20),'$':(0x02,0x21),'%':(0x02,0x22),
 '^':(0x02,0x23),'&':(0x02,0x24),'*':(0x02,0x25),'(':(0x02,0x26),')':(0x02,0x27),
 '_':(0x02,0x2d),'+':(0x02,0x2e),'{':(0x02,0x2f),'}':(0x02,0x30),'|':(0x02,0x31),
 ':':(0x02,0x33),'"':(0x02,0x34),'~':(0x02,0x35),'<':(0x02,0x36),'>':(0x02,0x37),'?':(0x02,0x38),
}

def find_hidg():
    cands = sorted(glob.glob("/dev/hidg*"))
    if not cands:
        sys.exit("No /dev/hidg* device. Ensure your USB mode includes HID keyboard.")
    return cands[0]

def press(fd, mod, code):
    fd.write(bytes([mod,0,code,0,0,0,0,0])); fd.flush()
    fd.write(b'\x00'*8); fd.flush()

def type_text(s, wpm=300):
    dev = find_hidg()
    if not os.access(dev, os.W_OK):
        sys.exit(f"No write access to {dev}. Run as root (sudo).")
    delay = max(0.002, 60.0/(wpm*5))
    with open(dev, "wb", buffering=0) as fd:
        for ch in s:
            if ch.isalpha():
                mod = 0x02 if ch.isupper() else 0x00
                code = KEY[ch.lower()][1]
                press(fd, mod, code)
            elif ch in KEY:
                mod, code = KEY[ch]
                press(fd, mod, code)
            else:
                # skip unknown char
                continue
            time.sleep(delay)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: inject_hid.py 'text' [wpm]"); sys.exit(1)
    wpm = int(sys.argv[2]) if len(sys.argv)>2 else 300
    type_text(sys.argv[1], wpm)

