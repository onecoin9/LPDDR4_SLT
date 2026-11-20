"""状态、电源和连接的行为回归；全部是假电源/假传输，不操作 DUT。"""
import asyncio
import threading
import time
import unittest
from types import SimpleNamespace

from app.manualrun import ManualRunner, BoardHealthMonitor
from app.protocol import Ack, StartTest, TestDone, Ready, DutLog, Progress, HsgCodec
from app.sequencer import Sequencer
from app.seriallink import BaseStreamSession
from app.connection import DutSession
from app.ws import Hub
from tests.test_manual_settings import ready_frame, ack_frame, done_frame, FakeTransport


async def until(check, limit=1):
    deadline = time.monotonic() + limit
    while not check():
        if time.monotonic() >= deadline:
            raise AssertionError("condition did not complete")
        await asyncio.sleep(.005)


class Sink:
    def __init__(self): self.active = set(); self.events = []
    def begin_run(self, ch): self.active.add(ch); self.events.append(("begin", ch))
    def end_run(self, ch): self.active.discard(ch); self.events.append(("end", ch))


class Power:
    def __init__(self):
        self.dut_lines = [4, 5]
        self.dut_channels = [5, 6]
        self._power = {1: False, 2: False}
        self.passthrough_base = 44000
        self.board_host = "192.0.2.1"
        self.run_mode = "full_run"
        self.ready_timeout_sec = 1
        self.test_timeout_sec = 1
        self.log_drain_sec = .025
        self.power_off_on_fail = True
        self.power_off_on_pass = True
        self.cfg = "Freq=3200\nAgingTime=5\n"
        self.file_sink = Sink()
        self.calls = []
        self.error = None
    def _require(self): pass
    def dut_port(self, d): return 44000 + self.dut_channels[d-1]
    def ch(self, d): return self.dut_channels[d-1]
    def get_cfg_text(self): return self.cfg
    def set_power(self, d, on):
        if self.error: raise self.error
        self.calls.append((self.ch(d), on))
        self._power[d] = on
        return dict(dut=d, line=self.dut_lines[d-1], powerOn=on)
    def set_power_all(self, on):
        for d in list(self._power): self.set_power(d, on)
        return dict(powerOn=on, mask=0x30)


class ManualLifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.md = Power(); self.hub = Hub()
        self.r = ManualRunner(self.md, self.hub)
        self.r._transports = {1: FakeTransport(), 2: FakeTransport()}
    async def asyncTearDown(self): await self.r.close()
    def status(self, d=1): return self.hub.ensure(1, self.md.ch(d))
    async def phase(self, state, d=1):
        await self.r.power(d, True)
        if state in ("cfg_sent", "running", "pass", "fail"):
            self.r.on_datagram(d, ready_frame())
        if state in ("running", "pass", "fail"):
            self.r.on_datagram(d, ack_frame())
        if state in ("pass", "fail"):
            self.r.on_datagram(d, done_frame(0 if state == "pass" else 1))
        if state == "timeout": self.r._set(d, "timeout", "ready_timeout")

    async def test_phase_and_manual_off_matrix(self):
        for phase, public, online in [("wait_ready", "TESTING", False), ("cfg_sent", "TESTING", True),
                                      ("running", "TESTING", True), ("pass", "PASS", True),
                                      ("fail", "FAIL", True), ("timeout", "FAIL", False)]:
            with self.subTest(phase=phase):
                await self.r.power(1, False)
                await self.phase(phase)
                self.assertEqual((self.status()["state"], self.status()["connected"]), (public, online))
                await self.r.power(1, False)
                expect = public if public in ("PASS", "FAIL") else "OFFLINE"
                self.assertEqual((self.status()["state"], self.status()["connected"]), (expect, False))
                self.r.on_datagram(1, ready_frame())
                self.r.on_datagram(1, done_frame())
                self.assertEqual((self.status()["state"], self.status()["connected"]), (expect, False))

    async def test_power_only_online_then_off(self):
        self.md.run_mode = "power_only"
        await self.r.power(1, True)
        self.r.on_datagram(1, ready_frame())
        self.assertEqual((self.status()["state"], self.status()["connected"]), ("IDLE", True))
        self.assertEqual(self.r._transports[1].sent, [])
        await self.r.power(1, False)
        self.r.on_datagram(1, ready_frame())
        self.assertFalse(self.status()["connected"])

    async def test_failure_auto_off_red_result_grey_connection_and_tail_window(self):
        await self.phase("fail")
        self.assertIn(5, self.md.file_sink.active)
        self.assertTrue(self.md._power[1])
        await until(lambda: not self.md._power[1])
        self.assertEqual((self.status()["state"], self.status()["connected"]), ("FAIL", False))
        self.assertNotIn(5, self.md.file_sink.active)
        count = self.status()["totalCount"]
        self.r.on_datagram(1, ready_frame())
        self.r.on_datagram(1, ack_frame())
        self.r.on_datagram(1, done_frame())
        self.assertEqual((self.status()["state"], self.status()["totalCount"]), ("FAIL", count))

    async def test_pass_auto_off_terminal_ready_latched(self):
        """PASS 默认自动下电（2026-10-10 用户拍板），且终态不被迟到帧翻盘"""
        await self.phase("pass")
        self.r.on_datagram(1, ready_frame())
        self.r.on_datagram(1, done_frame(1))
        await until(lambda: not self.md._power[1])
        self.assertEqual((self.status()["state"], self.status()["totalCount"]), ("PASS", 1))

    async def test_pass_stay_on_when_switch_off_and_latched(self):
        """power_off_on_pass=False：PASS 保持上电，终态同样不被迟到帧翻盘"""
        self.md.power_off_on_pass = False
        await self.phase("pass")
        self.r.on_datagram(1, ready_frame())
        self.r.on_datagram(1, done_frame(1))
        await asyncio.sleep(.04)
        self.assertTrue(self.md._power[1])
        self.assertEqual((self.status()["state"], self.status()["totalCount"]), ("PASS", 1))

    async def test_old_fail_task_never_cuts_retest(self):
        await self.phase("fail")
        await self.r.power(1, False)
        await self.r.power(1, True)
        await asyncio.sleep(.06)
        self.assertTrue(self.md._power[1])
        self.assertEqual(self.r.state(1)["state"], "wait_ready")
        self.assertIn(5, self.md.file_sink.active)

    async def test_inflight_off_finishes_before_retest_on(self):
        entered = threading.Event(); release = threading.Event()
        original = self.md.set_power
        def blocking(d, on):
            if not on: entered.set(); release.wait(2)
            return original(d, on)
        self.md.set_power = blocking
        await self.phase("fail")
        await until(entered.is_set)
        # Old physical command is in flight. Queue an off/on retest via the same lock.
        retest = asyncio.create_task(self.r.power(1, True))
        await asyncio.sleep(.02)
        self.assertFalse(retest.done())
        release.set()
        await retest
        self.assertEqual(self.md.calls[-2:], [(5, False), (5, True)])
        self.assertTrue(self.md._power[1])

    async def test_cancelled_power_request_waits_for_io(self):
        entered = threading.Event(); release = threading.Event()
        original = self.md.set_power
        def blocking(d, on): entered.set(); release.wait(2); return original(d, on)
        self.md.set_power = blocking
        task = asyncio.create_task(self.r.power(1, True))
        await until(entered.is_set)
        task.cancel()
        await asyncio.sleep(.01)
        self.assertTrue(self.r.power_lock.locked())
        release.set()
        await task
        self.assertTrue(self.md._power[1])

    async def test_duplicate_power_on_does_not_reset_active_round(self):
        await self.phase("running")
        run_id = self.r.state(1)["runId"]
        await self.r.power(1, True)
        self.assertEqual((self.r.state(1)["runId"], self.r.state(1)["state"]), (run_id, "running"))

    async def test_cfg_aging_and_budget_frozen(self):
        await self.phase("cfg_sent")
        cfg = self.r.state(1)["cfg"]
        self.md.cfg = "Freq=3733\nAgingTime=50\n"; self.md.test_timeout_sec = 60000
        self.r._send_cfg(1)
        self.assertIn(cfg.encode(), self.r._transports[1].sent[-1][0])
        self.assertEqual((self.r._aging_min(1), self.r.state(1)["runLimit"]), (5, 1))

    async def test_elapsed_accumulates_and_freezes(self):
        await self.phase("running")
        self.r._st[1]["t0"] -= 61
        self.r.on_datagram(1, done_frame())
        self.assertGreaterEqual(self.r.snapshot()["duts"][0]["sinceSec"], 61)
        self.assertGreaterEqual(self.status()["durationSec"], 61)
        before = self.r.snapshot()["duts"][0]["sinceSec"]
        await asyncio.sleep(.03)
        self.assertEqual(self.r.snapshot()["duts"][0]["sinceSec"], before)

    async def test_manual_reboot_freezes_time_and_keeps_power_for_investigation(self):
        self.md.power_off_on_fail = False
        await self.phase("running")
        self.r._st[1]["t0"] -= 61
        self.r.on_datagram(1, ready_frame())
        self.assertEqual((self.status()["state"], self.status()["failItem"]),
                         ("FAIL", "dut_reboot"))
        duration = self.status()["durationSec"]
        count = self.status()["totalCount"]
        await asyncio.sleep(.05)
        self.r.on_datagram(1, done_frame())
        self.assertTrue(self.md._power[1])
        self.assertEqual(self.status()["state"], "FAIL")
        self.assertEqual((self.status()["durationSec"], self.status()["totalCount"]),
                         (duration, count))
        self.assertEqual(sum(p[4] == 0x15 for p, _ in self.r._transports[1].sent), 1)

    async def test_manual_reboot_auto_off_only_affected_dut(self):
        await self.phase("running", 1)
        await self.phase("running", 2)
        self.r.on_datagram(1, ready_frame())
        self.assertEqual(self.status(1)["state"], "FAIL")
        await until(lambda: not self.md._power[1])
        self.assertEqual(self.status(1)["failItem"], "dut_reboot")
        self.assertTrue(self.md._power[2])
        self.assertEqual(self.status(2)["state"], "TESTING")

    async def test_board_offline_matrix_and_recovery(self):
        self.md.power_off_on_fail = False
        self.md.power_off_on_pass = False
        for phase in ("wait_ready", "cfg_sent", "running", "pass", "fail", "timeout"):
            with self.subTest(phase=phase):
                self.r.board_online = True
                await self.r.power(1, False); await self.phase(phase)
                self.r.board_offline()
                expected = "PASS" if phase == "pass" else "FAIL"
                self.assertEqual((self.status()["state"], self.status()["connected"]), (expected, False))
                self.r.board_online = True
                self.r.on_datagram(1, ready_frame())
                self.assertEqual((self.status()["state"], self.status()["connected"]), (expected, False))

    async def test_first_board_health_failure_is_handled(self):
        await self.phase("running")
        def no_board(): raise OSError("board down")
        self.md.board_state = no_board
        await BoardHealthMonitor(self.md, self.hub, self.r).check()
        self.assertEqual(self.r.state(1)["detail"], "commboard_offline")
        self.assertFalse(self.status()["connected"])

    async def test_index_shift_keeps_timeout_on_original_channel(self):
        self.md.ready_timeout_sec = .035
        self.md.power_off_on_fail = False
        await self.r.power(2, True)
        self.md.dut_lines.pop(0); self.md.dut_channels.pop(0)
        self.md._power = {1: True}; self.r.drop_dut(1)
        await until(lambda: self.r.state(1)["state"] == "timeout")
        self.assertEqual(self.hub.ensure(1, 6)["state"], "FAIL")
        self.assertNotEqual(self.hub.ensure(1, 5)["state"], "FAIL")

    async def test_power_command_error_visible_without_claiming_off(self):
        await self.phase("fail")
        self.md.error = OSError("no ack")
        await until(lambda: "powerError" in self.r.state(1))
        self.assertTrue(self.md._power[1])
        self.assertEqual(self.status()["state"], "FAIL")
        self.assertIn("自动下电失败", self.status()["testInfo"])
        self.md.error = None
        await self.r.power(1, False)
        self.assertFalse(self.md._power[1])
        self.assertNotIn("powerError", self.r.state(1))
        self.assertNotIn("自动下电失败", self.status()["testInfo"])

    async def test_group_on_off_preserves_both_results(self):
        await self.r.power(0, True, all_duts=True)
        for d, code in [(1, 0), (2, 1)]:
            self.r.on_datagram(d, ready_frame()); self.r.on_datagram(d, ack_frame()); self.r.on_datagram(d, done_frame(code))
        await self.r.power(0, False, all_duts=True)
        self.assertEqual([self.status(d)["state"] for d in (1, 2)], ["PASS", "FAIL"])
        self.assertFalse(any(self.md._power.values()))

    async def test_cfg_send_exception_finishes_fail(self):
        await self.r.power(1, True)
        self.r._transports[1].sendto = lambda *_: (_ for _ in ()).throw(OSError("send"))
        # ACK send can also fail: receiver must turn it into a visible failure.
        self.r.on_datagram(1, ready_frame())
        self.assertEqual(self.status()["state"], "FAIL")

    async def test_cfg_preparation_error_visible_and_no_power_on(self):
        before = self.r.state(1).copy()
        events = list(self.md.file_sink.events)
        self.md.get_cfg_text = lambda: (_ for _ in ()).throw(OSError("cfg missing"))
        with self.assertRaises(OSError): await self.r.power(1, True)
        self.assertEqual(self.r.state(1)['state'], before['state'])
        self.assertEqual(self.md.file_sink.events, events)
        self.assertEqual(self.md.calls, [])
        self.assertFalse(self.md._power[1])

    async def test_power_pending_indicator_covers_command_ack(self):
        entered = threading.Event(); release = threading.Event(); snapshots = []
        original = self.md.set_power
        def blocking(d, on): entered.set(); release.wait(2); return original(d, on)
        self.md.set_power = blocking
        self.r.on_change = lambda: snapshots.append(self.r.state(1))
        task = asyncio.create_task(self.r.power(1, True))
        await until(entered.is_set)
        self.assertEqual(self.r.state(1)["powerAction"], "turning_on")
        self.assertFalse(self.md._power[1])
        release.set(); await task
        self.assertEqual(self.r.state(1)["powerAction"], "")
        self.assertTrue(self.md._power[1])


class Session:
    def __init__(self, slot=1):
        self.site = 1; self.slot = slot; self.connected = True; self.ready_generation = 0
        self.sent = []; self.queues = []; self.error = None
    def send(self, msg):
        if self.error and isinstance(msg, StartTest): raise self.error
        self.sent.append(msg)
    def subscribe(self): q = asyncio.Queue(); self.queues.append(q); return q
    def unsubscribe(self, q): self.queues.remove(q)
    def emit(self, evt):
        for q in self.queues: q.put_nowait(evt)


class Recorder:
    def __init__(self): self.results = []; self.writers = []
    def start_run(self, *args):
        w = SimpleNamespace(closed=False, lines=[])
        w.write_log = lambda level, msg: w.lines.append(msg)
        w.close = lambda **kw: setattr(w, 'closed', True)
        self.writers.append(w); return w
    def append_result(self, *args): self.results.append(args)


class AutomaticLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_scan_reservation_blocks_normal_start_and_config_changes(self):
        from app.sequencer import SequencerBusyError
        owner = object()
        production = self.seq.cfg_text
        self.seq.reserve(owner)
        with self.assertRaises(SequencerBusyError):
            await self.seq.start([(1, 1)], "OTHER")
        with self.assertRaises(SequencerBusyError):
            self.seq.set_cfg_text("OTHER")
        self.seq.release(object())
        self.assertTrue(self.seq.reserved)
        self.seq.release(owner)
        self.assertEqual(self.seq.cfg_text, production)
        self.assertFalse(self.seq.reserved)
        self.assertEqual(self.sess.sent, [])

    async def test_point_cfg_and_result_are_owned_by_the_run(self):
        owner = object()
        self.seq.reserve(owner)
        production = self.seq.cfg_text
        outcomes = {}
        await self.seq.start([(1, 1)], "POINT", cfg_text="Freq=2400\nMemTester=0\n",
                             owner=owner, outcomes=outcomes)
        await until(lambda: self.sess.queues)
        self.assertEqual(self.seq.cfg_text, production)
        self.assertTrue(any(isinstance(x, StartTest) and "2400" in x.cfg for x in self.sess.sent))
        self.sess.emit(TestDone(result="PASS", failItem="", durationSec=2))
        await until(lambda: self.hub.ensure(1, 1)["state"] == "PASS")
        self.hub.ensure(1, 1)["result"] = "FAIL"  # Later projection must not rewrite this run's result.
        await until(lambda: bool(outcomes))
        self.assertEqual(outcomes[(1, 1)]["result"], "PASS")
        self.seq.release(owner)

    async def test_startup_failure_retained_even_when_started_list_is_empty(self):
        async def power(keys): return 0
        self.seq.power_hook = power
        owner = object()
        self.seq.reserve(owner)
        outcomes = {}
        started = await self.seq.start([(1, 1)], "POINT", cfg_text="MemTester=0\n",
                                       owner=owner, outcomes=outcomes)
        await until(lambda: bool(outcomes))
        self.assertEqual(started, [])
        self.assertEqual(outcomes[(1, 1)]["failItem"], "dut_conn_timeout")
        self.seq.release(owner)
    async def asyncSetUp(self):
        self.hub = Hub(); self.sess = Session(); self.rec = Recorder()
        self.conns = SimpleNamespace(get=lambda site, slot: self.sess if slot == 1 else None)
        self.seq = Sequencer({'dut': {'test_timeout_sec': .25, 'boot_timeout_sec': .04, 'log_drain_sec': .015}}, self.conns, self.hub, self.rec)
        self.hub.update(1, 1, connected=True, state="IDLE")
    async def asyncTearDown(self): await self.seq.close()
    async def running(self):
        await self.seq.start([(1, 1)], "B")
        await until(lambda: self.sess.queues)
    async def test_stop_preparation_and_compensate_power(self):
        gate = asyncio.Event(); entered = asyncio.Event(); off = []
        async def hook(keys): entered.set(); await gate.wait(); return 0
        async def cancel(keys): off.extend(keys)
        self.seq.power_hook = hook; self.seq.power_cancel_hook = cancel
        start = asyncio.create_task(self.seq.start([(1, 1)], "B"))
        await entered.wait()
        stop = asyncio.create_task(self.seq.stop([(1, 1)]))
        await asyncio.sleep(.01); gate.set()
        self.assertEqual(await stop, [(1, 1)])
        self.assertEqual(await start, [])
        self.assertEqual(off, [(1, 1)])
        self.assertEqual(self.sess.sent, [])
        self.assertEqual(self.rec.results, [])
        self.assertEqual(self.hub.ensure(1, 1)["state"], "OFFLINE")
    async def test_busy_filtered_before_power_hook(self):
        await self.running()
        calls = []
        async def hook(keys): calls.extend(keys); return 0
        self.seq.power_hook = hook
        self.assertEqual(await self.seq.start([(1, 1), (1, 1)], "B"), [])
        self.assertEqual(calls, [])
    async def test_cached_connection_not_fresh_ready(self):
        async def hook(keys): self.hub.update(1, 1, connected=True); return 0
        self.seq.power_hook = hook
        self.assertEqual(await self.seq.start([(1, 1)], "B"), [])
        await until(lambda: not self.seq.tasks)
        self.assertEqual(self.sess.sent, [])
        self.assertEqual(self.hub.ensure(1, 1)["state"], "FAIL")
    async def test_new_ready_during_preparation_starts(self):
        async def hook(keys):
            self.sess.ready_generation += 1
            self.hub.update(1, 1, connected=True)
            return 0
        self.seq.power_hook = hook
        self.assertEqual(await self.seq.start([(1, 1)], "B"), [(1, 1)])
        await until(lambda: self.sess.queues)
        self.sess.emit(TestDone(result="PASS"))
        await until(lambda: not self.seq.tasks)
        self.assertEqual(self.hub.ensure(1, 1)["state"], "PASS")
    async def test_negative_ack_cannot_be_overwritten_by_pass(self):
        await self.running()
        self.sess.emit(Ack(0x15, 2)); self.sess.emit(TestDone(result="PASS"))
        await until(lambda: not self.seq.tasks)
        self.assertEqual(self.hub.ensure(1, 1)["state"], "FAIL")
        self.assertEqual(len(self.rec.results), 1)
        self.assertTrue(self.rec.writers[0].closed)
    async def test_unexpected_send_exception_cleans_up(self):
        self.sess.error = OSError("send error")
        await self.seq.start([(1, 1)], "B")
        await until(lambda: not self.seq.tasks)
        self.assertEqual(self.hub.ensure(1, 1)["state"], "FAIL")
        self.assertIn("runtime_error", self.hub.ensure(1, 1)["testInfo"])
        self.assertTrue(self.rec.writers[0].closed)
        self.assertFalse(self.sess.queues)
    async def test_terminal_tail_log_saved(self):
        await self.running()
        self.sess.emit(TestDone(result="FAIL", failItem="test"))
        self.sess.emit(DutLog("ERROR", "address=0x123 expected=0 got=1"))
        await until(lambda: not self.seq.tasks)
        self.assertIn("address=0x123", '\n'.join(self.rec.writers[0].lines))
    async def test_fail_auto_off_red_and_late_ready_ignored(self):
        off = []
        async def hook(keys): self.sess.ready_generation += 1; self.hub.update(1, 1, connected=True); return 0
        async def cancel(keys): off.extend(keys)
        self.seq.power_hook = hook; self.seq.power_cancel_hook = cancel
        await self.running(); self.sess.emit(TestDone(result="FAIL"))
        await until(lambda: not self.seq.tasks)
        self.assertEqual(off, [(1, 1)])
        self.assertEqual((self.hub.ensure(1, 1)["state"], self.hub.ensure(1, 1)["connected"]), ("FAIL", False))
        self.assertTrue(self.sess._ignore_frames)

    async def test_immediate_stop_after_reservation_cleans_up(self):
        gate = asyncio.Event()
        async def hook(keys): await gate.wait(); return 0
        self.seq.power_hook = hook
        start = asyncio.create_task(self.seq.start([(1, 1)], "B"))
        await asyncio.sleep(0)  # start 已登记，但子任务可能尚未进入第一行
        stop = asyncio.create_task(self.seq.stop([(1, 1)]))
        gate.set()
        self.assertEqual(await stop, [(1, 1)])
        self.assertEqual(await start, [])
        self.assertFalse(self.seq.tasks)
        self.assertFalse(self.sess.sent)

    async def test_stop_during_terminal_drain_keeps_result(self):
        self.seq.log_drain_sec = .04
        await self.running(); self.sess.emit(TestDone(result="FAIL", failItem="bad_bit"))
        await until(lambda: self.hub.ensure(1, 1)["state"] == "FAIL")
        self.assertEqual(await self.seq.stop([(1, 1)]), [])
        await until(lambda: not self.seq.tasks)
        self.assertEqual(self.hub.ensure(1, 1)["state"], "FAIL")
        self.assertEqual(len(self.rec.results), 1)


class WebSocketOrdering(unittest.IsolatedAsyncioTestCase):
    async def test_single_sender_keeps_event_order(self):
        gate = asyncio.Event()
        class WS:
            def __init__(self): self.sent=[]; self.active=0; self.max_active=0
            async def accept(self): pass
            async def send_text(self, payload):
                self.active += 1; self.max_active = max(self.max_active, self.active)
                await gate.wait(); self.sent.append(payload); self.active -= 1
        hub = Hub(); ws = WS(); await hub.connect(ws)
        hub._send_texts(["TESTING"]); hub._send_texts(["FAIL"]); hub._send_texts(["POWER_OFF"])
        await asyncio.sleep(.01); gate.set()
        await until(lambda: len(ws.sent) == 3)
        self.assertEqual(ws.sent, ["TESTING", "FAIL", "POWER_OFF"])
        self.assertEqual(ws.max_active, 1)
        await hub.close()

    async def test_slow_client_has_bounded_queue_and_reconnects(self):
        class WS:
            def __init__(self): self.closed=False
            async def accept(self): pass
            async def send_text(self, payload): await asyncio.Event().wait()
            async def close(self, code): self.closed = code == 1013
        hub = Hub(); ws = WS(); await hub.connect(ws)
        for _ in range(260): hub._send_texts(["state"])
        await until(lambda: ws.closed)
        self.assertNotIn(ws, hub.clients)
        await hub.close()


class ConnectionProjection(unittest.TestCase):
    def test_udp_offline_keeps_terminal_results(self):
        for result in ("PASS", "FAIL"):
            hub = Hub(); s = DutSession(1, 1, "A", "192.0.2.1", 1, 1, HsgCodec(), hub, {})
            hub.result(1, 1, result, "bad_bit", 12)
            s._mark_offline()
            self.assertEqual((hub.ensure(1, 1)["state"], hub.ensure(1, 1)["connected"]), (result, False))
    def test_stream_offline_keeps_terminal_results(self):
        for result in ("PASS", "FAIL"):
            hub = Hub(); s = BaseStreamSession(1, 1, HsgCodec(), hub, {})
            hub.result(1, 1, result, "bad_bit", 12)
            s._on_link_dead("down")
            self.assertEqual((hub.ensure(1, 1)["state"], hub.ensure(1, 1)["connected"]), (result, False))
