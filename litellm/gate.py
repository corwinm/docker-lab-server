#!/usr/bin/python3
"""Authenticated internal-only synchronous fixed-purpose backup gate. No exec API."""
import hmac
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

BIND = '172.26.0.1'
PORT = 9843
NETWORK = ipaddress.ip_network('172.26.0.0/16')


def allowed(ip, path, auth, token, body):
    if ipaddress.ip_address(ip) not in NETWORK or path != '/backup':
        return False
    if not hmac.compare_digest(auth.encode(), b'Bearer ' + token):
        return False
    # WUD sends a container object. All fields are treated as data, never commands.
    return (isinstance(body, dict) and body.get('name') == 'litellm-litellm-1'
            and body.get('result', {}).get('hook') == {'phase': 'pre', 'parentTrigger': 'litellm'})


def backup():
    result = subprocess.run(['/usr/bin/python3', '-I', '/usr/local/lib/litellm-backup/backup.py'],
                            check=True, capture_output=True, timeout=480,
                            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin',
                                 'HOME': '/root', 'DOCKER_CONFIG': '/root/.docker'})
    report = json.loads(result.stdout)
    if report.get('restore_verified') is not True:
        raise RuntimeError('Restore verification missing')
    return report


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log headers, tokens, payloads, or raw child errors.

    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        self.connection.settimeout(10)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 131072:
                return self.reply(400, {'error': 'invalid body size'})
            body = json.loads(self.rfile.read(size))
            token = Path('/etc/litellm-backup/token').read_bytes().strip()
            if not allowed(self.client_address[0], self.path,
                           self.headers.get('Authorization', ''), token, body):
                return self.reply(403, {'error': 'denied'})
        except (ValueError, TypeError, AttributeError):
            return self.reply(400, {'error': 'invalid request'})
        try:
            report = backup()
        except Exception as error:
            print(json.dumps({'event': 'backup_failed', 'type': type(error).__name__}), flush=True)
            return self.reply(503, {'error': 'backup or restore verification failed; update forbidden'})
        print(json.dumps({'event': 'backup_verified', **report}), flush=True)
        self.reply(200, report)


if __name__ == '__main__':
    if len(sys.argv) != 1 or os.geteuid() != 0:
        raise SystemExit('Requires root and no arguments')
    HTTPServer((BIND, PORT), Handler).serve_forever()
