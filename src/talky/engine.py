"""Isolated Voxtype child. Never control the user's existing daemon."""
import json
import os
from pathlib import Path
import subprocess
import time
import threading


def engine_environment(runtime):
    original_runtime = os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
    environment = {key: value for key, value in os.environ.items() if not key.startswith('VOXTYPE_')}
    environment.update(XDG_RUNTIME_DIR=str(runtime),
                       PIPEWIRE_RUNTIME_DIR=os.environ.get('PIPEWIRE_RUNTIME_DIR', original_runtime),
                       PULSE_SERVER=os.environ.get('PULSE_SERVER', f'unix:{original_runtime}/pulse/native'))
    # Redirect non-runtime Voxtype side effects (meeting cleanup, caches) too.
    environment['XDG_DATA_HOME'] = str(runtime / 'data')
    environment['XDG_CONFIG_HOME'] = str(runtime / 'config')
    environment['XDG_CACHE_HOME'] = str(runtime / 'cache')
    return environment


class Engine:
    def __init__(self, runtime, settings):
        self.runtime, self.settings = Path(runtime), settings
        self.directory = self.runtime / 'voxtype'
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.environment = engine_environment(self.runtime)
        self.config = self.runtime / 'voxtype.toml'
        self.result_file = self.runtime / 'transcript.txt'
        self.process = None
        self.closing = threading.Event()

    def start(self):
        model = str(Path(self.settings.model).expanduser().resolve(strict=True))
        quote = json.dumps
        self.config.write_text(f'''engine = "whisper"
state_file = "auto"
[hotkey]
enabled = false
[audio]
device = "default"
sample_rate = 16000
max_duration_secs = {self.settings.max_recording_seconds}
[whisper]
mode = "local"
model = {quote(model)}
language = {quote(self.settings.language)}
translate = false
on_demand_loading = false
gpu_isolation = false
streaming = false
eager_processing = {str(self.settings.eager).lower()}
initial_prompt = {quote(', '.join(self.settings.vocabulary), ensure_ascii=False)}
[output]
mode = "file"
file_path = {quote(str(self.result_file))}
file_mode = "overwrite"
auto_submit = false
smart_auto_submit = false
[output.notification]
on_recording_start = false
on_recording_stop = false
on_transcription = false
[osd]
enabled = false
''')
        self.result_file.unlink(missing_ok=True)
        (self.directory / 'state').unlink(missing_ok=True)
        if self.closing.is_set():
            return
        self.process = subprocess.Popen([self.settings.voxtype, '--config', str(self.config), 'daemon'],
                                        env=self.environment, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        start_new_session=True)
        deadline = time.monotonic() + 90
        while not self.closing.is_set() and time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('speech engine failed to start')
            if self.state() == 'idle':
                return
            time.sleep(.1)
        if not self.closing.is_set():
            raise RuntimeError('speech engine startup timed out')

    def state(self):
        try:
            return (self.directory / 'state').read_text().strip()
        except FileNotFoundError:
            return 'loading'

    def command(self, command):
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError('speech engine stopped')
        # XDG_RUNTIME_DIR controls both PID lookup and all command sentinels.
        subprocess.run([self.settings.voxtype, '--config', str(self.config), 'record', command],
                       env=self.environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=3, check=True)

    def result(self):
        try:
            return self.result_file.read_text().strip()
        except FileNotFoundError:
            return ''
        finally:
            self.result_file.unlink(missing_ok=True)

    def close(self):
        self.closing.set()
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.result_file.unlink(missing_ok=True)
