#!/usr/bin/env python3
import argparse, subprocess, sys
ap = argparse.ArgumentParser(description="Quick recon on a target")
ap.add_argument("--target", default="10.13.37.2")
ap.add_argument("--top", type=int, default=200, help="Top N ports (nmap)")
args = ap.parse_args()
subprocess.call(["ping","-c","1",args.target])
subprocess.call(["nmap","--top-ports",str(args.top),"-sS","-Pn",args.target])
