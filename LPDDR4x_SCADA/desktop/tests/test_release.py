from pathlib import Path
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.localdata import init_mock_data
from audit_source import check_files
from launch_paths import configure_paths
from stage_payload import stage_payload
from app.settingsstore import SettingsDocument, SettingsStore, read_document
from app.runtimepolicy import atomic_json
from app.cfg import base_cfg
from app.profileplan import ProfileError, require_profile
from release_output import release_output, publish_release


def product_profile(name="CURRENT", algorithm="test_solid_bit"):
    return {"name": name, "rankEnabled": False, "pl1Enabled": True, "pl2Enabled": True,
            "channels": {}, "mr": {}, "params": [],
            "pl2": {"selectedAlgorithms": [algorithm], "patterns": {}}}


class ReleaseTests(unittest.TestCase):
    def test_git_policy_rejects_private_data_and_compiled_output_but_keeps_recipes(self):
        check_files(['backend/app/cfg.py', 'backend/app/protocol.py', 'desktop/release.spec', 'frontend/package-lock.json'])
        for name in ('backend/config.yaml', 'backend/runtime_policy.json', 'backend/settings.json', 'backend/.settings.active',
                     'backend/handler_settings.json', 'backend/manual_debug.cfg', 'bulid_20261012/a.txt', 'build/a.txt',
                     'frontend/dist/assets/index.js', 'backend/products/part.json', 'other/a.dll',
                     'backend/license/license.lic', 'licensing_tools/keys/issuer.private.key'):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                check_files([name])

    def test_release_replaces_fixed_build_removes_old_assets_and_keeps_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            candidate = repo / 'desktop/build/release/dist/package'
            for name in ('LPDDR4x_SCADA_PYD.exe', 'BUILD_REPORT.json',
                         '_internal/new.dll', 'frontend_dist/new.js', 'config.yaml'):
                path = candidate / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('new')
            output = publish_release(candidate, repo)
            (output / '_internal/old.dll').write_text('old')
            (output / 'frontend_dist/old.js').write_text('old')
            (output / 'LPDDR4x_SCADA_PYD.exe').write_text('old')
            log = output / 'manual_logs/run/dut5.log'
            log.parent.mkdir(parents=True)
            log.write_text('keep')
            self.assertEqual(publish_release(candidate, repo), output)
            self.assertEqual(output.name, 'build')
            self.assertEqual((output / 'LPDDR4x_SCADA_PYD.exe').read_text(), 'new')
            self.assertFalse((output / 'BUILD_REPORT.json').exists())
            self.assertFalse((output / '_internal/old.dll').exists())
            self.assertFalse((output / 'frontend_dist/old.js').exists())
            self.assertEqual(log.read_text(), 'keep')
            self.assertEqual(sorted(p.name for p in repo.iterdir()), ['build', 'desktop'])

    def test_release_removes_legacy_internal_report_but_keeps_runtime_data(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            candidate = repo / 'desktop/build/release/dist/package'
            for name in ('LPDDR4x_SCADA_PYD.exe', '_internal/python.dll',
                         'frontend_dist/index.html'):
                path = candidate / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('program')
            output = publish_release(candidate, repo)
            (output / 'BUILD_REPORT.json').write_text('private build paths')
            (output / 'settings.json').write_text('customer settings')
            publish_release(candidate, repo)
            self.assertFalse((output / 'BUILD_REPORT.json').exists())
            self.assertEqual((output / 'settings.json').read_text(), 'customer settings')

    def test_engineering_inputs_rejected_before_existing_release_is_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            candidate = repo / 'desktop/build/release/dist/package'
            for name in ('LPDDR4x_SCADA_PYD.exe', '_internal/python.dll',
                         'frontend_dist/index.html'):
                path = candidate / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('program')
            output = publish_release(candidate, repo)
            (candidate / 'LPDDR4x_SCADA_PYD.exe').write_text('replacement')
            for name in ('_internal/app/protocol.py', 'frontend_dist/assets/index.js.map',
                         'backend/config.json', '.git/config', 'build.ps1'):
                path = candidate / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('engineering')
                with self.subTest(name=name), self.assertRaises(ValueError):
                    publish_release(candidate, repo)
                self.assertEqual((output / 'LPDDR4x_SCADA_PYD.exe').read_text(), 'program')
                path.unlink()
                parent = path.parent
                while parent != candidate and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent

    def test_release_rejects_unrelated_directory_and_outside_output(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            output = repo / 'build'
            output.mkdir()
            (output / 'notes.txt').write_text('keep')
            for requested in (None, str(repo / 'backend'), str(repo.parent / 'build')):
                with self.subTest(requested=requested), self.assertRaises(ValueError):
                    release_output(repo, requested)
            self.assertEqual((output / 'notes.txt').read_text(), 'keep')

    def test_incomplete_release_leaves_previous_package_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            output = repo / 'build'
            (output / '_internal').mkdir(parents=True)
            for name in ('LPDDR4x_SCADA_PYD.exe', 'BUILD_REPORT.json'):
                (output / name).write_text('old')
            candidate = repo / 'desktop/build/release/dist/package'
            candidate.mkdir(parents=True)
            with self.assertRaises(ValueError):
                publish_release(candidate, repo)
            self.assertEqual((output / 'LPDDR4x_SCADA_PYD.exe').read_text(), 'old')

    def test_field_payload_uses_product_cfg_and_preserves_inactive_legacy_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = init_mock_data(str(root / 'data'))
            cfg = yaml.safe_load((source / 'config.yaml').read_text())
            cfg['manual_debug'].update(enabled=True, run_mode='full_run', scheme='')
            cfg['manual_debug']['board_host'] = '192.0.2.123'
            (source / 'config.yaml').write_text(yaml.safe_dump(cfg))
            external = root / 'current.cfg'
            external.write_text('P2Mask=0x123\nFreq=3733\nAgingTime=50\n')
            (source / 'runtime_policy.json').write_text(json.dumps({'cfgAckTimeoutSec': 40}))
            (source / 'session_settings.json').write_text(json.dumps({'cfg_file': str(external), 'log_dir': str(root / 'logs')}))
            profile = product_profile()
            document = SettingsDocument(products={profile['name']: profile}, runtimePolicy={'cfgAckTimeoutSec': 40})
            atomic_json(source / 'settings.json', document.model_dump())
            expected = require_profile(profile, base_cfg(cfg))['cfgText']
            front = root / 'front'; front.mkdir(); (front / 'index.html').write_text('test')
            result = stage_payload(source, root / 'package', front, 'field')
            packed = yaml.safe_load((root / 'package/config.yaml').read_text())
            self.assertEqual(packed['manual_debug']['board_host'], '192.0.2.123')
            self.assertEqual((root / 'package/strategies/current.cfg').read_bytes(), external.read_bytes())
            self.assertEqual((root / 'package/runtime_policy.json').read_bytes(),
                             (source / 'runtime_policy.json').read_bytes())
            self.assertEqual(result['active_cfg_sha256'], hashlib.sha256(expected.encode('utf-8')).hexdigest())
            self.assertEqual(result['active_cfg_source'], 'product')
            self.assertEqual(result['active_product'], 'CURRENT')
            self.assertNotEqual(expected, external.read_text())
            session = json.loads((root / 'package/session_settings.json').read_text())
            self.assertEqual(session['cfg_file'], 'strategies/current.cfg')
            self.assertEqual(session['log_dir'], 'manual_logs')
            external.unlink()
            # Missing unused files no longer block packaging or change the active CFG.
            cfg['manual_debug']['scheme'] = 'deleted-scheme'
            (source / 'config.yaml').write_text(yaml.safe_dump(cfg))
            again = stage_payload(source, root / 'without-legacy', front, 'field')
            self.assertEqual(again['active_cfg_sha256'], result['active_cfg_sha256'])
            self.assertFalse((root / 'without-legacy/strategies/current.cfg').exists())

    def test_field_payload_uses_selected_settings_and_machine_product(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = init_mock_data(str(root / 'data'))
            cfg = yaml.safe_load((source / 'config.yaml').read_text())
            cfg['manual_debug'].update(enabled=True, run_mode='full_run')
            (source / 'config.yaml').write_text(yaml.safe_dump(cfg))
            (source / 'session_settings.json').write_text('{}')
            first = product_profile('FIRST')
            selected = product_profile('SELECTED', 'test_random_value')
            document = SettingsDocument(products={'FIRST': first, 'SELECTED': selected})
            external = root / 'selected-settings.json'
            atomic_json(external, document.model_dump())
            SettingsStore(source, cfg).select(external, document)
            atomic_json(source / 'machine_settings.json', {'product': 'SELECTED'})
            front = root / 'front'; front.mkdir()
            result = stage_payload(source, root / 'package', front, 'field')
            expected = require_profile(selected, base_cfg(cfg))['cfgText']
            self.assertEqual(result['active_product'], 'SELECTED')
            self.assertEqual(result['active_cfg_sha256'], hashlib.sha256(expected.encode()).hexdigest())
            self.assertEqual(read_document(root / 'package/settings.json'), document)
            # Same startup fallback as main.py if the previous product no longer exists.
            atomic_json(source / 'machine_settings.json', {'product': 'REMOVED'})
            fallback = stage_payload(source, root / 'fallback', front, 'field')
            self.assertEqual(fallback['active_product'], 'FIRST')

    def test_invalid_selected_product_never_falls_back_to_legacy_cfg(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = init_mock_data(str(root / 'data'))
            cfg = yaml.safe_load((source / 'config.yaml').read_text())
            cfg['manual_debug'].update(enabled=True, run_mode='full_run')
            (source / 'config.yaml').write_text(yaml.safe_dump(cfg))
            (source / 'session_settings.json').write_text('{}')
            document = SettingsDocument(products={'FIRST': product_profile('FIRST'),
                'BROKEN': product_profile('BROKEN', 'unknown-algorithm')})
            atomic_json(source / 'settings.json', document.model_dump())
            atomic_json(source / 'machine_settings.json', {'product': 'BROKEN'})
            front = root / 'front'; front.mkdir()
            with self.assertRaises(ProfileError):
                stage_payload(source, root / 'invalid', front, 'field')
            self.assertFalse((root / 'invalid').exists())
            atomic_json(source / 'settings.json', SettingsDocument().model_dump())
            with self.assertRaisesRegex(ValueError, 'valid selected product'):
                stage_payload(source, root / 'empty', front, 'field')
            self.assertFalse((root / 'empty').exists())

    def test_invalid_runtime_policy_rejected_before_package_written(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = init_mock_data(str(root / 'data'))
            (source / 'runtime_policy.json').write_text('{"checkReadyVersion": true}')
            front = root / 'front'
            front.mkdir()
            with self.assertRaises(ValueError):
                stage_payload(source, root / 'package', front, 'mock')
            self.assertFalse((root / 'package').exists())

    def test_launch_respects_cli_and_environment_before_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('cli', 'env', 'exe'):
                init_mock_data(str(root / name))
            with patch.dict(os.environ, {'SLT_DATA_DIR': str(root / 'env')}, clear=True):
                configure_paths(str(root / 'exe'), str(root / 'backend'))
                self.assertEqual(os.environ['SLT_DATA_DIR'], str(root / 'env'))
                configure_paths(str(root / 'exe'), str(root / 'backend'), str(root / 'cli'))
                self.assertEqual(os.environ['SLT_DATA_DIR'], str(root / 'cli'))

    def test_selected_settings_pack_as_portable_json_without_external_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = init_mock_data(str(root / 'data'))
            external = root / 'chosen.json'
            document = SettingsDocument(basic={"theme": "nord"}, handler={"rx_port": 7012},
                                        runtimePolicy={"cfgAckTimeoutSec": 44})
            atomic_json(external, document.model_dump())
            store = SettingsStore(source, {})
            store.select(external, document)
            # Stale legacy policy must not override a selected, valid settings file.
            (source / 'runtime_policy.json').write_text('broken')
            front = root / 'front'; front.mkdir()
            stage_payload(source, root / 'package', front, 'mock')
            self.assertEqual(read_document(root / 'package/settings.json'), document)
            self.assertFalse((root / 'package/.settings.active').exists())
