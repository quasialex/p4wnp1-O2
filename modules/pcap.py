# pcap.py
import subprocess, os
from pathlib import Path

LOGB = Path("/opt/p4wnp1/logs/pcap"); LOGB.mkdir(parents=True, exist_ok=True)

def register(subparsers):
    p = subparsers.add_parser("pcap", help="Packet capture (tcpdump)")
    ss = p.add_subparsers(dest="pcap_cmd")
    st = ss.add_parser("start", help="Start rotating capture")
    st.add_argument("--iface", default="usb0")
    st.add_argument("--size", type=int, default=25, help="File size MB")
    st.add_argument("--count", type=int, default=10, help="Rotate count")
    sp = ss.add_parser("stop", help="Stop all tcpdump captures")
    ss.add_parser("ls", help="List saved pcaps")

def handle(args):
    if args.pcap_cmd == "start":
        p = LOGB / "cap.pcap"
        cmd = [
            "systemd-run","--unit","p4w-pcap","--collect",
            "tcpdump","-i", args.iface, "-w", str(p), "-C", str(args.size), "-W", str(args.count), "-Z","root"
        ]
        return subprocess.run(cmd).returncode
    if args.pcap_cmd == "stop":
        return subprocess.run(["systemctl","stop","p4w-pcap"], text=True).returncode
    if args.pcap_cmd == "ls":
        for f in sorted(LOGB.glob("cap*.pcap")): print(f)
        return 0
    return 1

