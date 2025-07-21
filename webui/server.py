#!/usr/bin/env python3
from flask import Flask, send_from_directory, jsonify, request
import subprocess
import json
import os

BASE_DIR = os.getenv('P4WN_HOME', '/opt/p4wnp1')
CFG = os.path.join(BASE_DIR, 'config/payload.json')
ACTIVE = os.path.join(BASE_DIR, 'config/active_payload')
RUNNER = os.path.join(BASE_DIR, 'run_payload.sh')
LOG_FILE = os.path.join(BASE_DIR, 'logs/runner.log')

app = Flask(__name__, static_folder=os.path.dirname(__file__))

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

@app.route('/api/payloads')
def payloads():
    """Return mapping of available payloads and metadata."""
    with open(CFG) as f:
        data = json.load(f)
    return jsonify(data)

@app.route('/api/payloads/<name>', methods=['PATCH'])
def update_payload(name):
    """Update payload properties e.g. enabled flag."""
    with open(CFG) as f:
        data = json.load(f)
    if name not in data:
        return "Not found", 404
    payload = data[name]
    updates = request.get_json(force=True) or {}
    if 'enabled' in updates:
        payload['enabled'] = bool(updates['enabled'])
    data[name] = payload
    with open(CFG, 'w') as f:
        json.dump(data, f, indent=2)
    return '', 204

@app.route('/api/run/<payload>', methods=['POST'])
def run_payload(payload):
    with open(ACTIVE, 'w') as f:
        f.write(payload)
    result = subprocess.run(['bash', RUNNER], capture_output=True, text=True)
    return result.stdout + result.stderr

@app.route('/api/log')
def get_log():
    """Return the tail of the runner log."""
    lines = request.args.get('lines', 100)
    try:
        lines = int(lines)
    except ValueError:
        lines = 100
    if not os.path.exists(LOG_FILE):
        return ""
    with open(LOG_FILE) as f:
        data = f.readlines()
    return ''.join(data[-lines:])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
