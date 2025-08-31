#!/usr/bin/env python3
import os, sys, json, subprocess, shlex
from pathlib import Path

P4WN = Path("/opt/p4wnp1")
WWW_CAPTIVE = P4WN / "payloads/network/web/captive"
WWW_PAYLOADS = P4WN / "payloads/network/web/payloads"
LE_ENV = P4WN / "config/letsencrypt.env"

APACHE_VHOST_HTTP = "/etc/apache2/sites-available/p4wnp1-portal.conf"
APACHE_VHOST_HTTPS = "/etc/apache2/sites-available/p4wnp1-portal-ssl.conf"

def sh(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def enable_site(site):
    sh(f"a2ensite {shlex.quote(site)}")

def disable_default_sites():
    for s in ("000-default.conf", "default-ssl.conf"):
        sh(f"a2dissite {s}")

def write(path: str, text: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text)

def read_le_env():
    env = {}
    if LE_ENV.exists():
        for ln in LE_ENV.read_text().splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"): continue
            if "=" in ln:
                k,v = ln.split("=",1)
                env[k.strip()] = v.strip().strip('"')
    return env

def vhost_http(domain_or_any):
    # HTTP vhost always exists (captive portal + ACME webroot)
    return f"""
<VirtualHost *:80>
  ServerName {domain_or_any}
  ServerAdmin admin@localhost

  # Captive portal root (editable HTML)
  DocumentRoot {WWW_CAPTIVE}

  <Directory {WWW_CAPTIVE}>
    Options -Indexes +FollowSymLinks
    AllowOverride All
    Require all granted
  </Directory>

  Alias /payloads {WWW_PAYLOADS}
  <Directory {WWW_PAYLOADS}>
    Options -Indexes +FollowSymLinks
    Require all granted
  </Directory>

  # Helpful headers
  Header always set X-Frame-Options SAMEORIGIN
  Header always set X-Content-Type-Options nosniff

  # ACME webroot for certbot
  Alias /.well-known/acme-challenge /var/www/html/.well-known/acme-challenge/
  <Directory /var/www/html/.well-known/acme-challenge/>
    Options None
    AllowOverride None
    Require all granted
  </Directory>

  ErrorLog  ${APACHE_LOG_DIR}/p4wnp1-error.log
  CustomLog ${APACHE_LOG_DIR}/p4wnp1-access.log combined
</VirtualHost>
""".strip() + "\n"

def vhost_ssl(domain, cert, key):
    return f"""
<IfModule mod_ssl.c>
<VirtualHost *:443>
  ServerName {domain}
  ServerAdmin admin@localhost

  DocumentRoot {WWW_CAPTIVE}
  <Directory {WWW_CAPTIVE}>
    Options -Indexes +FollowSymLinks
    AllowOverride All
    Require all granted
  </Directory>

  Alias /payloads {WWW_PAYLOADS}
  <Directory {WWW_PAYLOADS}>
    Options -Indexes +FollowSymLinks
    Require all granted
  </Directory>

  SSLEngine on
  SSLCertificateFile {cert}
  SSLCertificateKeyFile {key}
  SSLProtocol all -SSLv2 -SSLv3 -TLSv1 -TLSv1.1

  Header always set Strict-Transport-Security "max-age=31536000"
  Header always set X-Frame-Options SAMEORIGIN
  Header always set X-Content-Type-Options nosniff

  ErrorLog  ${APACHE_LOG_DIR}/p4wnp1-ssl-error.log
  CustomLog ${APACHE_LOG_DIR}/p4wnp1-ssl-access.log combined
</VirtualHost>
</IfModule>
""".strip() + "\n"

def ensure_dirs():
    WWW_CAPTIVE.mkdir(parents=True, exist_ok=True)
    WWW_PAYLOADS.mkdir(parents=True, exist_ok=True)
    # If captive has no index, drop a stub
    idx = WWW_CAPTIVE / "index.html"
    if not idx.exists():
        idx.write_text("""<!doctype html><html><head><meta charset="utf-8">
<title>P4wnP1 Captive Portal</title></head>
<body><h1>P4wnP1 Captive Portal</h1><p>Place your portal files here.</p></body></html>
""")

def ensure_selfsigned():
    key = "/etc/ssl/private/p4wnp1-selfsigned.key"
    crt = "/etc/ssl/certs/p4wnp1-selfsigned.crt"
    if not Path(key).exists() or not Path(crt).exists():
        sh("openssl req -x509 -nodes -newkey rsa:2048 -days 365 "
           "-keyout /etc/ssl/private/p4wnp1-selfsigned.key "
           "-out /etc/ssl/certs/p4wnp1-selfsigned.crt "
           '-subj "/C=XX/ST=NA/L=NA/O=P4wnP1/OU=Portal/CN=localhost"')
    return crt, key

def main():
    ensure_dirs()
    env = read_le_env()
    domain = env.get("DOMAIN","").strip()
    email  = env.get("EMAIL","").strip()

    # Always create/enable HTTP vhost (Used for captive + ACME)
    host_token = domain if domain else "localhost"
    write(APACHE_VHOST_HTTP, vhost_http(host_token))
    disable_default_sites()
    enable_site("p4wnp1-portal.conf")

    # TLS path: Let's Encrypt if domain+email, else self-signed
    tls_cert = tls_key = None
    if domain and email:
        # ACME via webroot
        Path("/var/www/html/.well-known/acme-challenge").mkdir(parents=True, exist_ok=True)
        # ensure HTTP site is up for challenge
        sh("systemctl restart apache2")
        cp = sh(f"certbot certonly --agree-tos --noninteractive --email {shlex.quote(email)} "
                f"--webroot -w /var/www/html -d {shlex.quote(domain)}")
        if cp.returncode == 0:
            tls_cert = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
            tls_key  = f"/etc/letsencrypt/live/{domain}/privkey.pem"
        else:
            # fall back to self-signed
            tls_cert, tls_key = ensure_selfsigned()
    else:
        tls_cert, tls_key = ensure_selfsigned()

    # Write SSL vhost and enable
    write(APACHE_VHOST_HTTPS, vhost_ssl(host_token if domain else "localhost", tls_cert, tls_key))
    sh("a2enmod ssl headers rewrite")
    enable_site("p4wnp1-portal-ssl.conf")
    sh("systemctl restart apache2")

    print("[+] Apache captive portal configured.")
    if domain and email:
        print(f"[+] TLS: Let's Encrypt configured for {domain}")
    else:
        print("[+] TLS: self-signed certificate active")

if __name__ == "__main__":
    sys.exit(main())
