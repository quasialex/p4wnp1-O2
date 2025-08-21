# responder.py
import subprocess

def meta():
    return {
        "name": "responder",
        "summary": "Start/stop Responder for LLMNR/NBT-NS/MDNS capture",
        "usage": "p4wnctl.py responder start --iface usb0 --wpad --analyze",
        "notes": "Use only on engagements with explicit authorization.",
    }

def register(sub):
    p = sub.add_parser("responder", help="LLMNR/NBT-NS/MDNS poisoning & loot")
    ss = p.add_subparsers(dest="res_cmd")
    st = ss.add_parser("start", help="Start Responder")
    st.add_argument("--iface", default="usb0")
    st.add_argument("--wpad", action="store_true")
    st.add_argument("--analyze", action="store_true")
    sp = ss.add_parser("stop", help="Stop Responder")

def handle(args):
    if args.res_cmd == "start":
        cmd = ["responder", "-I", args.iface, "-v"]
        if args.wpad: cmd += ["-w"]
        if args.analyze: cmd += ["-A"]
        return subprocess.call(cmd)
    elif args.res_cmd == "stop":
        return subprocess.call(["pkill", "-f", "responder.py"])
