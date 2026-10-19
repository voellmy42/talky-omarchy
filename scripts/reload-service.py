#!/usr/bin/env python3
"""Reload Talky's idle service without starting the microphone or control UI."""
import fcntl
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from talky.service import ACTIVE, request, runtime_dir

try:
    snapshot = request('status', include_text=False)
except (OSError, RuntimeError, ValueError):
    snapshot = {}
if snapshot.get('state') in ACTIVE | {'cancelling', 'loading'}:
    raise SystemExit('Talky is busy. Finish or cancel dictation before reloading.')
if snapshot:
    request('shutdown')
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        with (runtime_dir() / 'service.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(.1)
    else:
        raise SystemExit('Previous Talky service did not stop; reload aborted.')
process = subprocess.Popen([str(ROOT / 'talky'), 'daemon'], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           start_new_session=True)
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    try:
        snapshot = request('status', include_text=False)
        if snapshot.get('state') == 'ready' and snapshot.get('formatter') != 'loading':
            print('Talky service reloaded; models ready; microphone idle.', flush=True)
            break
        if snapshot.get('state') == 'error':
            raise SystemExit('Talky could not load models. Open the app to inspect its status.')
    except (OSError, RuntimeError, ValueError):
        if process.poll() is not None:
            raise SystemExit('Talky service exited before becoming ready.')
    time.sleep(.15)
else:
    raise SystemExit('Talky is still loading; check its status in the app.')
