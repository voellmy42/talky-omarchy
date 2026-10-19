import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from talky.cli import extract_transcript
from talky.desktop import deliver
from talky.engine import engine_environment
from talky.formatter import safe_candidate
from talky.service import Controller
from talky.settings import Settings


class FakeEngine:
    def __init__(self):
        self.commands = []
        self.current = 'idle'
        self.text = ''
        self.process = None

    def state(self):
        return self.current

    def command(self, command):
        self.commands.append(command)

    def result(self):
        text, self.text = self.text, ''
        return text


class AppTests(unittest.TestCase):
    def make_controller(self, formatter=None):
        engine = FakeEngine()
        formatter = formatter or SimpleNamespace(state='ready', format=lambda text, *_: (text, 'cleaned', .1))
        control = Controller(engine, formatter, Settings())
        control.poll()
        return control

    def test_start_stop_race_waits_for_recording_acknowledgement(self):
        control = self.make_controller()
        with patch('talky.desktop.focus', return_value={'address': 'a', 'application': 'editor'}):
            control.command('start')
        control.command('stop')
        control.poll()  # engine still idle, but a start is in flight
        self.assertEqual(control.state, 'starting')
        self.assertEqual(control.engine.commands, ['start'])
        control.engine.current = 'recording'
        control.poll()
        self.assertEqual(control.engine.commands, ['start', 'stop'])
        self.assertEqual(control.state, 'transcribing')

    def test_cancel_during_cleanup_never_delivers_late_result(self):
        entered, release = threading.Event(), threading.Event()
        def format_later(raw, *_):
            entered.set()
            release.wait(2)
            return 'cleaned', 'cleaned', .1
        control = self.make_controller(SimpleNamespace(state='ready', format=format_later))
        control.state = 'formatting'
        thread = threading.Thread(target=control.finish, args=('raw', control.generation))
        with patch('talky.desktop.deliver') as delivery:
            thread.start()
            self.assertTrue(entered.wait(1))
            control.command('cancel')
            release.set()
            thread.join(2)
            delivery.assert_not_called()
            self.assertEqual(control.text, '')

    def test_focus_change_copies_without_paste(self):
        with patch('talky.desktop.copy') as copy, patch('talky.desktop.subprocess.run') as run:
            result, _ = deliver('private', {'address': 'a'}, {'address': 'b'})
            self.assertEqual(result, 'clipboard')
            copy.assert_called_once_with('private')
            run.assert_not_called()

    def test_multiline_output_uses_paste_without_enter(self):
        with patch('talky.desktop.copy'), patch('talky.desktop.subprocess.run') as run:
            deliver('line one\nline two', {'address': 'a', 'application': 'editor'}, {'address': 'a'})
            command = run.call_args.args[0]
            self.assertEqual(command, ['wtype', '-M', 'ctrl', '-k', 'v', '-m', 'ctrl'])

    def test_preview_does_not_touch_clipboard_or_type(self):
        control = self.make_controller()
        control.preview = True
        with patch('talky.desktop.deliver') as delivery:
            control.finish('original', control.generation)
            delivery.assert_not_called()
        self.assertEqual(control.state, 'preview')
        self.assertEqual(control.text, 'original')

    def test_unrecognized_cli_output_cannot_become_dictation(self):
        self.assertEqual(extract_transcript('Loading audio\nProcessing samples\n\nHallo.\n'), 'Hallo.')
        self.assertEqual(extract_transcript('No speech detected, skipping transcription.\n'), '')
        with self.assertRaises(ValueError):
            extract_transcript('Loading failed')

    def test_sensitive_edit_guards(self):
        self.assertFalse(safe_candidate('Do not delete v1.2.', 'Delete v1.2.'))
        self.assertFalse(safe_candidate('Set port 8080.', 'Set port 80.'))
        self.assertTrue(safe_candidate('um do not delete v1.2', 'Do not delete v1.2.'))
        self.assertTrue(safe_candidate('Ich chume nöd am Mäntig', 'Ich chume nöd am Mäntig.'))

    def test_cleanup_rejects_answers_translation_and_new_commands(self):
        self.assertFalse(safe_candidate('What is the capital of France?', 'The capital of France is Paris.'))
        self.assertFalse(safe_candidate('Bitte nicht ändern.', 'Please do not change.'))
        self.assertFalse(safe_candidate('Write banana', 'banana'))
        self.assertTrue(safe_candidate('The meeting is Tuesday, actually Thursday.', 'The meeting is Thursday.'))
        self.assertFalse(safe_candidate('Is this ready?', 'Is this ready.'))

    def test_engine_environment_isolates_control_and_keeps_audio_runtime(self):
        with patch.dict('os.environ', {'XDG_RUNTIME_DIR': '/run/user/1234', 'VOXTYPE_WHISPER_API_KEY': 'secret'}, clear=True):
            environment = engine_environment(Path('/tmp/isolated'))
        self.assertEqual(environment['XDG_RUNTIME_DIR'], '/tmp/isolated')
        self.assertEqual(environment['PIPEWIRE_RUNTIME_DIR'], '/run/user/1234')
        self.assertNotIn('VOXTYPE_WHISPER_API_KEY', environment)
        self.assertEqual(environment['XDG_DATA_HOME'], '/tmp/isolated/data')


if __name__ == '__main__':
    unittest.main()
