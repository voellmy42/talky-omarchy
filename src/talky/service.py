"""Talky's session service and local Unix-socket controls."""
from collections import deque
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import socket
import socketserver
import struct
import subprocess
import threading
import time

from . import desktop
from .engine import Engine
from .formatter import LocalFormatter
from .settings import Settings

ACTIVE = {'starting', 'recording', 'transcribing', 'formatting'}


def runtime_dir():
    base = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    return base / 'talky'


def request(command='status', **parameters):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(5)
        client.connect(str(runtime_dir() / 'control.sock'))
        client.sendall(json.dumps(dict(command=command, **parameters)).encode() + b'\n')
        received = bytearray()
        while b'\n' not in received:
            block = client.recv(65536)
            if not block:
                raise RuntimeError('Talky disconnected')
            received.extend(block)
            if len(received) > 2_000_000:
                raise ValueError('Talky response too large')
        return json.loads(received.partition(b'\n')[0])


class Controller:
    def __init__(self, engine, formatter, settings):
        self.engine, self.formatter, self.settings = engine, formatter, settings
        self.lock = threading.RLock()
        self.state = 'loading'
        self.message = 'Warming up local speech and cleanup models…'
        self.text = ''
        self.raw = ''
        self.target = {}
        self.generation = 0
        self.started = None
        self.released = None
        self.stage_started = time.monotonic()
        self.timings = {}
        self.cleanup = settings.cleanup
        self.cleanup_status = 'raw'
        self.levels = deque([0.0] * 36, maxlen=36)
        self.closing = threading.Event()
        self.saw_recording = False
        self.engine_ready = False
        self.preview = False
        self.stop_pending = False

    def snapshot(self, include_text=True):
        with self.lock:
            result = dict(state=self.state, message=self.message,
                        target=self.target.get('application', ''), cleanup=self.cleanup,
                        formatter=self.formatter.state, cleanup_status=self.cleanup_status,
                        elapsed=round(time.monotonic() - self.started, 1) if self.started and self.state == 'recording' else 0,
                        timings=self.timings, levels=list(self.levels))
            if include_text:
                result.update(text=self.text, raw=self.raw)
            return result

    def command(self, command, **parameters):
        with self.lock:
            if command == 'status':
                return self.snapshot(include_text=parameters.get('include_text', True))
            if command == 'shutdown':
                self.generation += 1
                self.closing.set()
                return {'ok': True}
            if command == 'cleanup':
                self.cleanup = bool(parameters.get('enabled', True))
                return self.snapshot()
            if command == 'copy':
                if self.text:
                    desktop.copy(self.text)
                return self.snapshot()
            if command == 'clear':
                self.text = self.raw = ''
                return self.snapshot()
            if command == 'cancel':
                if self.state in ACTIVE:
                    self.generation += 1
                    self.engine.command('cancel')
                    self.text = self.raw = ''
                    self.started = self.released = None
                    self.state, self.message = 'cancelling', 'Discarding dictation…'
                    self.stage_started = time.monotonic()
                return self.snapshot()
            if command == 'toggle':
                command = 'stop' if self.state in {'starting', 'recording'} else 'start'
            if command == 'start':
                if not self.engine_ready or self.state in ACTIVE | {'cancelling'}:
                    return self.snapshot()
                self.target = desktop.focus()
                if self.target.get('application') == 'io.talky.App':
                    self.target = {}
                self.preview = bool(parameters.get('preview', False))
                self.generation += 1
                self.text = self.raw = ''
                self.timings = {}
                self.levels.clear()
                self.levels.extend([0.0] * 36)
                self.started = self.stage_started = time.monotonic()
                self.released = None
                self.saw_recording = False
                self.stop_pending = False
                self.engine.result()  # discard any previous result
                self.engine.command('start')
                self.state, self.message = 'starting', 'Opening microphone…'
            elif command == 'stop' and self.state in {'starting', 'recording'}:
                self.released = time.monotonic()
                if self.state == 'starting':
                    self.stop_pending = True
                else:
                    self.stage_started = time.monotonic()
                    self.engine.command('stop')
                    self.state, self.message = 'transcribing', 'Turning speech into text…'
            return self.snapshot()

    def poll(self):
        with self.lock:
            if self.engine.process is not None and self.engine.process.poll() is not None:
                self.generation += 1
                self.engine_ready = False
                self.state, self.message = 'error', 'Speech engine stopped. Restart Talky to retry.'
                return
            engine_state = self.engine.state()
            if self.state == 'loading' and engine_state == 'idle':
                self.engine_ready = True
                self.state, self.message = 'ready', 'Ready when you are.'
            elif self.state == 'starting' and engine_state in {'recording', 'streaming'}:
                self.saw_recording = True
                self.state, self.message = 'recording', 'Listening. Say it your way.'
                self.stage_started = time.monotonic()
                if self.stop_pending:
                    self.engine.command('stop')
                    self.state, self.message = 'transcribing', 'Turning speech into text…'
            elif self.state == 'recording' and engine_state not in {'recording', 'streaming'}:
                self.released = self.stage_started = time.monotonic()
                self.state, self.message = 'transcribing', 'Turning speech into text…'
            elif self.state == 'transcribing' and engine_state == 'idle':
                raw = self.engine.result()
                if not raw:
                    self.state, self.message = 'ready', 'No transcript returned. Check your microphone and try again.'
                else:
                    self.raw = raw
                    self.state, self.message = 'formatting', 'A little polish, all on your device…'
                    token = self.generation
                    threading.Thread(target=self.finish, args=(raw, token), daemon=True).start()
            elif self.state == 'cancelling' and engine_state == 'idle':
                self.engine.result()
                self.state, self.message = 'ready', 'Cancelled. Nothing inserted.'
            elif self.state == 'starting' and time.monotonic() - self.stage_started > 5:
                self.engine.command('cancel')
                self.state, self.message = 'cancelling', 'Microphone did not start. Resetting…'
                self.stage_started = time.monotonic()
            elif self.state in {'transcribing', 'cancelling'} and time.monotonic() - self.stage_started > self.settings.asr_timeout:
                self.generation += 1
                self.engine_ready = False
                self.state, self.message = 'error', 'Speech engine timed out. Restart Talky to retry.'

    def finish(self, raw, token):
        try:
            asr_done = time.monotonic()
            if self.cleanup:
                text, cleanup_status, seconds = self.formatter.format(raw, self.target.get('application', ''), self.settings.vocabulary)
            else:
                text, cleanup_status, seconds = raw, 'raw', 0
            with self.lock:
                if token != self.generation or self.closing.is_set():
                    return
                self.text, self.cleanup_status = text, cleanup_status
                self.timings = dict(final_transcription_seconds=round(asr_done - (self.released or asr_done), 3),
                                    formatting_seconds=round(seconds, 3))
                if self.preview:
                    self.state, self.message = 'preview', 'Preview ready. Copy when you want to use it.'
                else:
                    self.state, self.message = desktop.deliver(text, self.target)
                    if self.state == 'inserted' and self.released:
                        self.timings['release_to_paste_sent_seconds'] = round(time.monotonic() - self.released, 3)
                    # A paste keystroke is observable; acceptance by the app is not.
                if cleanup_status == 'fallback':
                    self.message += ' Cleanup timed out or was rejected; original text used.'
        except (OSError, ValueError, subprocess.SubprocessError):
            with self.lock:
                if token == self.generation:
                    self.state, self.message = 'error', 'Output failed. Your text is available here to copy.'

    def read_levels(self):
        while not self.closing.is_set():
            try:
                with socket.socket(socket.AF_UNIX) as stream:
                    stream.settimeout(1)
                    stream.connect(str(self.engine.directory / 'audio.sock'))
                    buffer = b''
                    counter = 0
                    while not self.closing.is_set():
                        try:
                            block = stream.recv(4096)
                        except socket.timeout:
                            continue
                        if not block:
                            break
                        buffer += block
                        while len(buffer) >= 16:
                            _, low, high, _ = struct.unpack('=Ifff', buffer[:16])
                            buffer = buffer[16:]
                            counter += 1
                            if counter % 5 == 0:
                                amplitude = math.sqrt(min(1.0, max(abs(low), abs(high))))
                                if math.isfinite(amplitude):
                                    with self.lock:
                                        self.levels.append(amplitude)
            except OSError:
                self.closing.wait(.5)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        try:
            message = json.loads(self.rfile.readline(65536))
            if not isinstance(message, dict):
                raise ValueError('invalid request')
            command = message.pop('command')
            response = self.server.controller.command(command, **message)
        except (ValueError, KeyError, OSError, RuntimeError, subprocess.SubprocessError):
            response = {'error': 'Talky could not complete that action.'}
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode() + b'\n')


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def serve(config_path=None):
    os.umask(0o077)
    runtime = runtime_dir()
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    if runtime.stat().st_uid != os.getuid():
        raise RuntimeError('runtime directory has another owner')
    runtime.chmod(0o700)
    from .overlay import OverlayProcess
    settings = Settings.load(config_path)
    with (runtime / 'service.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        socket_path = runtime / 'control.sock'
        socket_path.unlink(missing_ok=True)
        engine = Engine(runtime / 'engine', settings)
        formatter = LocalFormatter(settings)
        controller = Controller(engine, formatter, settings)
        overlay = OverlayProcess()
        with Server(str(socket_path), Handler) as server:
            server.controller = controller
            server.timeout = .1
            signal.signal(signal.SIGTERM, lambda *_: controller.closing.set())
            signal.signal(signal.SIGINT, lambda *_: controller.closing.set())
            def warmup():
                try:
                    engine.start()
                except (OSError, RuntimeError, ValueError):
                    with controller.lock:
                        controller.state, controller.message = 'error', 'Could not load speech model. Check Talky settings and restart.'
            engine_thread = threading.Thread(target=warmup, daemon=True)
            formatter_thread = threading.Thread(target=formatter.start, daemon=True)
            engine_thread.start()
            formatter_thread.start()
            threading.Thread(target=controller.read_levels, daemon=True).start()
            try:
                while not controller.closing.is_set():
                    server.handle_request()
                    overlay.poll()
                    if not engine_thread.is_alive():
                        controller.poll()
            finally:
                controller.closing.set()
                controller.generation += 1
                overlay.close()
                engine.close()
                formatter.close()
                socket_path.unlink(missing_ok=True)
    return 0
