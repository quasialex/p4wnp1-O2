#!/usr/bin/env python3
from flask import Flask, send_from_directory, jsonify, request
import subprocess
import json
import os

BASE_DIR = os.getenv('P4WN_HOME', '/opt/p4wnp1')
CFG = os.path.join(BASE_DIR, 'config/payload.json')
ACTIVE = os.path.join(BASE_DIR, 'config/active_payload')
RUNNER = os.path.join(BASE_DIR, 'run_payload.sh')

app = Flask(__name__, static_folder=os.path.dirname(__file__))

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

@app.route('/api/payloads')
def payloads():
    with open(CFG) as f:
        data = json.load(f)
    return jsonify(list(data.keys()))

@app.route('/api/run/<payload>', methods=['POST'])
def run_payload(payload):
    with open(ACTIVE, 'w') as f:
        f.write(payload)
    result = subprocess.run(['bash', RUNNER], capture_output=True, text=True)
    return result.stdout + result.stderr

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
