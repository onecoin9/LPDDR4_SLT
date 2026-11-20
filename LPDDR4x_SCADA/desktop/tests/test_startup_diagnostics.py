import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from startup_diagnostics import run_with_diagnostics
from desktop import wait_for_backend


class StartupDiagnosticsTests(unittest.TestCase):
    def test_frozen_port_conflict_is_logged_and_explained(self):
        def failed():
            print('OSError: [WinError 10048] Address already in use', file=sys.stderr)
            raise RuntimeError('Backend startup failed')
        before = sys.stdout, sys.stderr
        with tempfile.TemporaryDirectory() as d, patch.object(sys, 'frozen', True, create=True), patch('startup_diagnostics.show_failure') as alert:
            self.assertEqual(run_with_diagnostics(failed, d), 1)
            file = next(Path(d, 'startup_logs').glob('*.log'))
            self.assertIn('10048', file.read_text('utf-8'))
            self.assertIn('通讯端口已被占用', alert.call_args.args[0])
            self.assertIn(str(file), alert.call_args.args[0])
        self.assertEqual((sys.stdout, sys.stderr), before)

    def test_missing_config_is_caught_before_application_import(self):
        with tempfile.TemporaryDirectory() as d, patch('startup_diagnostics.show_failure') as alert:
            def failed():
                raise FileNotFoundError('Missing config.yaml')
            self.assertEqual(run_with_diagnostics(failed, d), 1)
            self.assertIn('找不到运行配置', alert.call_args.args[0])
            self.assertIn('Missing config.yaml', next(Path(d, 'startup_logs').glob('*.log')).read_text('utf-8'))

    def test_unattended_failure_still_records_traceback(self):
        with tempfile.TemporaryDirectory() as d, patch('startup_diagnostics.show_failure') as alert:
            self.assertEqual(run_with_diagnostics(lambda: 0, d), 0)
            def failed():
                raise ValueError('invalid startup configuration')
            self.assertEqual(run_with_diagnostics(failed, d, show_dialog=False), 1)
            alert.assert_not_called()
            self.assertIn('invalid startup configuration', next(Path(d, 'startup_logs').glob('*.log')).read_text('utf-8'))

    def test_dead_backend_thread_fails_without_waiting_for_timeout(self):
        thread = Mock()
        thread.is_alive.return_value = False
        with patch('desktop.time.sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, '后端启动失败'):
                wait_for_backend(Mock(started=False), thread)
            sleep.assert_not_called()
