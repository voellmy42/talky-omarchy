"""Independent, service-owned recording HUD. Never opens the control window."""
import fcntl
import os
import subprocess
import threading
import time

from .service import request, runtime_dir
from .settings import ROOT

VISIBLE_STATES = {'starting', 'recording', 'transcribing', 'formatting', 'cancelling'}
CSS = '''
window.talky-overlay { background: transparent; }
.talky-pill { background: #15201f; color: #e8f0ed; border: 1px solid #608b77;
              border-radius: 24px; padding: 10px 16px; }
.talky-pill.recording { border-color: #b4f1d4; }
.talky-pill label { font-size: 14px; font-weight: 600; }
.talky-pill .dot { color: #b4f1d4; font-size: 16px; }
.talky-pill button { background: #263c34; color: #dff6eb; border: none;
                     border-radius: 14px; padding: 6px 12px; box-shadow: none; }
.talky-pill button:hover { background: #375446; }
'''


def presentation(snapshot):
    """UI state is independent of main-window visibility and transcript contents."""
    state = snapshot.get('state', '')
    elapsed = max(0, int(snapshot.get('elapsed', 0)))
    labels = {'starting': 'Opening microphone…',
              'recording': f'Listening · {elapsed // 60}:{elapsed % 60:02}',
              'transcribing': 'Transcribing…', 'formatting': 'Finishing touches…',
              'cancelling': 'Cancelling…'}
    return state in VISIBLE_STATES, labels.get(state, ''), state in {'starting', 'recording'}


class OverlayProcess:
    """Restart a failed HUD without restarting speech recognition or the UI."""
    def __init__(self):
        self.process = None
        self.retry_at = 0

    def poll(self):
        if self.process is not None and self.process.poll() is None:
            return
        if time.monotonic() < self.retry_at:
            return
        self.retry_at = time.monotonic() + 5
        try:
            self.process = subprocess.Popen([str(ROOT / 'talky'), 'overlay'],
                                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            self.process = None

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


def run_overlay(request_fn=request, on_update=None):
    # gtk4-layer-shell must precede libwayland-client in Python's load order.
    # See upstream linking.md; importing its typelib after GTK is too late.
    from ctypes import CDLL
    CDLL('libgtk4-layer-shell.so.0')
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gtk4LayerShell', '1.0')
    from gi.repository import Gtk, Gdk, Gio, GLib, Gtk4LayerShell as Layer

    class Overlay(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='io.talky.Overlay', flags=Gio.ApplicationFlags.NON_UNIQUE)
            self.window = None
            self.snapshot = {}
            self.polling = False
            self.last_seen = time.monotonic()
            self.lock_file = None

        def do_activate(self):
            if self.window is not None:
                return
            if not Layer.is_supported():
                self.quit()
                return
            # The live service and CLI can both request a HUD. Only one owns it.
            runtime = runtime_dir()
            runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.lock_file = (runtime / 'overlay.lock').open('a')
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.quit()
                return
            self.hold()  # Remain alive while the HUD is hidden between recordings.
            provider = Gtk.CssProvider()
            provider.load_from_string(CSS)
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.window = Gtk.Window(application=self, title='Talky recording')
            self.window.add_css_class('talky-overlay')
            self.window.set_resizable(False)
            Layer.init_for_window(self.window)
            Layer.set_namespace(self.window, 'talky-recording')
            Layer.set_layer(self.window, Layer.Layer.OVERLAY)
            Layer.set_keyboard_mode(self.window, Layer.KeyboardMode.NONE)
            Layer.set_anchor(self.window, Layer.Edge.BOTTOM, True)
            Layer.set_margin(self.window, Layer.Edge.BOTTOM, 60)
            self.pill = Gtk.Box(spacing=12, css_classes=['talky-pill'])
            self.window.set_child(self.pill)
            self.spinner = Gtk.Spinner()
            self.dot = Gtk.Label(label='●', css_classes=['dot'])
            self.pill.append(self.dot)
            self.pill.append(self.spinner)
            self.label = Gtk.Label(label='Listening', width_chars=21, xalign=0)
            self.pill.append(self.label)
            self.wave = Gtk.DrawingArea(content_width=112, content_height=28)
            self.wave.set_draw_func(self.draw_wave)
            self.pill.append(self.wave)
            self.stop = Gtk.Button(label='Finish')
            self.stop.set_tooltip_text('Finish dictation (F8)')
            self.stop.connect('clicked', lambda *_: self.send('stop'))
            self.pill.append(self.stop)
            self.cancel = Gtk.Button(label='×')
            self.cancel.set_tooltip_text('Cancel dictation (Shift+F8)')
            self.cancel.connect('clicked', lambda *_: self.send('cancel'))
            self.pill.append(self.cancel)
            GLib.timeout_add(80, self.poll)
            self.poll()

        def send(self, command):
            def work():
                try:
                    request_fn(command)
                except (OSError, RuntimeError, ValueError):
                    pass
            threading.Thread(target=work, daemon=True).start()

        def poll(self):
            if self.polling:
                return True
            self.polling = True
            def work():
                try:
                    # No dictated text is needed in this process.
                    snapshot = request_fn('status', include_text=False)
                    GLib.idle_add(self.update, snapshot)
                except (OSError, RuntimeError, ValueError):
                    GLib.idle_add(self.disconnected)
                finally:
                    self.polling = False
            threading.Thread(target=work, daemon=True).start()
            return True

        def disconnected(self):
            self.window.set_visible(False)
            if time.monotonic() - self.last_seen > 5:
                self.quit()
            return False

        def update(self, snapshot):
            if 'state' not in snapshot:
                return self.disconnected()
            self.last_seen = time.monotonic()
            self.snapshot = snapshot
            visible, label, can_stop = presentation(snapshot)
            recording = snapshot['state'] == 'recording'
            self.label.set_text(label)
            self.stop.set_visible(can_stop)
            self.cancel.set_sensitive(snapshot['state'] != 'cancelling')
            self.dot.set_visible(recording)
            self.spinner.set_visible(visible and not recording)
            self.spinner.set_spinning(visible and not recording)
            if recording:
                self.pill.add_css_class('recording')
            else:
                self.pill.remove_css_class('recording')
            self.window.set_visible(visible)
            self.wave.set_visible(recording)
            self.wave.queue_draw()
            if on_update is not None:
                on_update(self, snapshot)
            return False

        def draw_wave(self, area, context, width, height):
            values = self.snapshot.get('levels') or [0] * 36
            context.set_source_rgb(.70, .95, .83)
            spacing = width / len(values)
            for index, value in enumerate(values):
                bar = max(3, min(1.0, max(0, value)) * (height - 4))
                context.rectangle(index * spacing + .5, (height - bar) / 2,
                                  max(1, spacing - 1), bar)
                context.fill()

    app = Overlay()
    try:
        return app.run([])
    finally:
        if app.lock_file is not None:
            app.lock_file.close()
