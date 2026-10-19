#!/usr/bin/env python3
"""Verify paste into a dedicated scratch GTK editor; never record audio."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
from talky import desktop

EXPECTED = 'Talky paste test. Do not submit.\nGrüezi, Zürich! Port 8080.'
result = 1
app = Gtk.Application(application_id='io.talky.PasteTest')

def activate(application):
    window = Gtk.ApplicationWindow(application=application, title='Talky — scratch paste test')
    window.set_default_size(620, 260)
    editor = Gtk.TextView()
    window.set_child(editor)
    window.present()
    editor.grab_focus()
    def insert():
        target = desktop.focus()
        if target.get('application') != 'io.talky.PasteTest':
            print('Scratch editor not focused; skipped paste.', flush=True)
            app.quit()
            return False
        status, _ = desktop.deliver(EXPECTED, target)
        def verify():
            global result
            buffer = editor.get_buffer()
            actual = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
            result = 0 if actual == EXPECTED and status == 'inserted' else 1
            print('Scratch paste: ' + ('PASS' if result == 0 else 'FAIL'), flush=True)
            app.quit()
            return False
        GLib.timeout_add(400, verify)
        return False
    GLib.timeout_add(1000, insert)
app.connect('activate', activate)
app.run([])
raise SystemExit(result)
