#!/usr/bin/env python3
"""
Native Messaging Host for Anki Vocab Builder.
Manages the Django server lifecycle: starts on demand, stops after idle timeout.

Chrome communicates via stdin/stdout using the native messaging protocol:
  - Each message: 4-byte little-endian length prefix + UTF-8 JSON body
"""
import sys
import json
import struct
import subprocess
import threading
import os
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
PYTHON = os.path.join(BASE_DIR, '.venv', 'bin', 'python3')
LOG_FILE = os.path.join(BASE_DIR, 'django_run.log')

IDLE_TIMEOUT = 300  # seconds — server stops after 5 min of no heartbeats

_proc = None
_timer = None
_lock = threading.Lock()


# ── Native messaging protocol ────────────────────────────────────────────────

def read_message():
    raw = sys.stdin.buffer.read(4)
    if len(raw) < 4:
        return None
    length = struct.unpack('<I', raw)[0]
    data = sys.stdin.buffer.read(length)
    return json.loads(data.decode('utf-8'))


def send_message(obj):
    data = json.dumps(obj).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('<I', len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


# ── Server management ────────────────────────────────────────────────────────

def server_running():
    return _proc is not None and _proc.poll() is None


def start_server():
    global _proc
    with _lock:
        if server_running():
            return
        log_fh = open(LOG_FILE, 'a')
        _proc = subprocess.Popen(
            [PYTHON, 'manage.py', 'runserver', '127.0.0.1:8000', '--noreload'],
            cwd=BACKEND_DIR,
            stdout=log_fh,
            stderr=log_fh,
        )


def stop_server():
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            _proc.terminate()
            try:
                _proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _proc.kill()
        _proc = None


def reset_idle_timer():
    global _timer
    if _timer:
        _timer.cancel()
    _timer = threading.Timer(IDLE_TIMEOUT, stop_server)
    _timer.daemon = True
    _timer.start()


# ── Main loop ────────────────────────────────────────────────────────────────

def main():
    while True:
        msg = read_message()
        if msg is None:
            # Chrome disconnected — clean up
            break

        action = msg.get('action')

        if action == 'start':
            start_server()
            reset_idle_timer()
            send_message({'status': 'started', 'running': server_running()})

        elif action == 'heartbeat':
            reset_idle_timer()
            send_message({'status': 'ok', 'running': server_running()})

        elif action == 'stop':
            if _timer:
                _timer.cancel()
            stop_server()
            send_message({'status': 'stopped'})

    # Chrome port closed — stop server to avoid orphan process
    stop_server()


if __name__ == '__main__':
    main()
