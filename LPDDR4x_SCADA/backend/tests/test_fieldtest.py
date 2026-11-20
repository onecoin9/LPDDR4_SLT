"""Real production admission/state machine with fake board and isolated records."""
import asyncio
import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from app.fieldtest import FieldTests
from app.manualrun import ManualRunner
from app.recorder import Recorder
from app.runtimepolicy import RunPolicy
from app.sequencer import SequencerBusyError
from app.ws import Hub
from tests.test_state_lifecycle import Power, until
from tests.test_manual_settings import FakeTransport, ready_frame, ack_frame, done_frame


class FieldTestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.md, self.hub = Power(), Hub()
        self.md.enabled = True
        self.md.board_state = lambda: {'ok': True, 'state': 'NONE'}
        self.r = ManualRunner(self.md, self.hub)
        self.r._transports = {1: FakeTransport(), 2: FakeTransport()}
        self.r.record_sink = Recorder(self.tmp.name)
        self.seq = SimpleNamespace(reserved=False, boot_timeout_sec=3, test_timeout=20)
        self.field = FieldTests({'sites': {'mode': 'legacy'}}, self.r, self.seq)
        self.reset = patch('app.manualrun.PRODUCTION_RESET_SEC', .01)
        self.reset.start()
        self.results = []
        self.r.on_production_result = lambda *args: self.results.append(args)
        self.cfg = 'Freq=3200\nAgingTime=1\nPatternTest=1\nMemtester=1\n'

    async def asyncTearDown(self):
        await self.r.close()
        self.reset.stop()
        self.tmp.cleanup()

    async def start(self, targets=None, **kw):
        return await self.field.start(targets or [(1, 5)], 'WO-LOT', self.cfg,
                                      {'configurationStatus': 'complete'}, **kw)

    async def powered(self, d=1):
        await until(lambda: self.md._power[d] and not self.r._st[d].get('power_pending'))

    def running(self, d=1):
        self.r.on_datagram(d, ready_frame())
        self.r.on_datagram(d, ack_frame())
        self.assertEqual(self.r.state(d)['state'], 'running')

    async def test_cold_start_uses_only_configured_channels_and_frozen_product_cfg(self):
        self.assertEqual(self.field.available(), [5, 6])
        self.assertFalse(self.hub.ensure(1, 5)['connected'])
        self.assertEqual(await self.start(), [(1, 5)])
        self.assertEqual(self.md.calls, [])  # Handler can register pending before any completion.
        self.assertEqual(self.field.available(), [6])
        self.md.cfg = 'WRONG_MANUAL_CFG=1\n'
        await self.powered()
        self.running()
        sent = self.r._transports[1].sent
        self.assertTrue(any(self.cfg.encode() in packet for packet, _ in sent))
        self.assertFalse(any(b'WRONG_MANUAL' in packet for packet, _ in sent))
        self.assertEqual(self.md.calls, [(5, False), (5, True)])
        self.assertEqual(self.r.state(1)['runLimit'], 20)

    async def test_pass_csv_snapshot_callback_once_and_automatic_power_off(self):
        await self.start(); await self.powered(); self.running()
        self.r.on_datagram(1, done_frame())
        self.r.on_datagram(1, done_frame())
        await until(lambda: not self.md._power[1])
        self.assertEqual(self.results, [(1, 5, 'PASS')])
        with next(Path(self.tmp.name).rglob('summary.csv')).open(encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([(r['batch'], r['slot'], r['result']) for r in rows], [('WO-LOT', '05', 'PASS')])
        record = json.loads(next(Path(self.tmp.name).rglob('*.run.json')).read_text())
        self.assertEqual((record['origin'], record['batch'], record['cfgText']), ('monitor', 'WO-LOT', self.cfg))
        self.assertTrue(record['cfgAcked'])
        self.assertEqual(self.hub.ensure(1, 5)['state'], 'PASS')
        self.assertFalse(self.hub.ensure(1, 5)['connected'])

    async def test_manual_power_only_does_not_disable_explicit_production_test(self):
        self.md.run_mode = 'power_only'
        await self.start(); await self.powered(); self.running()
        self.assertEqual(self.md.run_mode, 'power_only')
        await self.field.stop()
        await self.r.power(2, True)
        self.r.on_datagram(2, ready_frame())
        self.assertEqual(self.r._transports[2].sent, [])

    async def test_production_and_manual_reboot_latch_fail_separately(self):
        await self.start(); await self.powered(); self.running()
        self.r.on_datagram(1, ready_frame())
        self.assertEqual(self.r.state(1)['detail'], 'dut_reboot')
        self.assertEqual(self.results, [(1, 5, 'FAIL')])
        await self.r.power(2, True); self.running(2)
        self.r.on_datagram(2, ready_frame())
        self.assertEqual((self.r.state(2)['state'], self.r.state(2)['detail']),
                         ('fail', 'dut_reboot'))
        self.assertEqual(self.results, [(1, 5, 'FAIL')])  # 手动不进入生产结算

    async def test_stop_before_hardware_starts_never_powers_on(self):
        await self.start()
        self.assertEqual(await self.field.stop(), [(1, 5)])
        await until(lambda: not self.r._effects)
        self.assertNotIn((5, True), self.md.calls)
        self.assertEqual(self.results, [(1, 5, 'CANCEL')])
        self.assertFalse(list(Path(self.tmp.name).rglob('summary.csv')))

    async def test_stop_only_own_production_not_independent_manual_channel(self):
        await self.r.power(2, True)
        await self.start(); await self.powered(); self.running()
        self.assertEqual(await self.field.stop(), [(1, 5)])
        self.assertFalse(self.md._power[1]); self.assertTrue(self.md._power[2])
        self.assertEqual(self.r.state(2)['state'], 'wait_ready')

    async def test_invalid_channel_batch_rejected_before_any_io(self):
        for target in ([(1, 5), (1, 1)], [(2, 5)]):
            with self.assertRaises(HTTPException): await self.start(target)
        self.assertFalse(self.md.calls)
        self.assertFalse(self.r._effects)

    async def test_duplicate_start_does_not_rearm_active_run(self):
        await self.start()
        run_id = self.r.state(1)['runId']
        with self.assertRaises(HTTPException): await self.start()
        self.assertEqual(self.r.state(1)['runId'], run_id)

    async def test_reserved_or_license_denied_has_no_io(self):
        self.seq.reserved = True
        with self.assertRaises(SequencerBusyError): await self.start()
        self.seq.reserved = False
        def deny(): raise RuntimeError('license denied')
        self.r.authorize_start = deny
        with self.assertRaisesRegex(RuntimeError, 'license denied'): await self.start()
        self.assertFalse(self.md.calls)
        self.assertEqual(self.r.state(1)['state'], 'idle')

    async def test_missing_port_or_boot_key_mapping_rejected_before_io(self):
        self.r._transports.pop(1)
        with self.assertRaises(HTTPException): await self.start()
        self.r._transports[1] = FakeTransport()
        with self.assertRaises(HTTPException):
            await self.start(io_control=SimpleNamespace(action='power_key'))
        self.assertFalse(self.md.calls)

    async def test_power_failure_reports_handler_and_never_sends_cfg(self):
        self.md.error = RuntimeError('board timeout')
        await self.start(origin='handler')
        await until(lambda: self.r.state(1)['state'] == 'fail')
        self.assertEqual(self.results, [(1, 5, 'FAIL')])
        self.assertEqual(self.r._transports[1].sent, [])

    async def test_policy_and_cfg_are_frozen_for_whole_batch(self):
        self.r.production_policy_provider = lambda: RunPolicy(cfgAckTimeoutSec=1)
        await self.start([(1, 5), (1, 6)])
        self.r.production_policy_provider = lambda: RunPolicy(cfgAckTimeoutSec=2)
        self.assertEqual([self.r._st[d]['_policy'].cfgAckTimeoutSec for d in (1, 2)], [1, 1])

    async def test_production_still_enforces_its_ready_version_policy(self):
        self.r.production_policy_provider = lambda: RunPolicy(checkReadyVersion=True, expectedReadyVersion='WRONG')
        await self.start(); await self.powered()
        self.r.on_datagram(1, ready_frame())
        self.assertEqual(self.r.state(1)['state'], 'fail')
        self.assertIn('version_mismatch', self.r.state(1)['detail'])
        self.assertFalse(any(packet[0][4] == 0x15 for packet in self.r._transports[1].sent))

    async def test_production_still_rejects_pass_without_required_ack(self):
        self.r.production_policy_provider = lambda: RunPolicy(cfgAckTimeoutSec=.2)
        await self.start(); await self.powered()
        self.r.on_datagram(1, ready_frame())
        self.r.on_datagram(1, done_frame())
        self.assertEqual(self.r.state(1)['detail'], 'cfg_ack_missing')

    async def test_invalid_production_policy_still_blocks_production_before_io(self):
        from app.runtimepolicy import PolicyUnavailable
        def broken(): raise PolicyUnavailable('invalid production policy')
        self.r.production_policy_provider = broken
        with self.assertRaises(PolicyUnavailable): await self.start()
        self.assertFalse(self.md.calls)
        self.assertEqual(self.r.state(1)['state'], 'idle')

    async def test_ready_timeout_and_board_offline_finish_once(self):
        self.seq.boot_timeout_sec = .015
        await self.start()
        await until(lambda: self.r.state(1)['state'] == 'timeout')
        self.r.board_offline()
        self.assertEqual(self.results, [(1, 5, 'FAIL')])

    async def test_stopped_terminal_timing_does_not_keep_counting(self):
        await self.start(); await self.powered(); self.running()
        await self.field.stop()
        stopped = self.hub.ensure(1, 5)['durationSec']
        await asyncio.sleep(.03)
        self.assertEqual(self.hub.ensure(1, 5)['durationSec'], stopped)

    async def test_wait_ready_updates_home_duration_before_cfg_ack(self):
        await self.start(); await self.powered()
        await until(lambda: self.hub.ensure(1, 5)['durationSec'] > 1, limit=2.5)
        self.assertEqual(self.hub.ensure(1, 5)['step'], '等待 READY')
        self.assertEqual(self.hub.ensure(1, 5)['progress'], 0)

    async def test_stop_power_failure_is_red_in_both_views(self):
        await self.start(); await self.powered(); self.running()
        self.md.error = RuntimeError('off failed')
        await self.field.stop()
        self.assertEqual(self.r.state(1)['state'], 'fail')
        self.assertEqual(self.hub.ensure(1, 5)['state'], 'FAIL')
        self.assertIn('off failed', self.r.state(1)['powerError'])

    async def test_boot_keys_use_explicit_advancing_serial_and_only_selected_lines(self):
        from app.commboard import CommBoard
        from app.models import IoControlConfig
        commands = []
        board = CommBoard('192.0.2.1')
        board.mb = SimpleNamespace(write_multiple=lambda addr, regs: commands.append((addr, regs)))
        self.md._client = lambda: board
        self.md.dut_key_lines = [4, 5]
        await self.start([(1, 5), (1, 6)], io_control=IoControlConfig(action='power_key', intervalSec=0))
        await self.powered(2)
        self.assertEqual(len(commands), 2)
        self.assertNotEqual(commands[0][1][1], commands[1][1][1])
        # Exactly one IoControl (four words) per requested line, plus command/serial.
        self.assertEqual([len(regs) for _, regs in commands], [6, 6])

    async def test_manual_power_only_gate_also_covers_previous_terminal_round(self):
        await self.r.power(2, True); self.running(2)
        self.r.on_datagram(2, done_frame())
        self.md.run_mode = 'power_only'
        before = len(self.r._transports[2].sent)
        self.r.on_datagram(2, ready_frame())
        self.assertEqual(len(self.r._transports[2].sent), before)
