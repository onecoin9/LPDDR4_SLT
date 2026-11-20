"""Manual progress delivery without a pre-existing general DUT snapshot.

All I/O uses the fake board/transport; no hardware or real configuration is read.
"""
import json
from types import SimpleNamespace
import unittest

from app.manualrun import ManualRunner
from app.protocol import HsgCodec, ROLE_SLAVE, CMD_RECORD, DT_STRING, build_frame
from app.ws import Hub
from tests.test_manual_settings import FakeTransport, ready_frame, ack_frame, done_frame
from tests.test_state_api import api
from tests.test_state_lifecycle import Power, until


def progress_frame(pct, step='PL test'):
    body = json.dumps(dict(progress=pct, step=step, stage='PL')).encode()
    return build_frame(ROLE_SLAVE, CMD_RECORD, bytes([1, DT_STRING]) + body)


class ManualProgress(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.md = Power()
        self.md.test_timeout_sec = 600
        self.hub = Hub()
        self.hub.site_ids = [1]
        self.runner = ManualRunner(self.md, self.hub, HsgCodec())
        self.runner._transports = {1: FakeTransport(), 2: FakeTransport()}
        info = SimpleNamespace(enabled=True, info=lambda: dict(duts=[
            dict(dut=d, channel=self.md.ch(d), line=self.md.dut_lines[d-1],
                 powerOn=self.md._power[d]) for d in (1, 2)]))
        self.payload = api('_manual_state_payload', mdbg=info, runner=self.runner)
        self.events = []
        self.runner.on_change = lambda: self.events.append(self.payload())

    async def asyncTearDown(self):
        await self.runner.close()

    async def running(self, dut=1, origin='manual'):
        if origin == 'manual':
            await self.runner.power(dut, True)
        else:
            self.md._power[dut] = True
            self.runner._arm_admitted(dut, cfg_text=self.md.cfg, origin=origin)
        self.runner.on_datagram(dut, ready_frame())
        self.runner.on_datagram(dut, ack_frame())
        self.assertEqual(self.runner.state(dut)['state'], 'running')

    async def test_cold_snapshot_empty_but_manual_tick_delivers_nonzero_progress(self):
        # Field mode skips legacy sessions: the browser initially has no DUT row.
        initial = self.hub.snapshot()
        self.assertEqual(initial['sites'][0]['duts'], [])
        await self.running()
        ctx = self.runner._st[1]
        ctx['aging'] = 50
        ctx['t0'] -= 95
        await until(lambda: self.events[-1]['run']['duts'][0].get('progress') == 3, limit=2.8)
        current = self.events[-1]['run']['duts'][0]
        self.assertEqual((current['channel'], current['step']), (5, '测试运行中'))
        # No browser-side insertion into initial['sites'] is needed for this event.
        self.assertEqual(initial['sites'][0]['duts'], [])

    async def test_reported_progress_and_step_delivered_immediately_per_channel(self):
        await self.running(1)
        await self.running(2)
        self.runner.on_datagram(1, progress_frame(35.4, 'PL pattern'))
        self.runner.on_datagram(2, progress_frame(62, 'LK pattern'))
        runs = self.events[-1]['run']['duts']
        self.assertEqual([(r['channel'], r['progress'], r['step']) for r in runs],
                         [(5, 35, 'PL pattern'), (6, 62, 'LK pattern')])

    async def test_wait_cfg_and_retest_reset_previous_progress(self):
        await self.running()
        self.runner.on_datagram(1, progress_frame(81))
        await self.runner.power(1, False)
        await self.runner.power(1, True)
        wait = self.events[-1]['run']['duts'][0]
        self.assertEqual((wait['progress'], wait['step']), (0, '等待 READY'))
        self.runner.on_datagram(1, ready_frame())
        cfg = self.events[-1]['run']['duts'][0]
        self.assertEqual((cfg['progress'], cfg['step']), (0, '下发配置'))
        self.runner.on_datagram(1, ack_frame())
        self.assertEqual(self.events[-1]['run']['duts'][0]['progress'], 0)

    async def test_only_pass_can_report_100_and_late_progress_cannot_change_it(self):
        await self.running()
        self.runner.on_datagram(1, progress_frame(100))
        self.assertEqual(self.events[-1]['run']['duts'][0]['progress'], 99)
        self.runner.on_datagram(1, done_frame())
        self.assertEqual(self.payload()['run']['duts'][0]['progress'], 100)
        self.runner.on_datagram(1, progress_frame(2))
        self.assertEqual(self.payload()['run']['duts'][0]['progress'], 100)

    async def test_production_progress_keeps_existing_status_stream(self):
        for origin in ('monitor', 'handler'):
            with self.subTest(origin=origin):
                await self.running(origin=origin)
                count = len(self.events)
                self.runner.on_datagram(1, progress_frame(42))
                self.assertEqual(self.hub.ensure(1, 5)['progress'], 42)
                self.assertEqual(len(self.events), count)
                self.assertNotIn('progress', self.payload()['run']['duts'][0])
                self.assertNotIn('step', self.payload()['run']['duts'][0])
                await self.runner.power(1, False)
