import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
import yaml
from app.localdata import backend_data_dir, init_mock_data


class LocalDataTests(unittest.TestCase):
    def test_generated_mock_data_assembles_the_actual_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            init_mock_data(directory, site=351, mock_port=45001, log_port=45002)
            result = subprocess.run([sys.executable, '-B', '-c',
                'from app.main import conns,cplane,mdbg,CFG; assert not cplane.cb_enabled; assert not mdbg.enabled; assert conns.hub.site_ids == [351]'],
                env={**os.environ, 'SLT_DATA_DIR': directory}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_mock_init_is_hardware_disabled_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            data = init_mock_data(directory)
            cfg = yaml.safe_load((data / 'config.yaml').read_text(encoding='utf-8'))
            for name in ('manual_debug', 'commboard', 'tempctrl', 'handler'):
                self.assertFalse(cfg[name]['enabled'])
            self.assertTrue(all(slot['ip'] == '127.0.0.1' for site in cfg['sites'] for slot in site['slots']))
            original = (data / 'config.yaml').read_bytes()
            with self.assertRaises(FileExistsError):
                init_mock_data(directory)
            self.assertEqual(original, (data / 'config.yaml').read_bytes())

    def test_explicit_data_dir_wins_over_existing_private_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_mock_data(str(root / 'local_data'))
            with patch.dict(os.environ, {'SLT_DATA_DIR': str(root / 'explicit')}):
                self.assertEqual(backend_data_dir(str(root / 'backend')), str(root / 'explicit'))
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(backend_data_dir(str(root / 'backend')), str(root / 'local_data'))
