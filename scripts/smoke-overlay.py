#!/usr/bin/env python3
"""Exercise the actual HUD with synthetic state, no microphone or main window.

Checks visibility, layer placement, waveform rendering, unchanged keyboard focus,
and hiding after completion. Does not contact the real dictation service.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import signal
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from talky.overlay import run_overlay


COMPOSITOR_ENV = dict(os.environ)
signal.alarm(12)  # A failed GTK callback must not leave the test process running.


def active_window():
    data = json.loads(subprocess.run(['hyprctl', '-j', 'activewindow'], capture_output=True,
                                    text=True, check=True, env=COMPOSITOR_ENV).stdout)
    return data.get('address')


started = time.monotonic()
initial_focus = active_window()
verified = set()
result = 1


def synthetic_status(command, **parameters):
    elapsed = time.monotonic() - started
    state = 'recording' if elapsed < 4 else ('formatting' if elapsed < 5 else 'ready')
    return {'state': state, 'elapsed': int(elapsed),
            'levels': [.06, .12, .24, .48, .8, 1, .72, .36, .18] * 4}


def check(app, snapshot):
    global result
    from gi.repository import GLib
    state = snapshot['state']
    # Mapping takes a frame; inspect after GTK/compositor have processed it.
    if state not in verified:
        verified.add(state)
        def verify():
            global result
            expected_visible = state != 'ready'
            assert app.window.get_visible() == expected_visible, state
            assert active_window() == initial_focus, 'Overlay stole keyboard focus'
            if state == 'recording':
                layers = json.loads(subprocess.run(['hyprctl', '-j', 'layers'], capture_output=True,
                                                  text=True, check=True, env=COMPOSITOR_ENV).stdout)
                found = []
                for monitor in layers.values():
                    for group in monitor.get('levels', {}).values():
                        found.extend(layer for layer in group if layer.get('namespace') == 'talky-recording')
                assert len(found) == 1, 'Expected one independent Talky layer'
                layer = found[0]
                geometry = f'{layer["x"]},{layer["y"]} {layer["w"]}x{layer["h"]}'
                subprocess.run(['grim', '-g', geometry, '/tmp/talky-overlay-smoke.png'], check=True)
                print('Recording HUD visible; waveform captured; keyboard focus unchanged.', flush=True)
            elif state == 'formatting':
                assert not app.stop.get_visible()
                print('Processing HUD stays visible.', flush=True)
            else:
                print('Completed HUD hidden. PASS', flush=True)
                result = 0
                app.quit()
            return False
        GLib.timeout_add(200, verify)
    return False


with tempfile.TemporaryDirectory(prefix='talky-overlay-test-') as isolated:
    os.environ['XDG_RUNTIME_DIR'] = isolated
    # WAYLAND_DISPLAY may be relative to the real runtime directory.
    real_runtime = f'/run/user/{os.getuid()}'
    wayland = os.environ.get('WAYLAND_DISPLAY', 'wayland-1')
    if not wayland.startswith('/'):
        os.environ['WAYLAND_DISPLAY'] = str(Path(real_runtime) / wayland)
    run_overlay(synthetic_status, check)
raise SystemExit(result)
