"""Shared editor/monitor/manual contract; loopback APIs and fake power/UDP only."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from app.cfg import parse_cfg
from app.fieldtest import FieldTests
from app.manualrun import ManualRunner
from app.protocol import HsgCodec, StartTest
from app.settingsstore import revision
from tests import test_profile_api as fixture
from tests.test_manual_settings import FakeTransport, ready_frame, ack_frame, done_frame
from tests.test_profileplan import valid_profile
from tests.test_state_lifecycle import Sink, until


class SharedProductCfgApi(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixture.ProductApiTests.asyncSetUp(self)
        self.md = self.main.mdbg
        self.md.enabled = True
        self.md.dut_lines, self.md.dut_channels = [4, 5], [5, 6]
        self.md._power = {1: False, 2: False}
        self.md.run_mode, self.md.ready_timeout_sec = 'full_run', 5
        self.md.file_sink = Sink()
        self.md.board_state = lambda: {'ok': True, 'state': 'NONE'}
        self.calls = []

        def power(d, on):
            self.calls.append((d, on))
            self.md._power[d] = on
            return {'dut': d, 'powerOn': on}

        self.md.set_power = power
        self.md.set_power_all = lambda on: [power(d, on) for d in self.md._power]
        self.main.runner = ManualRunner(self.md, self.main.hub, HsgCodec())
        self.r = self.main.runner
        self.r._transports = {1: FakeTransport(), 2: FakeTransport()}
        self.r.record_sink = self.main.recorder
        self.r.production_policy_provider = self.main.run_policy_store.snapshot
        self.main.field_tests = FieldTests({'sites': {'mode': 'legacy'}}, self.r, self.main.seq)
        self.reset = patch('app.manualrun.PRODUCTION_RESET_SEC', .001)
        self.reset.start()
        self.profile = valid_profile(cfgOverrides={'AgingTime': 37, 'DieNum': 2},
            params=[{'name': 'VDD1(mV)', 'value': '1800', 'checked': True}])
        response = await self.client.post('/api/config', json={'product': self.profile['name'], 'profile': self.profile})
        self.assertEqual(response.status_code, 200)
        self.expected = response.json()['plan']['cfgText']
        self.assertEqual(response.json()['settingsRevision'], revision(self.main.settings_store.document))

    async def asyncTearDown(self):
        await self.main.field_tests.stop()
        await self.r.close()
        self.reset.stop()
        await fixture.ProductApiTests.asyncTearDown(self)

    def revision(self):
        return revision(self.main.settings_store.document)

    async def assert_sent_cfg(self, dut, text):
        expected = HsgCodec().encode(StartTest(text))
        await until(lambda: any(packet == expected for packet, _ in self.r._transports[dut].sent))

    async def test_manual_and_monitor_send_identical_product_despite_stale_file(self):
        Path(self.tmp.name, self.md.cfg_file).write_text('Freq=1600\nAgingTime=1\n', encoding='utf-8')
        self.md.scheme = 'missing-old-scheme'
        self.assertEqual(self.md.settings()['cfgContent'], self.expected)
        self.assertEqual(self.md.settings()['cfgProduct'], self.profile['name'])
        response = await self.client.post('/api/manual/power', json={'dut': 1, 'on': True})
        self.assertEqual(response.status_code, 200)
        self.r.on_datagram(1, ready_frame())
        self.assertEqual(self.r._st[1]['cfg'], self.expected)
        await self.assert_sent_cfg(1, self.expected)
        await self.r.power(1, False)
        response = await self.client.post('/api/test/start', json={'slots': [5]})
        self.assertEqual(response.status_code, 200)
        await until(lambda: self.md._power[1] and not self.r._st[1].get('power_pending'))
        self.r.on_datagram(1, ready_frame())
        self.assertEqual(self.r._st[1]['cfg'], self.expected)
        await self.assert_sent_cfg(1, self.expected)
        self.r.on_datagram(1, ack_frame())
        self.r.on_datagram(1, done_frame())
        self.assertEqual(self.r.state(1)['state'], 'pass')

    async def test_cfg_import_updates_product_and_both_next_runs_not_legacy_file(self):
        legacy = Path(self.tmp.name, self.md.cfg_file)
        legacy.write_text('do not change this old file', encoding='utf-8')
        edited = self.expected.replace('AgingTime=37', 'AgingTime=42').replace('VDD1=1800', 'VDD1=1850')
        response = await self.client.post('/api/products/import-cfg', json={
            'product': self.profile['name'], 'cfgText': edited, 'settingsRevision': self.revision()})
        self.assertEqual(response.status_code, 200, response.json())
        saved = self.main.settings_store.document.products[self.profile['name']]
        self.assertEqual(saved['cfgOverrides']['AgingTime'], 42)
        self.assertEqual(parse_cfg(self.md.get_cfg_text())['VDD1'], 1850)
        self.assertEqual(self.md.settings()['cfgContent'], response.json()['preview']['cfgText'])
        self.assertEqual(legacy.read_text(encoding='utf-8'), 'do not change this old file')
        self.assertFalse(self.calls)

    async def test_invalid_or_stale_import_keeps_product_and_files(self):
        previous = copy.deepcopy(self.main.settings_store.document)
        before = Path(self.main.settings_store.path).read_bytes()
        for text, rev, code in ((self.expected+'Unexpected=1\n', self.revision(), 422),
                                (self.expected, 'stale-revision', 409)):
            result = await self.client.post('/api/products/import-cfg', json={
                'product': self.profile['name'], 'cfgText': text, 'settingsRevision': rev})
            self.assertEqual(result.status_code, code)
            self.assertEqual(self.main.settings_store.document, previous)
            self.assertEqual(Path(self.main.settings_store.path).read_bytes(), before)
        self.assertFalse(self.calls)

    async def test_invalid_product_blocks_manual_before_state_logs_or_power(self):
        previous = self.r._st[1]
        self.main.machine.product = 'missing'
        result = await self.client.post('/api/manual/power', json={'dut': 1, 'on': True})
        self.assertEqual(result.status_code, 409)
        self.assertIs(self.r._st[1], previous)
        self.assertEqual(self.md.file_sink.events, [])
        self.assertFalse(self.calls)

    async def test_cfg_file_settings_cannot_bypass_shared_product(self):
        previous = self.md.board_host
        result = await self.client.post('/api/manual/settings', json={'boardHost': '192.0.2.22', 'cfgContent': 'Freq=1600'})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.md.board_host, previous)
        self.assertFalse(self.calls)

    async def test_selected_cfg_file_reads_and_saves_the_shared_product(self):
        selected = Path(self.tmp.name, 'selected.cfg')
        edited = self.expected.replace('AgingTime=37', 'AgingTime=48')
        selected.write_text(edited, encoding='utf-8')
        read = await self.main.api_manual_read_file(str(selected))
        self.assertEqual(read['content'], edited)
        imported = await self.client.post('/api/products/import-cfg', json={
            'product': self.profile['name'], 'cfgText': read['content'], 'settingsRevision': self.revision()})
        self.assertEqual(imported.status_code, 200)
        saved = await self.client.post('/api/manual/cfg_file', json={
            'path': str(selected), 'product': self.profile['name'], 'settingsRevision': self.revision()})
        self.assertEqual(saved.status_code, 200, saved.json())
        self.assertEqual(selected.read_text(encoding='utf-8'), self.md.get_cfg_text())
        self.assertEqual(self.md.settings()['cfgFile'], str(selected))
        self.assertEqual(parse_cfg(self.md.get_cfg_text())['AGINGTIME'], 48)
        self.assertFalse(self.calls)

    async def test_cfg_file_save_writes_customer_text_verbatim(self):
        # 2026-11-18 契约：保存写回用户编辑原文（注释、键序、字面格式全保留），
        # 产品编译结果仍是唯一下发来源——语义等价由 import-cfg 先行保证。
        selected = Path(self.tmp.name, 'verbatim.cfg')
        selected.write_text('placeholder', encoding='utf-8')
        draft = ('# customer header\n'
                 + '\n'.join(reversed(self.expected.splitlines()))
                 + '\n# tail comment\n')
        imported = await self.client.post('/api/products/import-cfg', json={
            'product': self.profile['name'], 'cfgText': draft, 'settingsRevision': self.revision()})
        self.assertEqual(imported.status_code, 200, imported.json())
        saved = await self.client.post('/api/manual/cfg_file', json={
            'path': str(selected), 'text': draft,
            'product': self.profile['name'], 'settingsRevision': self.revision()})
        self.assertEqual(saved.status_code, 200, saved.json())
        self.assertEqual(selected.read_text(encoding='utf-8'), draft)
        self.assertEqual(saved.json()['cfgContent'], draft)
        self.assertEqual(parse_cfg(selected.read_text(encoding='utf-8')),
                         parse_cfg(self.md.get_cfg_text()))
        self.assertFalse(self.calls)

    async def test_cfg_file_save_rejects_invalid_text_without_overwriting(self):
        selected = Path(self.tmp.name, 'invalid.cfg')
        selected.write_text('unchanged', encoding='utf-8')
        for bad in ('no equals sign\n', self.expected + 'Unexpected=1\n',
                    'Freq=1600\nFreq=2400\n', ''):
            saved = await self.client.post('/api/manual/cfg_file', json={
                'path': str(selected), 'text': bad,
                'product': self.profile['name'], 'settingsRevision': self.revision()})
            self.assertIn(saved.status_code, (400, 422), saved.json())
            self.assertEqual(selected.read_text(encoding='utf-8'), 'unchanged')
        self.assertFalse(self.calls)

    async def test_cfg_file_save_rejects_stale_or_non_cfg_paths_without_overwriting(self):
        for name, rev, code in (('selected.cfg', 'stale', 409), ('source.py', self.revision(), 400)):
            selected = Path(self.tmp.name, name)
            selected.write_text('unchanged', encoding='utf-8')
            saved = await self.client.post('/api/manual/cfg_file', json={
                'path': str(selected), 'product': self.profile['name'], 'settingsRevision': rev})
            self.assertEqual(saved.status_code, code)
            self.assertEqual(selected.read_text(encoding='utf-8'), 'unchanged')
        self.assertFalse(self.calls)

    async def test_product_selection_persists_without_start_or_device_actions(self):
        alternate = valid_profile(name='SECOND', cfgOverrides={'AgingTime': 43})
        saved = await self.client.post('/api/products', json=alternate)
        self.assertEqual(saved.status_code, 200)
        selected = await self.client.post('/api/products/select', json={'product': 'SECOND'})
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(self.md.settings()['cfgProduct'], 'SECOND')
        self.assertEqual(parse_cfg(self.md.get_cfg_text())['AGINGTIME'], 43)
        self.assertIn('SECOND', Path(self.main.MACHINE_CFG_PATH).read_text(encoding='utf-8'))
        bad = await self.client.post('/api/products/select', json={'product': ['bad']})
        self.assertEqual(bad.status_code, 409)
        self.assertEqual(self.main.machine.product, 'SECOND')
        stale = await self.client.post('/api/products/select', json={'product': self.profile['name'], 'settingsRevision': 'stale'})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.main.machine.product, 'SECOND')
        self.assertFalse(self.calls)
        self.assertEqual(self.md.file_sink.events, [])

    async def test_all_manual_channels_take_one_admission_snapshot(self):
        provider = self.md.product_plan_provider
        compiled = []
        def counted():
            plan = provider()
            compiled.append(plan)
            return plan
        self.md.product_plan_provider = counted
        await self.r.power(1, True, all_duts=True)
        self.assertEqual(len(compiled), 1)
        self.assertEqual([self.r._st[d]['cfg'] for d in (1, 2)], [self.expected, self.expected])
        self.assertEqual([self.r._st[d]['aging'] for d in (1, 2)], [37, 37])

    async def test_edit_during_run_freezes_cfg_and_keeps_manual_protection_independent(self):
        self.r.production_policy_provider = lambda: (_ for _ in ()).throw(AssertionError('production policy used'))
        await self.r.power(1, True)
        run = self.r._st[1]
        response = await self.client.post('/api/products/import-cfg', json={
            'product': self.profile['name'], 'cfgText': self.expected.replace('AgingTime=37', 'AgingTime=41'),
            'settingsRevision': self.revision()})
        self.assertEqual(response.status_code, 200, response.json())
        self.assertIs(self.r._st[1], run)
        self.assertEqual(run['cfg'], self.expected)
        self.assertEqual(run['aging'], 37)
        self.r.on_datagram(1, ready_frame())
        await self.assert_sent_cfg(1, self.expected)
        self.assertEqual(parse_cfg(self.md.get_cfg_text())['AGINGTIME'], 41)
