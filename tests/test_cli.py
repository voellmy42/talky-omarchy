import subprocess
import sys
import unittest
from talky.cli import format_text


class FormatterTests(unittest.TestCase):
    def test_passthrough_preserves_sensitive_meaning(self):
        raw = 'Do not deploy v1.2. Tuesday, actually Thursday. Grüezi!\n'
        self.assertEqual(format_text(raw, [], 1)[:2], (raw, 'passthrough'))

    def test_failure_and_empty_preserve_input(self):
        for code in ['raise SystemExit(1)', 'print(" ")', 'print("\\x00")']:
            with self.subTest(code=code):
                self.assertEqual(format_text('do not delete', [sys.executable, '-c', code], 1)[:2],
                                 ('do not delete', 'fallback'))

    def test_timeout_preserves_input(self):
        self.assertEqual(format_text('original', [sys.executable, '-c',
                         'import time; time.sleep(10)'], .05)[:2], ('original', 'fallback'))

    def test_missing_binary_preserves_input(self):
        self.assertEqual(format_text('original', ['/nonexistent/talky'], 1)[:2],
                         ('original', 'fallback'))

    def test_stdout_is_only_text_even_on_invalid_config(self):
        result = subprocess.run([sys.executable, '-m', 'talky.cli', 'format', '--config',
                                 '/nonexistent/config'], input='private dictation\n',
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, 'private dictation\n')
        self.assertNotIn('private dictation', result.stderr)


if __name__ == '__main__':
    unittest.main()
