"""授权接纳边界：拒绝时没有状态/电源副作用，到期后活动轮次可收尾。"""
import asyncio
from types import SimpleNamespace
import unittest

from app.license_core import LicenseDenied
from app.manualrun import ManualRunner
from app.sequencer import Sequencer
from app.protocol import TestDone
from app.ws import Hub
from tests.test_state_lifecycle import Power, Session, Recorder, until
from tests.test_manual_settings import FakeTransport, ready_frame, ack_frame, done_frame
from tests.test_state_api import api


def denied():
    raise LicenseDenied({"state": "expired", "allowedToStart": False, "message": "授权已到期"})


class Gates(unittest.IsolatedAsyncioTestCase):
    async def test_automatic_denial_has_no_state_power_or_tasks(self):
        hub = Hub(); sess = Session(); rec = Recorder(); calls = []
        hub.update(1, 1, connected=True, state="IDLE")
        seq = Sequencer({}, SimpleNamespace(get=lambda *a: sess), hub, rec)
        async def power(keys): calls.append(keys); return 0
        seq.power_hook = power; seq.authorize_start = denied
        with self.assertRaises(LicenseDenied): await seq.start([(1, 1)], "B")
        self.assertEqual((seq.tasks, seq._contexts, calls, rec.results), ({}, {}, [], []))
        self.assertEqual(hub.ensure(1, 1)["state"], "IDLE")

    async def test_automatic_admitted_run_finishes_after_expiry(self):
        hub = Hub(); sess = Session(); rec = Recorder()
        hub.update(1, 1, connected=True, state="IDLE")
        seq = Sequencer({'dut': {'log_drain_sec': .005}}, SimpleNamespace(get=lambda *a: sess), hub, rec)
        seq.authorize_start = lambda: None
        try:
            await seq.start([(1, 1)], "B"); await until(lambda: sess.queues)
            seq.authorize_start = denied
            sess.emit(TestDone(result="PASS")); await until(lambda: not seq.tasks)
            self.assertEqual(hub.ensure(1, 1)["state"], "PASS")
            with self.assertRaises(LicenseDenied): await seq.start([(1, 1)], "B2")
        finally: await seq.close()

    async def test_manual_denial_for_single_group_and_arm_has_no_side_effects(self):
        for mode in ("full_run", "power_only"):
            for kind in ("single", "all", "arm"):
                md = Power(); md.run_mode = mode; hub = Hub(); runner = ManualRunner(md, hub)
                runner.authorize_start = denied
                try:
                    with self.assertRaises(LicenseDenied):
                        if kind == "arm": runner.arm(1)
                        else: await runner.power(1, True, all_duts=kind == "all")
                    self.assertEqual((md.calls, md.file_sink.events, runner._run_serial), ([], [], 0))
                    self.assertFalse(any(md._power.values()))
                    self.assertFalse(runner._timer)
                finally: await runner.close()

    async def test_manual_cfg_duplicate_ready_finish_and_off_allowed_after_expiry(self):
        md = Power(); md.power_off_on_pass = False; hub = Hub(); runner = ManualRunner(md, hub)
        runner._transports = {1: FakeTransport()}; runner.authorize_start = lambda: None
        try:
            await runner.power(1, True)
            runner.authorize_start = denied
            # 首次 CFG 尚未确认时重复 READY 属握手重发，不是测试中重启。
            runner.on_datagram(1, ready_frame()); runner.on_datagram(1, ready_frame())
            self.assertEqual(runner.state(1)["state"], "cfg_sent")
            runner.on_datagram(1, ack_frame())
            self.assertEqual(runner.state(1)["state"], "running")
            runner.on_datagram(1, done_frame())
            self.assertEqual(runner.state(1)["state"], "pass")
            await runner.power(1, False)
            self.assertFalse(md._power[1])
            with self.assertRaises(LicenseDenied): await runner.power(1, True)
        finally: await runner.close()

    async def test_direct_board_power_on_and_reboot_are_guarded(self):
        for name in ("api_board_power_on", "api_board_reboot"):
            fn = api(name, license_service=SimpleNamespace(require_valid=denied))
            with self.assertRaises(LicenseDenied): await fn(1, "A")

    async def test_handler_uses_same_sequencer_and_returns_failure(self):
        from app.handler import HandlerService
        hub = Hub(); sess = Session()
        hub.update(1, 1, connected=True, state="IDLE")
        seq = Sequencer({}, SimpleNamespace(get=lambda *a: sess), hub, Recorder())
        seq.authorize_start = denied
        handler = HandlerService({}, hub, seq.start, lambda s: [], lambda: "B")
        import json
        reply = json.loads(await handler._dispatch(json.dumps({"method": "teststart", "data": {"bibid": 1, "sites": [{"siteid": 1, "IsEnable": True}]}}).encode()))
        self.assertEqual(reply["status"], "fail")
        self.assertFalse(seq.tasks)
