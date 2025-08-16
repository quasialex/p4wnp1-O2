# /opt/p4wnp1/webui/services/status.py
from .shell import run, P4WN

def usb_status():       return run(f"{P4WN}/p4wnctl.py usb status")[1]
def payload_status():   return run(f"{P4WN}/p4wnctl.py payload status")[1]
def payload_list():     return run(f"{P4WN}/p4wnctl.py payload list")[1].splitlines()
def ip_list():          return run(f"{P4WN}/p4wnctl.py ip")[1].splitlines()
def web_status():       return run(f"{P4WN}/p4wnctl.py web status")[1]
def usb_set(mode):      return run(f"sudo {P4WN}/p4wnctl.py usb set {mode}")
def payload_set(name):  return run(f"sudo {P4WN}/p4wnctl.py payload set {name}")
def web_bind(host,port):return run(f"sudo {P4WN}/p4wnctl.py web config set --host {host} --port {int(port)}")
def web_ctl(cmd):       return run(f"sudo {P4WN}/p4wnctl.py web {cmd}")
