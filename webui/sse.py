# /opt/p4wnp1/webui/sse.py
import time, json
from flask import Response, stream_with_context
from services import status as st

def stream():
    @stream_with_context
    def gen():
        while True:
            payload = {
                "usb": st.usb_status(),
                "payload": st.payload_status(),
                "web": st.web_status(),
                "ip": st.ip_list(),
            }
            yield f"data: {json.dumps(payload)}\n\n"
            time.sleep(2)
    return Response(gen(), mimetype="text/event-stream")
