"""Talky: local dictation for Omarchy."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import tomllib
import wave


def run(command, text, timeout):
    """Bound the whole child process group, including shell grandchildren."""
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    try:
        stdout, _ = process.communicate(text, timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise
    if process.returncode:
        raise RuntimeError("backend failed")
    return stdout


def config(path):
    settings = tomllib.loads(Path(path).read_text()) if path else {}
    formatter = settings.get("formatter", {})
    if not isinstance(formatter, dict):
        raise ValueError("formatter must be a table")
    command = formatter.get("command", [])
    timeout = formatter.get("timeout_seconds", 2.0)
    if not isinstance(command, list) or any(not isinstance(x, str) for x in command):
        raise ValueError("formatter.command must be an argv array")
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
        raise ValueError("formatter timeout must be in (0, 60] seconds")
    return command, timeout


def format_text(raw, command, timeout):
    start = time.perf_counter()
    status = "passthrough"
    result = raw
    if command and raw.strip():
        try:
            candidate = run(command, raw, timeout)
            if not candidate.strip() or '\x00' in candidate:
                raise ValueError("invalid output")
            result, status = candidate, "formatted"
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
            status = "fallback"
    return result, status, time.perf_counter() - start


def benchmark(args):
    command, timeout = config(args.config)
    model = Path(args.model).expanduser().resolve(strict=True)
    audio = Path(args.audio).resolve(strict=True)
    with wave.open(str(audio), 'rb') as recording:
        if (recording.getnchannels(), recording.getframerate(), recording.getsampwidth(),
                recording.getcomptype()) != (1, 16000, 2, 'NONE'):
            raise ValueError("audio must be mono 16 kHz PCM16 WAV")
        duration = recording.getnframes() / 16000
    # A separate config prevents inheriting remote engines or user's output hooks.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="talky-") as temporary:
        isolated = Path(temporary) / 'voxtype.toml'
        isolated.write_text('[whisper]\nmode = "local"\nmodel = ' + json.dumps(str(model))
                            + '\nlanguage = ' + json.dumps(args.language)
                            + '\ntranslate = false\n[output]\nmode = "clipboard"\n')
        rows = []
        for index in range(args.runs):
            start = time.perf_counter()
            raw = run([args.voxtype, '--config', str(isolated), 'transcribe', str(audio)],
                      None, args.asr_timeout)
            asr = time.perf_counter() - start
            raw = extract_transcript(raw)
            formatted, status, formatting = format_text(raw, command, timeout)
            row = dict(run=index + 1, model_loading="fresh-process", audio_seconds=duration,
                       transcription_seconds=asr, formatting_seconds=formatting,
                       offline_total_seconds=asr + formatting, formatter_status=status,
                       release_to_insertion_seconds=None)
            if args.include_text:
                row.update(raw=raw, formatted=formatted)
            rows.append(row)
    # Explicit output only: benchmark data can contain private speech.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f"Wrote {len(rows)} offline measurements to {args.output}", file=sys.stderr)


def extract_transcript(output):
    # Voxtype 1.1.1 prints audio metadata on stdout, then a blank line before
    # the transcript. Never pass that metadata into a formatter.
    if '\n\n' in output:
        return output.split('\n\n', 1)[1].strip()
    if 'No speech detected, skipping transcription.' in output:
        return ''
    raise ValueError('unrecognized Voxtype transcription output')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    app = sub.add_parser('app', help='open the native Talky app')
    app.add_argument('--config')
    sub.add_parser('overlay', help='run the service-owned recording HUD')
    daemon = sub.add_parser('daemon', help='run the isolated resident Talky service')
    daemon.add_argument('--config')
    for name in ('start', 'stop', 'toggle', 'cancel', 'status', 'shutdown', 'copy', 'clear'):
        control = sub.add_parser(name, help=f'{name} Talky (never the existing Voxtype daemon)')
        if name in ('start', 'toggle'):
            control.add_argument('--preview', action='store_true')
    hook = sub.add_parser('format', help='stdin/stdout formatter; errors preserve input')
    hook.add_argument('--config')
    bench = sub.add_parser('benchmark', help='offline fresh-process ASR timings')
    bench.add_argument('audio')
    bench.add_argument('--model', required=True, help='existing local Whisper model path')
    bench.add_argument('--language', default='auto')
    bench.add_argument('--config')
    bench.add_argument('--voxtype', default='voxtype')
    bench.add_argument('--runs', type=int, default=3)
    bench.add_argument('--asr-timeout', type=float, default=120)
    bench.add_argument('--output', required=True, help='new local JSONL file')
    bench.add_argument('--include-text', action='store_true')
    args = parser.parse_args(sys.argv[1:] or ['app'])
    if args.action in ('app', 'daemon', 'overlay'):
        try:
            if args.action == 'app':
                from .ui import run_app
                return run_app(args.config)
            if args.action == 'overlay':
                from .overlay import run_overlay
                return run_overlay()
            from .service import serve
            return serve(args.config)
        except (OSError, ValueError, RuntimeError) as error:
            print(f'talky: could not start ({type(error).__name__})', file=sys.stderr)
            return 1
    if args.action not in ('format', 'benchmark'):
        from .service import request
        try:
            result = request(args.action, **({'preview': args.preview} if hasattr(args, 'preview') else {}))
            # Status intentionally omits dictated text; preview is in the app.
            result.pop('text', None)
            result.pop('raw', None)
            print(json.dumps(result, ensure_ascii=False))
            return 1 if 'error' in result else 0
        except (OSError, RuntimeError, ValueError):
            if args.action in ('start', 'toggle'):
                from .settings import ROOT
                subprocess.Popen([str(ROOT / 'talky'), 'app'], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                print('talky: opening app; start dictation once models are ready', file=sys.stderr)
                return 0
            print('talky: service unavailable; launch talky app first', file=sys.stderr)
            return 1
    if args.action == 'format':
        raw = sys.stdin.read()
        try:
            command, timeout = config(args.config)
            result, status, _ = format_text(raw, command, timeout)
        except (OSError, ValueError, tomllib.TOMLDecodeError):
            result, status = raw, 'fallback'
        if status == 'fallback':
            print('talky: formatter unavailable; preserving input', file=sys.stderr)
        sys.stdout.write(result)
    else:
        try:
            if args.runs < 1 or args.asr_timeout <= 0:
                raise ValueError('runs and ASR timeout must be positive')
            benchmark(args)
        except (OSError, ValueError, RuntimeError, EOFError, wave.Error, subprocess.TimeoutExpired) as error:
            print(f'talky: benchmark failed ({type(error).__name__})', file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
