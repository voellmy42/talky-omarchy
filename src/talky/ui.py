"""Native GTK4 control window. The service owns the separate recording HUD."""
import json
from pathlib import Path
import subprocess
import threading
import time

from .settings import DEFAULT_CONFIG, ROOT, Settings
from .service import ACTIVE, request

CSS = '''
window { background: #11171a; color: #e8f0ed; }
headerbar { background: #11171a; border: none; box-shadow: none; }
.brand { font-size: 15px; font-weight: 700; letter-spacing: 3px; color: #91b3a6; }
.hero { font-size: 36px; font-weight: 700; letter-spacing: -1px; }
.muted { color: #91a29d; font-size: 14px; }
.eyebrow { color: #99c9b6; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
.card { background: #1b2427; border: 1px solid #2d3b3c; border-radius: 18px; padding: 22px; }
button { background: #243235; color: #e5eeeb; border: none; border-radius: 10px; padding: 10px 18px; box-shadow: none; }
button:hover { background: #32494a; }
button.primary { background: #b4f1d4; color: #10251d; font-weight: 700; padding: 14px 24px; }
button.primary:hover { background: #cef9e6; }
button.destructive { background: #593338; color: #ffced2; }
textview, textview text { background: #1b2427; color: #e8f0ed; font-size: 16px; }
entry { background: #243235; color: #e8f0ed; border-radius: 8px; padding: 8px; }
dropdown { background: #243235; border-radius: 8px; }
.status { font-size: 20px; font-weight: 600; }
'''


def run_app(config_path=None):
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, Gdk, Gio, GLib
    class TalkyApp(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='io.talky.App', flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
            self.window = None
            self.snapshot = {}
            self.polling = False
            self.last_text = None
            self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG
            self.countdown = 0
            self.service_process = None

        def do_activate(self):
            if self.window is not None:
                self.window.present()
                self.ensure_service()
                return
            provider = Gtk.CssProvider()
            provider.load_from_string(CSS)
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.window = Gtk.ApplicationWindow(application=self, title='Talky')
            self.window.set_default_size(660, 760)
            self.window.connect('close-request', self.on_close)
            header = Gtk.HeaderBar()
            header.set_title_widget(Gtk.Label(label='TALKY', css_classes=['brand']))
            self.window.set_titlebar(header)
            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20,
                            margin_start=30, margin_end=30, margin_top=16, margin_bottom=28)
            self.window.set_child(outer)
            outer.append(Gtk.Label(label='YOUR VOICE. YOUR MACHINE.', xalign=0, css_classes=['eyebrow']))
            outer.append(Gtk.Label(label='Think it. Say it.', xalign=0, css_classes=['hero']))
            outer.append(Gtk.Label(label='Local dictation for wherever you write.', xalign=0, css_classes=['muted']))

            recording = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, css_classes=['card'])
            outer.append(recording)
            self.state_label = Gtk.Label(label='Getting ready…', xalign=0, css_classes=['status'])
            recording.append(self.state_label)
            self.wave = Gtk.DrawingArea(content_height=52)
            self.wave.set_draw_func(self.draw_wave)
            recording.append(self.wave)
            self.message = Gtk.Label(label='Loading local models', xalign=0, wrap=True, css_classes=['muted'])
            recording.append(self.message)
            buttons = Gtk.Box(spacing=10)
            recording.append(buttons)
            self.record_button = Gtk.Button(label='Start dictation', css_classes=['primary'])
            self.record_button.connect('clicked', self.record)
            buttons.append(self.record_button)
            self.cancel_button = Gtk.Button(label='Cancel')
            self.cancel_button.connect('clicked', lambda *_: self.send('cancel'))
            buttons.append(self.cancel_button)
            self.preview_switch = Gtk.CheckButton(label='Preview here instead of pasting')
            self.preview_switch.set_active(True)
            recording.append(self.preview_switch)

            options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            expander = Gtk.Expander(label='Language, cleanup & vocabulary')
            expander.set_child(options)
            outer.append(expander)
            row = Gtk.Box(spacing=16, margin_top=12)
            options.append(row)
            row.append(Gtk.Label(label='Language', hexpand=True, xalign=0))
            self.languages = Gtk.DropDown.new_from_strings(['Auto · EN / DE / Swiss German', 'English', 'German / Swiss German'])
            settings = Settings.load(self.config_path)
            self.languages.set_selected(('auto', 'en', 'de').index(settings.language))
            row.append(self.languages)
            row = Gtk.Box(spacing=16)
            row.append(Gtk.Label(label='Local cleanup', hexpand=True, xalign=0))
            self.cleanup_switch = Gtk.Switch(active=settings.cleanup, valign=Gtk.Align.CENTER)
            self.cleanup_switch.connect('notify::active', lambda widget, *_: self.send('cleanup', enabled=widget.get_active()))
            row.append(self.cleanup_switch)
            options.append(row)
            self.vocabulary = Gtk.Entry(placeholder_text='Names and technical terms, separated by commas')
            self.vocabulary.set_text(', '.join(settings.vocabulary))
            options.append(self.vocabulary)
            save = Gtk.Button(label='Save settings & reload models')
            save.connect('clicked', self.save_settings)
            options.append(save)
            self.model_label = Gtk.Label(label='All processing stays on this computer.', xalign=0, wrap=True, css_classes=['muted'])
            options.append(self.model_label)

            transcript = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, css_classes=['card'], vexpand=True)
            outer.append(transcript)
            row = Gtk.Box(spacing=12)
            row.append(Gtk.Label(label='LATEST DICTATION', xalign=0, hexpand=True, css_classes=['eyebrow']))
            copy_button = Gtk.Button(label='Copy')
            copy_button.connect('clicked', lambda *_: self.send('copy'))
            row.append(copy_button)
            clear = Gtk.Button(label='Clear')
            clear.connect('clicked', lambda *_: self.send('clear'))
            row.append(clear)
            transcript.append(row)
            self.text = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                     vexpand=True, top_margin=4, bottom_margin=4)
            scroll = Gtk.ScrolledWindow(min_content_height=110, vexpand=True)
            scroll.set_child(self.text)
            transcript.append(scroll)
            self.raw_expander = Gtk.Expander(label='Original transcription')
            self.raw_label = Gtk.Label(xalign=0, wrap=True, selectable=True, css_classes=['muted'])
            self.raw_expander.set_child(self.raw_label)
            transcript.append(self.raw_expander)
            self.timing_label = Gtk.Label(xalign=0, wrap=True, css_classes=['muted'])
            transcript.append(self.timing_label)
            footer = Gtk.Box(spacing=12)
            footer.append(Gtk.Label(label='No cloud · No saved recordings · No auto-submit', hexpand=True, xalign=0, css_classes=['muted']))
            quit_button = Gtk.Button(label='Quit Talky')
            quit_button.connect('clicked', self.quit_talky)
            footer.append(quit_button)
            outer.append(footer)
            GLib.timeout_add(120, self.poll)
            self.window.present()
            self.ensure_service()

        def ensure_service(self):
            def start():
                try:
                    request()
                except (OSError, RuntimeError, ValueError):
                    self.service_process = subprocess.Popen([str(ROOT / 'talky'), 'daemon', '--config', str(self.config_path)],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            threading.Thread(target=start, daemon=True).start()

        def send(self, command, **parameters):
            def work():
                try:
                    result = request(command, **parameters)
                    if result.get('error'):
                        GLib.idle_add(self.message.set_text, result['error'])
                except (OSError, ValueError, RuntimeError):
                    GLib.idle_add(self.message.set_text, 'Talky service unavailable. Restart the app to retry.')
            threading.Thread(target=work, daemon=True).start()

        def record(self, *_):
            if self.countdown:
                self.countdown = 0
                self.record_button.set_label('Start dictation')
                return
            if self.snapshot.get('state') in {'starting', 'recording'}:
                self.send('stop')
                return
            # In paste mode, give the user time to focus the destination first.
            if not self.preview_switch.get_active():
                self.countdown = 3
                self.message.set_text('Focus the window you want to dictate into. Starting in 3…')
                self.record_button.set_label('Cancel countdown')
                GLib.timeout_add(1000, self.tick_countdown)
            else:
                self.send('start', preview=True)

        def tick_countdown(self):
            if not self.countdown:
                return False
            self.countdown -= 1
            if self.countdown:
                self.message.set_text(f'Focus your destination. Starting in {self.countdown}…')
                return True
            self.send('start', preview=False)
            return False

        def poll(self):
            if self.polling:
                return True
            self.polling = True
            def work():
                try:
                    result = request()
                    GLib.idle_add(self.update, result)
                except (OSError, RuntimeError, ValueError):
                    pass
                finally:
                    self.polling = False
            threading.Thread(target=work, daemon=True).start()
            return True

        def update(self, snapshot):
            if 'state' not in snapshot:
                return False
            self.snapshot = snapshot
            state = snapshot['state']
            names = {'loading': 'Getting ready…', 'ready': 'Ready when you are', 'starting': 'Opening microphone…',
                     'recording': f'Listening · {int(snapshot["elapsed"])}s', 'transcribing': 'Finding the words…',
                     'formatting': 'Finishing touches…', 'inserted': 'Words delivered', 'clipboard': 'Ready to paste',
                     'preview': 'Your words, ready', 'cancelling': 'Cancelling…', 'error': 'Let’s fix that'}
            self.state_label.set_text(names.get(state, state))
            if not self.countdown:
                self.message.set_text(snapshot['message'])
                self.record_button.set_label('Finish dictation' if state in {'starting', 'recording'} else 'Start dictation')
            self.record_button.set_sensitive(state not in {'loading', 'transcribing', 'formatting', 'cancelling', 'error'})
            self.cancel_button.set_sensitive(state in ACTIVE)
            text = snapshot.get('text', '')
            if text != self.last_text:
                self.text.get_buffer().set_text(text)
                self.last_text = text
            self.raw_label.set_text(snapshot.get('raw', ''))
            self.raw_expander.set_visible(bool(text and snapshot.get('raw') != text))
            timings = snapshot.get('timings', {})
            items = []
            if 'final_transcription_seconds' in timings:
                items.append(f'Final ASR {timings["final_transcription_seconds"]:.2f}s')
                items.append(f'Cleanup {timings["formatting_seconds"]:.2f}s · {snapshot.get("cleanup_status", "raw")}')
            if 'release_to_paste_sent_seconds' in timings:
                items.append(f'Finish → paste sent {timings["release_to_paste_sent_seconds"]:.2f}s')
            self.timing_label.set_text('  /  '.join(items))
            self.model_label.set_text(f'Whisper local · Cleanup {snapshot.get("formatter", "unavailable")}\nEnglish / German / Swiss German · Dialect quality needs evaluation')
            self.wave.queue_draw()
            return False

        def draw_wave(self, area, context, width, height):
            values = self.snapshot.get('levels', [0] * 36)
            recording = self.snapshot.get('state') == 'recording'
            context.set_source_rgb(.63, .9, .77) if recording else context.set_source_rgb(.29, .4, .37)
            count = len(values) or 36
            spacing = width / count
            for index, value in enumerate(values):
                bar = max(3, value * (height - 6)) if recording else 3
                context.rectangle(index * spacing + 1, (height - bar) / 2, max(1, spacing - 3), bar)
                context.fill()

        def save_settings(self, *_):
            if self.snapshot.get('state') in ACTIVE or self.countdown:
                self.message.set_text('Finish or cancel dictation before reloading settings.')
                return
            settings = Settings.load(self.config_path)
            settings.language = ('auto', 'en', 'de')[self.languages.get_selected()]
            settings.cleanup = self.cleanup_switch.get_active()
            settings.vocabulary = [x.strip() for x in self.vocabulary.get_text().split(',') if x.strip()]
            self.config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            values = vars(settings)
            def encode(value):
                return str(value).lower() if isinstance(value, bool) else json.dumps(value, ensure_ascii=False)
            self.config_path.write_text('\n'.join(f'{key} = {encode(value)}' for key, value in values.items()) + '\n')
            self.config_path.chmod(0o600)
            def reload():
                try:
                    request('shutdown')
                    for _ in range(60):
                        time.sleep(.1)
                        try:
                            request()
                        except (OSError, ValueError, RuntimeError):
                            break
                    self.ensure_service()
                except (OSError, ValueError, RuntimeError):
                    self.ensure_service()
            threading.Thread(target=reload, daemon=True).start()
            self.message.set_text('Reloading local models…')

        def on_close(self, *_):
            self.window.set_visible(False)
            return True

        def quit_talky(self, *_):
            self.countdown = 0
            try:
                request('shutdown')
            except (OSError, ValueError, RuntimeError):
                pass
            self.quit()

    app = TalkyApp()
    return app.run([])
