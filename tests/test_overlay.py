import unittest
from types import SimpleNamespace
from unittest.mock import patch
from talky.overlay import OverlayProcess, presentation
from talky.service import Controller
from talky.settings import Settings


class OverlayTests(unittest.TestCase):
    def test_shows_recording_even_without_a_main_window(self):
        visible, label, can_stop = presentation({'state': 'recording', 'elapsed': 67})
        self.assertTrue(visible)
        self.assertEqual(label, 'Listening · 1:07')
        self.assertTrue(can_stop)

    def test_processing_stays_visible_and_completion_hides_it(self):
        for state in ('starting', 'transcribing', 'formatting', 'cancelling'):
            self.assertTrue(presentation({'state': state})[0], state)
        for state in ('ready', 'inserted', 'clipboard', 'preview', 'error', 'loading'):
            self.assertFalse(presentation({'state': state})[0], state)
        self.assertFalse(presentation({'state': 'formatting'})[2])

    def test_overlay_status_excludes_transcripts(self):
        controller = Controller(SimpleNamespace(), SimpleNamespace(state='ready'), Settings())
        controller.raw = 'private transcript'
        controller.text = 'private final text'
        snapshot = controller.command('status', include_text=False)
        self.assertNotIn('text', snapshot)
        self.assertNotIn('raw', snapshot)
        self.assertIn('levels', snapshot)

    def test_service_restarts_failed_overlay_but_not_healthy_one(self):
        supervisor = OverlayProcess()
        child = SimpleNamespace(poll=lambda: None)
        with patch('talky.overlay.subprocess.Popen', return_value=child) as launch:
            supervisor.poll()
            supervisor.poll()
            launch.assert_called_once()
            self.assertEqual(launch.call_args.args[0][-1], 'overlay')
        supervisor.process = SimpleNamespace(poll=lambda: 1)
        with patch('talky.overlay.subprocess.Popen', return_value=child) as launch:
            supervisor.poll()  # throttle crash loops
            launch.assert_not_called()
            supervisor.retry_at = 0
            supervisor.poll()
            launch.assert_called_once()


if __name__ == '__main__':
    unittest.main()
