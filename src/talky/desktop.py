"""Hyprland app identity and explicit clipboard/paste output."""
import json
import subprocess


def focus():
    try:
        result = subprocess.run(['hyprctl', '-j', 'activewindow'], capture_output=True,
                                text=True, timeout=1, check=True)
        window = json.loads(result.stdout)
        return {'address': window.get('address', ''), 'application': window.get('class', '')}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'address': '', 'application': ''}


def copy(text):
    subprocess.run(['wl-copy', '--type', 'text/plain;charset=utf-8'], input=text, text=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=True)


def deliver(text, target, current=None):
    """Paste only into the original window. Never send an Enter keystroke."""
    copy(text)
    current = focus() if current is None else current
    if not target.get('address') or target['address'] != current.get('address'):
        return 'clipboard', 'Focus changed. Text copied; paste it where you want.'
    terminal = any(name in target.get('application', '').lower() for name in
                   ('alacritty', 'kitty', 'ghostty', 'foot', 'terminal', 'konsole', 'wezterm'))
    command = ['wtype', '-M', 'ctrl']
    if terminal:
        command += ['-M', 'shift']
    command += ['-k', 'v']
    if terminal:
        command += ['-m', 'shift']
    command += ['-m', 'ctrl']
    try:
        subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=3, check=True)
        return 'inserted', 'Paste sent. Ready for your next thought.'
    except (OSError, subprocess.SubprocessError):
        return 'clipboard', 'Typing unavailable. Text copied to your clipboard.'
