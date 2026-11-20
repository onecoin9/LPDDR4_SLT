"""Fixed-unit timing contract, strict bounds and firmware compatibility gates."""
import subprocess
import sys
import unittest
from pathlib import Path

from app.cfg import _DEFAULTS
from app.profileplan import compile_profile
from app.protocol import Ack, HsgCodec, Ready, TestDone, build_frame
from app.timing_catalog import BY_KEY, CATALOG, firmware_error, wire_value
from tests.test_profileplan import valid_profile
from tests import test_runtime_policy as fixtures
from tests.test_state_lifecycle import until
from tests.test_manual_settings import ready_frame, ack_frame, done_frame
from app.runtimepolicy import RunPolicy


def row(key, value, checked=True):
    return dict(name=key, value=str(value), checked=checked)


def compile_rows(rows, **kwargs):
    return compile_profile(valid_profile(timingSchema=1, params=rows, **kwargs), dict(_DEFAULTS))


class TimingCatalogueTests(unittest.TestCase):
    def test_catalogue_generated_frontend_is_current(self):
        root = Path(__file__).resolve().parents[2]
        subprocess.run([sys.executable, '-B', str(root / 'desktop/generate_timing_catalog.py'), '--check'],
                       check=True, capture_output=True)
        self.assertEqual([r['id'] for r in CATALOG], list(range(50)))
        self.assertEqual(len(BY_KEY), 50)

    def test_every_boundary_and_out_of_range_is_enforced_server_side(self):
        for field in CATALOG:
            with self.subTest(key=field['key']):
                for n in (field['min'], field['max']):
                    result = compile_rows([row(field['key'], n)])
                    self.assertTrue(result['valid'], result['errors'])
                    self.assertIn(f"{field['id']}:{n * field['scale']}", result['cfgText'])
                for n in (field['min']-1, field['max']+1):
                    self.assertFalse(compile_rows([row(field['key'], n)])['valid'])

    def test_zero_is_explicit_and_unselected_fields_inherit(self):
        p = compile_rows([row(' TRCD ', 0), row('TRP', '', False)])
        self.assertTrue(p['valid'], p['errors'])
        self.assertIn('TimingRegV=1\nTReg=0:0\n', p['cfgText'])
        self.assertNotIn('TRP=', p['cfgText'])
        self.assertNotIn('TimingRegV', compile_rows([row('TRCD', '', False)])['cfgText'])

    def test_precision_nonfinite_and_huge_exponents_are_rejected(self):
        for key, value in [('TRCD', '1.1'), ('TRCD_05T', 2), ('TRFC', '380.001'),
                           ('TRFC', 'NaN'), ('TRFC', 'Infinity'), ('TRFC', '1e999999999'),
                           ('TRCD', '1e-999999'), ('TRCD', '0x7'), ('TRCD', True),
                           ('TRFC', '380.0000000000000000000000000000000001')]:
            with self.subTest(key=key, value=value):
                self.assertFalse(compile_rows([row(key, value)])['valid'])
        self.assertEqual(wire_value(BY_KEY['TRFC'], '380.01'), 38001)

    def test_duplicate_legacy_mixed_units_and_pending_review_block_start(self):
        cases = [([row('TRCD', 1), row('TRCD', 2)], {}),
                 ([row('TMRW', 2)], {}), ([row('TRCD', 1)], {'timingUnit': 2}),
                 ([], {'timingReviewRequired': True})]
        for rows, extra in cases:
            self.assertFalse(compile_rows(rows, **extra)['valid'])

    def test_all_fields_and_complete_algorithms_fit_one_device_payload(self):
        from app.testplan import ALL_ALGORITHMS
        p = valid_profile(timingSchema=1, params=[row(f['key'], f['max']) for f in CATALOG],
                          pl2=dict(selectedAlgorithms=list(ALL_ALGORITHMS), patterns={}))
        result = compile_profile(p, dict(_DEFAULTS))
        self.assertTrue(result['valid'], result['errors'])
        self.assertLessEqual(result['mcuMessage']['payloadBytes'], 1017)
        self.assertEqual(len(next(s for s in result['cfgText'].splitlines() if s.startswith('TReg=')).split(',')), 50)

    def test_new_ready_ascii_and_existing_binary_protocol_both_decode(self):
        msg = HsgCodec().decode(build_frame(1, 0x10, b'T1:abcdef0 1234\x00'))
        self.assertIsInstance(msg, Ready)
        self.assertEqual(msg.version, 'T1:abcdef0 1234')
        self.assertNotEqual(HsgCodec().decode(ready_frame()).version, msg.version)
        self.assertEqual(firmware_error('TimingRegV=1\nTReg=0:0\n', 'fw:old'), 'timing_firmware_update_required')
        self.assertIsNone(firmware_error('TimingRegV=1\nTReg=0:0\n', msg.version))
        self.assertIsNone(firmware_error('AgingTime=1\n', 'old'))


class TimingAutomaticGateTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.AutomaticPolicyTests.asyncSetUp
    asyncTearDown = fixtures.AutomaticPolicyTests.asyncTearDown
    begin = fixtures.AutomaticPolicyTests.begin
    complete = fixtures.AutomaticPolicyTests.complete
    async def test_old_firmware_cannot_receive_register_cfg_or_retries(self):
        self.seq.set_cfg_text('TimingRegV=1\nTReg=0:0\n')
        await self.begin(RunPolicy(cfgRetryIntervalSec=.005))
        self.assertEqual((await self.complete())['failItem'], 'timing_firmware_update_required')
        self.assertEqual(self.sess.sent, [])

    async def test_capable_firmware_accepts_cfg_and_can_complete(self):
        self.sess.version = 'T1:abcdef0 1234'
        self.seq.set_cfg_text('AgingTime=0\nTimingRegV=1\nTReg=0:0\n')
        await self.begin(RunPolicy(cfgAckTimeoutSec=.2))
        await until(lambda: bool(self.sess.sent))
        self.sess.queue.put_nowait(Ack(0x15, 0))
        self.sess.queue.put_nowait(TestDone('PASS'))
        self.assertEqual((await self.complete())['result'], 'PASS')


class TimingManualGateTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.ManualPolicyTests.asyncSetUp
    asyncTearDown = fixtures.ManualPolicyTests.asyncTearDown
    async def test_old_firmware_cannot_receive_register_cfg(self):
        await self.runner.power(1, True)
        self.runner._st[1]['cfg'] = 'TimingRegV=1\nTReg=0:0\n'
        self.runner.on_datagram(1, ready_frame())
        self.assertEqual(self.runner.state(1)['detail'], 'timing_firmware_update_required')
        self.assertTrue(all(packet[0][4] != 0x15 for packet in self.runner._transports[1].sent))

    async def test_capable_firmware_accepts_register_cfg(self):
        await self.runner.power(1, True)
        self.runner._st[1]['cfg'] = 'TimingRegV=1\nTReg=0:0\n'
        self.runner.on_datagram(1, build_frame(1, 0x10, b'T1:abcdef0 1234\x00'))
        self.assertEqual(self.runner.state(1)['state'], 'cfg_sent')
        self.runner.on_datagram(1, ack_frame())
        self.runner.on_datagram(1, done_frame())
        self.assertEqual(self.runner.state(1)['state'], 'pass')
