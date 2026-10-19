#!/usr/bin/env python3
"""Install/remove only Talky's launcher. No autostart or Voxtype changes."""
import argparse
from pathlib import Path
import shutil
import json
import datetime
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--remove', action='store_true')
parser.add_argument('--keys', action='store_true', help='add separate F8 toggle and Shift+F8 cancel shortcuts')
args = parser.parse_args()
home = Path.home()
binary = home / '.local/bin/talky'
desktop = home / '.local/share/applications/io.talky.App.desktop'
icon = home / '.local/share/icons/hicolor/scalable/apps/io.talky.App.svg'
marker = '# Managed by Talky checkout: ' + str(ROOT)
if args.remove:
    if binary.is_symlink() and binary.resolve() == ROOT / 'talky':
        binary.unlink()
    if desktop.exists() and marker in desktop.read_text():
        desktop.unlink()
    if icon.exists() and icon.read_bytes() == (ROOT / 'assets/talky.svg').read_bytes():
        icon.unlink()
    print('Talky launcher removed. Models and project files retained.')
else:
    if (binary.exists() or binary.is_symlink()) and not (binary.is_symlink() and binary.resolve() == ROOT / 'talky'):
        raise SystemExit('Refusing to replace an existing talky executable.')
    if desktop.exists() and marker not in desktop.read_text():
        raise SystemExit('Refusing to replace an existing desktop entry.')
    if icon.exists() and icon.read_bytes() != (ROOT / 'assets/talky.svg').read_bytes():
        raise SystemExit('Refusing to replace an existing icon.')
    for destination in (binary, desktop, icon):
        destination.parent.mkdir(parents=True, exist_ok=True)
    if not binary.is_symlink():
        binary.symlink_to(ROOT / 'talky')
    # Desktop Exec has its own escaping rules, independent of shell syntax.
    executable = str(ROOT / 'talky').replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    desktop.write_text(f'''[Desktop Entry]
{marker}
Type=Application
Name=Talky
Comment=Local voice dictation for Omarchy
Exec="{executable}" app
Icon=io.talky.App
Terminal=false
Categories=Utility;Accessibility;
StartupNotify=true
StartupWMClass=io.talky.App
''')
    shutil.copyfile(ROOT / 'assets/talky.svg', icon)
    print('Talky is available in your app launcher. No keybindings or services changed.')
if shutil.which('update-desktop-database'):
    subprocess.run(['update-desktop-database', str(desktop.parent)], check=False)

if args.keys:
    config = home / '.config/hypr/bindings.lua'
    begin, end = '-- BEGIN TALKY SHORTCUTS', '-- END TALKY SHORTCUTS'
    before = config.read_text()
    if args.remove:
        if begin in before and end in before:
            start = before.index(begin)
            finish = before.index(end, start) + len(end)
            after = before[:start] + before[finish:].lstrip('\n')
        else:
            after = before
    else:
        bindings = json.loads(subprocess.run(['hyprctl', '-j', 'binds'], capture_output=True,
                                           text=True, check=True).stdout)
        if begin not in before:
            conflicts = [b for b in bindings if b.get('key', '').upper() == 'F8' and b.get('modmask') in (0, 1)]
            if conflicts:
                raise SystemExit('F8 or Shift+F8 is already bound; launcher installed, shortcuts skipped.')
            # Absolute executable path; no dependency on the compositor PATH.
            command = str(ROOT / 'talky')
            after = before.rstrip() + '\n\n' + begin + '\n' + \
                'o.bind("F8", "Talky dictation", ' + json.dumps(command + ' toggle') + ')\n' + \
                'o.bind("SHIFT + F8", "Cancel Talky dictation", ' + json.dumps(command + ' cancel') + ')\n' + end + '\n'
        else:
            after = before
    if after != before:
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup = config.with_name(config.name + '.before-talky-' + stamp)
        shutil.copy2(config, backup)
        config.write_text(after)
        subprocess.run(['hyprctl', 'reload'], check=True, capture_output=True)
        errors = subprocess.run(['hyprctl', 'configerrors'], capture_output=True, text=True, check=True).stdout.strip()
        if errors and errors.lower() not in ('ok', 'no errors', 'no errors found'):
            config.write_text(before)
            subprocess.run(['hyprctl', 'reload'], check=True, capture_output=True)
            raise SystemExit('Hyprland reported errors; restored previous bindings: ' + errors)
        print('Talky shortcuts ' + ('removed.' if args.remove else 'installed: F8 toggle, Shift+F8 cancel.') + ' Backup: ' + str(backup))
