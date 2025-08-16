# /opt/p4wnp1/webui/app.py
import os
from flask import request, abort
from flask import Flask, render_template, request, jsonify
from sse import stream
from services import status as st

app = Flask(__name__, template_folder="templates", static_folder="static")

HOST = os.getenv("WEBUI_HOST", "127.0.0.1")
PORT = int(os.getenv("WEBUI_PORT", "8080"))
TOKEN = os.getenv("WEBUI_TOKEN", "")

@app.before_request
def require_token():
    # If no token is configured, allow all (explicit choice)
    if not WEBUI_TOKEN:
        return
    if request.headers.get("X-P4WN-Token") != WEBUI_TOKEN:
        abort(401)

@app.get("/")
def dashboard():
    return render_template("dashboard.html",
        usb=st.usb_status(), payload=st.payload_status(),
        web=st.web_status(), ips=st.ip_list())

@app.get("/usb")
def usb():
    return render_template("usb.html", usb=st.usb_status())

@app.post("/usb/set")
def usb_set():
    mode = request.form.get("mode","")
    rc, out = st.usb_set(mode)
    return jsonify(ok=(rc==0), msg=out, usb=st.usb_status())

@app.get("/payloads")
def payloads():
    return render_template("payloads.html",
                           current=st.payload_status(),
                           names=st.payload_list())

@app.post("/payloads/set")
def payloads_set():
    name = request.form.get("name","")
    rc, out = st.payload_set(name)
    return jsonify(ok=(rc==0), msg=out, current=st.payload_status())

@app.get("/network")
def network():
    return render_template("network.html", ips=st.ip_list())

@app.get("/web")
def web():
    return render_template("logs.html", web=st.web_status())

@app.post("/web/ctl")
def web_ctl():
    cmd = request.form.get("cmd","status")
    rc, out = st.web_ctl(cmd)
    return jsonify(ok=(rc==0), msg=out, web=st.web_status())

@app.post("/web/bind")
def web_bind():
    host = request.form.get("host","0.0.0.0")
    port = int(request.form.get("port","8080"))
    rc, out = st.web_bind(host, port)
    return jsonify(ok=(rc==0), msg=out, web=st.web_status())

@app.get("/events")
def events():
    return stream()

if __name__ == "__main__":
    # read WEBUI_HOST/WEBUI_PORT set by p4wnctl's systemd override
    import os
    host = os.getenv("WEBUI_HOST", "0.0.0.0")   # was "127.0.0.1"
    port = int(os.getenv("WEBUI_PORT", "8080"))
    app.run(host=host, port=port, debug=False)
