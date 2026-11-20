"""Production REST/Handler flows; real code, fake board, no hardware I/O."""
import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.fieldtest import FieldTests
from app.manualrun import ManualRunner
from tests import test_profile_api as api_fixture
from tests.test_profileplan import valid_profile
from tests.test_state_lifecycle import Power, until
from tests.test_manual_settings import FakeTransport, ready_frame, ack_frame, done_frame


class FieldProductionApi(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await api_fixture.ProductApiTests.asyncSetUp(self)
        self.md = Power()
        self.md.enabled = True
        self.md.board_state = lambda: {'ok': True, 'state': 'NONE'}
        self.main.mdbg = self.md
        self.main.runner = ManualRunner(self.md, self.main.hub)
        self.main.runner._transports = {1: FakeTransport(), 2: FakeTransport()}
        self.main.runner.record_sink = self.main.recorder
        self.main.runner.production_policy_provider = self.main.run_policy_store.snapshot
        self.main.runner.on_production_result = lambda *a: self.main.seq.on_result(*a) if self.main.seq.on_result else None
        self.main.field_tests = FieldTests({'sites': {'mode': 'legacy'}}, self.main.runner, self.main.seq)
        self.reset = patch('app.manualrun.PRODUCTION_RESET_SEC', .01)
        self.reset.start()
        self.p = valid_profile()
        result = await self.client.post('/api/config', json={'product': self.p['name'], 'profile': self.p})
        self.assertEqual(result.status_code, 200)
        self.expected = result.json()['plan']['cfgText']

    async def asyncTearDown(self):
        await self.main.field_tests.stop()
        await self.main.runner.close()
        self.reset.stop()
        await api_fixture.ProductApiTests.asyncTearDown(self)

    async def powered(self, d=1):
        await until(lambda: self.md._power[d] and not self.main.runner._st[d].get('power_pending'))

    def complete(self, d=1):
        r = self.main.runner
        r.on_datagram(d, ready_frame()); r.on_datagram(d, ack_frame()); r.on_datagram(d, done_frame())

    async def test_home_config_start_pass_updates_snapshot_and_records(self):
        r = await self.client.post('/api/test/start', json={})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['started'], [[1, 5], [1, 6]])
        await self.powered(2)
        self.complete(1); self.complete(2)
        for d in (1, 2):
            self.assertEqual(self.main.runner._st[d]['cfg'], self.expected)
            self.assertEqual(self.main.hub.ensure(1, d+4)['state'], 'PASS')
        self.assertTrue(list(Path(self.tmp.name).rglob('summary.csv')))

    async def test_single_channel_and_stop_do_not_touch_other_channel(self):
        r = await self.client.post('/api/test/start', json={'site': 1, 'slots': [6]})
        self.assertEqual(r.json()['started'], [[1, 6]])
        await self.powered(2)
        stopped = await self.client.post('/api/test/stop', json={'site': 1})
        self.assertEqual(stopped.json()['stopped'], [[1, 6]])
        self.assertTrue(all(ch == 6 for ch, _ in self.md.calls))
        self.assertFalse(self.md._power[2])

    async def test_unconfigured_site_or_channel_does_not_touch_board(self):
        for body in ({'site': 2}, {'slots': [1, 5]}):
            r = await self.client.post('/api/test/start', json=body)
            self.assertEqual(r.status_code, 400)
        self.assertFalse(self.md.calls)

    async def test_invalid_product_and_scan_reservation_block_before_io(self):
        r = await self.client.post('/api/config', json={'product': self.p['name'],
                    'profile': valid_profile(pl2={'selectedAlgorithms': []})})
        self.assertEqual(r.status_code, 422)
        owner = object(); self.main.seq.reserve(owner)
        r = await self.client.post('/api/test/start', json={})
        self.assertEqual(r.status_code, 409)
        self.main.seq.release(owner)
        self.assertFalse(self.md.calls)

    async def test_handler_uses_same_transport_and_collects_production_result(self):
        self.assertEqual(self.main._site_flags(1)[4:6], '11')
        r = json.loads(await self.main.handler._dispatch(json.dumps({'method': 'teststart', 'data': {
            'bibid': 1, 'sites': [{'siteid': 5, 'IsEnable': True}]}}).encode()))
        self.assertEqual(r['status'], 'success')
        await self.powered()
        self.complete()
        method, data = self.main.handler._tx_queue.get_nowait()
        self.assertEqual(method, 'testend')
        self.assertEqual(data['sites'], [{'siteid': 5, 'result': 1}])
        self.main.handler._tx_queue.task_done()
        self.assertEqual(self.main.runner._st[1]['origin'], 'handler')

    async def test_repeat_click_keeps_active_run_and_returns_conflict(self):
        first = await self.client.post('/api/test/start', json={})
        self.assertEqual(first.status_code, 200)
        serials = [self.main.runner.state(d)['runId'] for d in (1, 2)]
        second = await self.client.post('/api/test/start', json={})
        self.assertEqual(second.status_code, 409)
        self.assertEqual([self.main.runner.state(d)['runId'] for d in (1, 2)], serials)

    async def test_manual_mode_change_cannot_disarm_production_run(self):
        await self.client.post('/api/test/start', json={})
        r = await self.client.post('/api/manual/settings', json={'runMode': 'power_only'})
        self.assertEqual(r.status_code, 409)
        self.assertTrue(all(self.main.runner.state(d)['state'] == 'wait_ready' for d in (1, 2)))
