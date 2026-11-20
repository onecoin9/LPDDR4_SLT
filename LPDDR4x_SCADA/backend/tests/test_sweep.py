"""扫描引擎单元测试（Phase 2）：点生成 / 主轴定位 / 逐点编译 / 边界 / 全流程。"""

import asyncio
import os
import sys
import tempfile
import unittest

sys.path.insert(0, ".")
from app.cfg import _DEFAULTS, parse_cfg, stages_from_map  # noqa: E402
from app.sweep import (  # noqa: E402
    SWEEP_MAX_POINTS,
    SweepEngine,
    SweepError,
    build_points,
    compile_point,
    find_axis,
)


def sweep_profile(**kw):
    p = {
        "name": "SWEEP-TEST",
        "timingSchema": 1,
        "rankEnabled": True, "pl1Enabled": True, "pl2Enabled": True,
        "rankCapacityGb": [1, 1],
        "channels": {"ch1": True, "ch2": True},
        "mr": {"ch1": [], "ch2": []},
        "params": [
            {"id": 1, "name": "VDD1(mV)", "value": "1950", "checked": True,
             "start": "", "step": "", "end": ""},
            {"id": 2, "name": "TRCD", "value": "0", "checked": True,
             "start": "0", "step": "1", "end": "12"},
        ],
        "pl2": {"testMode": "Block测试", "ascEnabled": True, "ascOrder": "升序",
                "patterns": {"Block测试": [{"name": "test_solid_bit", "checked": True}]}},
    }
    p.update(kw)
    return p


class TestBuildPoints(unittest.TestCase):
    def test_basic(self):
        pts = build_points("-3", "0.5", "3")
        self.assertEqual(len(pts), 13)
        self.assertEqual(pts[0], -3.0)
        self.assertEqual(pts[-1], 3.0)

    def test_integer_step(self):
        self.assertEqual(build_points("40", "10", "60"), [40.0, 50.0, 60.0])

    def test_descending(self):
        self.assertEqual(build_points("3", "-1", "0"), [3.0, 2.0, 1.0, 0.0])

    def test_errors(self):
        with self.assertRaises(SweepError):
            build_points("1", "0", "5")          # 步进 0
        with self.assertRaises(SweepError):
            build_points("0", "1", "-5")         # 方向矛盾
        with self.assertRaises(SweepError):
            build_points("0", "0.01", "100")     # 超点数上限
        with self.assertRaises(SweepError):
            build_points("a", "1", "2")          # 非数值

    def test_max_points_cap(self):
        self.assertGreater(SWEEP_MAX_POINTS, 0)

    def test_nonfinite_rejected(self):
        for value in ("nan", "inf", "-inf"):
            with self.assertRaises(SweepError):
                build_points(value, "1", "3")


class TestFindAxis(unittest.TestCase):
    def test_single_axis(self):
        row = find_axis(sweep_profile())
        self.assertEqual(row["name"], "TRCD")

    def test_no_axis(self):
        prof = sweep_profile()
        prof["params"][1].update(start="", step="", end="")
        with self.assertRaises(SweepError):
            find_axis(prof)

    def test_two_axes_rejected(self):
        prof = sweep_profile()
        prof["params"][0].update(start="1", step="1", end="2")
        with self.assertRaises(SweepError):
            find_axis(prof)

    def test_unchecked_axis_rejected(self):
        prof = sweep_profile()
        prof["params"][1]["checked"] = False
        with self.assertRaises(SweepError):
            find_axis(prof)


class TestCompilePoint(unittest.TestCase):
    def test_axis_substituted_and_quick(self):
        text, warns = compile_point(sweep_profile(), "TRCD", 7, dict(_DEFAULTS), True)
        m = parse_cfg(text)
        self.assertIn('TReg=0:7\n',text)               # Current explicit raw ABI, no legacy bare key.
        self.assertEqual(m["AGINGTIME"], 0)            # quick：三键清零
        self.assertEqual(m["MEMTESTER"], 0)
        self.assertEqual(m["DVFSTEST"], 0)
        self.assertEqual(stages_from_map(m), ["PL", "LK"])
        self.assertEqual(warns, [])
        # 原档案不被改动
        self.assertEqual(sweep_profile()["params"][1]["value"], "0")

    def test_full_mode_keeps_aging(self):
        text, _ = compile_point(sweep_profile(), "TRCD", 1.0, dict(_DEFAULTS), False)
        m = parse_cfg(text)
        self.assertIn('TReg=0:1\n',text)
        self.assertEqual(m["AGINGTIME"], _DEFAULTS["AgingTime"])

    def test_vdd_axis_mck_not_applied_to_vdd(self):
        # VDD 轴扫描：值按 mV 直传
        prof = sweep_profile()
        prof["params"] = [
            {"id": 1, "name": "VDD1(mV)", "value": "1950", "checked": True,
             "start": "1800", "step": "50", "end": "2000"}]
        text, warns = compile_point(prof, "VDD1(mV)", 1850, dict(_DEFAULTS), True)
        self.assertEqual(parse_cfg(text)["VDD1"], 1850)
        self.assertEqual(warns, [])

    def test_invalid_raw_axis_is_not_run_at_baseline(self):
        prof = sweep_profile(timingUnit=2)
        for value in (31, 32, 1.5):
            with self.assertRaises(SweepError):
                compile_point(prof, "TRCD", value, dict(_DEFAULTS), True)

    def test_rejected_legacy_or_ns_axis_cannot_run_defaults(self):
        prof=sweep_profile(); prof.pop('timingSchema')
        with self.assertRaises(SweepError): compile_point(prof,'TRCD',1,dict(_DEFAULTS),True)
        prof['timingSchema']=2
        with self.assertRaises(SweepError): compile_point(prof,'TRCD',1,dict(_DEFAULTS),True)


class _FakeHub:
    def __init__(self):
        self.states = {}
        self.logs = []

    def ensure(self, site, slot):
        return self.states.setdefault((site, slot), {
            "state": "IDLE", "result": None, "failItem": None, "durationSec": 0.0})

    def syslog(self, level, msg):
        self.logs.append((level, msg))


class _FakeSeq:
    """最小 Sequencer 替身：start 返回全部 targets，任务立即完成并写 hub 结果。"""

    def __init__(self, hub, results_by_point):
        self.hub = hub
        self.results_by_point = results_by_point   # [(point_value, result), ...]
        self.calls = []                            # (batch, cfg_text)
        self.tasks = {}
        self.cfg_text = ""
        self.owner = None

    def reserve(self, owner):
        if self.owner is not None:
            raise SweepError("busy")
        self.owner = owner

    def release(self, owner):
        if self.owner is owner:
            self.owner = None

    def set_cfg_text(self, text):
        self.cfg_text = text

    async def start(self, targets, batch, *, cfg_text=None, owner=None, outcomes=None, run_policy=None):
        point = self.results_by_point[len(self.calls)][1]
        self.calls.append((batch, cfg_text if cfg_text is not None else self.cfg_text, point))
        for key in targets:
            st = self.hub.ensure(*key)
            st.update(result=point, failItem="" if point == "PASS" else "init_fail",
                      durationSec=1.0)
            if outcomes is not None:
                outcomes[key] = dict(st)
            # 模拟真实 Sequencer 的 tasks 生命周期：start 后任务已完成
        return list(targets)

    async def stop(self, targets):
        return []


class TestEngineFlow(unittest.TestCase):
    def _run_engine(self, results_by_point, **start_kw):
        hub = _FakeHub()
        seq = _FakeSeq(hub, results_by_point)
        root = tempfile.mkdtemp()
        eng = SweepEngine(seq, hub, root)
        targets = [(1, 1), (1, 2)]

        async def drive():
            st = await eng.start(sweep_profile(), targets, dict(_DEFAULTS),
                                 batch_prefix="B", **start_kw)
            self.assertTrue(st["running"])
            await _wait_task(eng)

        asyncio.run(drive())
        return eng, seq

    def test_full_pass_then_fail_boundary(self):
        # 当前raw ABI 0..12共13点：前9点PASS，后4点FAIL，边界[0,8]
        rbp = [(v, "PASS" if v <= 8 else "FAIL") for v in
               range(13)]
        eng, seq = self._run_engine(rbp)
        st = eng.status
        self.assertFalse(st["running"])
        self.assertEqual(st["axis"], "TRCD")
        self.assertEqual(len(st["results"]), 13)
        self.assertEqual(len(seq.calls), 13)
        b = st["summary"]["pass_boundary"]
        self.assertEqual((b["from"], b["to"]), ("0", "8"))
        # CSV 与 summary 落盘（summary = 同名去 .csv 后缀 + .summary.json）
        self.assertTrue(os.path.exists(st["csv_path"]))
        summary_file = os.path.splitext(st["csv_path"])[0] + ".summary.json"
        self.assertTrue(os.path.exists(summary_file))
        with open(st["csv_path"], encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 1 + 13 * 2)      # 表头 + 13 点 × 2 通道
        self.assertEqual(lines[1].split(",")[1], "0")
        # 批次名可下钻
        self.assertTrue(st["results"][0]["batch"].endswith("SW01"))
        # quick 模式生效于每点编译
        self.assertIn("AgingTime=0", seq.calls[0][1])

    def test_stop_on_fail(self):
        rbp = [(v, "PASS" if v < 6 else "FAIL") for v in
               range(13)]
        eng, seq = self._run_engine(rbp, stop_on_fail=True)
        # raw值6（第7点）FAIL即停
        self.assertEqual(len(eng.status["results"]), 7)
        self.assertIn("stop_on_fail", eng.status["aborted"])

    def test_boundary_degenerate(self):
        # 全 PASS → 无边界
        rbp = [(v, "PASS") for v in (0, 1, 2)]
        prof = sweep_profile()
        prof["params"][1].update(start="0", step="1", end="2")
        hub = _FakeHub()
        seq = _FakeSeq(hub, rbp)
        eng = SweepEngine(seq, hub, tempfile.mkdtemp())

        async def drive():
            await eng.start(prof, [(1, 1)], dict(_DEFAULTS), batch_prefix="B")
            await _wait_task(eng)

        asyncio.run(drive())
        self.assertIsNone(eng.status["summary"]["pass_boundary"])

    def test_running_guard(self):
        hub = _FakeHub()
        seq = _FakeSeq(hub, [(v, "PASS") for v in (1, 2)])
        eng = SweepEngine(seq, hub, tempfile.mkdtemp())
        eng.status["running"] = True
        with self.assertRaises(SweepError):
            asyncio.run(eng.start(sweep_profile(), [(1, 1)], dict(_DEFAULTS)))

    def test_preflight_rejects_all_points_before_reservation_or_io(self):
        hub = _FakeHub()
        seq = _FakeSeq(hub, [])
        eng = SweepEngine(seq, hub, tempfile.mkdtemp())
        prof = sweep_profile(timingUnit=2)
        prof["params"][1].update(start="30", step="1", end="32")
        with self.assertRaises(SweepError):
            asyncio.run(eng.start(prof, [(1, 1)], dict(_DEFAULTS)))
        self.assertEqual(seq.calls, [])
        self.assertIsNone(seq.owner)

    def test_production_cfg_unchanged_and_reservation_released(self):
        rbp = [(v, "PASS") for v in (0, 1, 2)]
        hub = _FakeHub()
        seq = _FakeSeq(hub, rbp)
        seq.cfg_text = "PRODUCTION"
        eng = SweepEngine(seq, hub, tempfile.mkdtemp())
        prof = sweep_profile()
        prof["params"][1].update(start="0", step="1", end="2")
        async def drive():
            await eng.start(prof, [(1, 1)], dict(_DEFAULTS))
            await _wait_task(eng)
            await asyncio.sleep(0)
        asyncio.run(drive())
        self.assertEqual(seq.cfg_text, "PRODUCTION")
        self.assertIsNone(seq.owner)

    def test_immediate_stop_releases_reservation_before_task_starts(self):
        hub = _FakeHub()
        seq = _FakeSeq(hub, [])
        with tempfile.TemporaryDirectory() as root:
            eng = SweepEngine(seq, hub, root)
            async def drive():
                await eng.start(sweep_profile(), [(1, 1)], dict(_DEFAULTS))
                self.assertIsNotNone(seq.owner)
                self.assertTrue(await eng.stop())
                self.assertIsNone(seq.owner)
                self.assertFalse(eng.status["running"])
                self.assertEqual(seq.calls, [])
                self.assertIn("停止", eng.status["aborted"])
            asyncio.run(drive())

    def test_stop_only_cancels_owned_targets_and_preserves_production_cfg(self):
        hub = _FakeHub()
        entered = asyncio.Event()
        stopped = []
        class RunningSeq(_FakeSeq):
            async def start(self, targets, batch, **kwargs):
                self.tasks[targets[0]] = asyncio.create_task(asyncio.Event().wait())
                entered.set()
                return list(targets)
            async def stop(self, targets):
                stopped.extend(targets)
                for key in targets:
                    self.tasks[key].cancel()
                await asyncio.gather(*(self.tasks[k] for k in targets), return_exceptions=True)
                return list(targets)
        seq = RunningSeq(hub, [])
        seq.cfg_text = "PRODUCTION"
        with tempfile.TemporaryDirectory() as root:
            eng = SweepEngine(seq, hub, root)
            async def drive():
                foreign = asyncio.create_task(asyncio.Event().wait())
                seq.tasks[(9, 9)] = foreign
                try:
                    await eng.start(sweep_profile(), [(1, 1)], dict(_DEFAULTS))
                    await entered.wait()
                    await eng.stop()
                    self.assertEqual(stopped, [(1, 1)])
                    self.assertFalse(foreign.done())
                    self.assertIsNone(seq.owner)
                    self.assertFalse(eng.status["running"])
                    self.assertEqual(seq.cfg_text, "PRODUCTION")
                    self.assertIn("停止", eng.status["aborted"])
                finally:
                    foreign.cancel()
                    await asyncio.gather(foreign, return_exceptions=True)
            asyncio.run(drive())

    def test_entire_scan_freezes_runtime_policy_across_points(self):
        from app.runtimepolicy import RunPolicy
        policy = RunPolicy(cfgAckTimeoutSec=20)
        seen = []
        hub = _FakeHub()
        class PolicySeq(_FakeSeq):
            async def start(self, targets, batch, **kwargs):
                seen.append(kwargs["run_policy"].cfgAckTimeoutSec)
                policy.cfgAckTimeoutSec = 40
                return await super().start(targets, batch, **kwargs)
        seq = PolicySeq(hub, [(1, "PASS"), (2, "PASS")])
        seq.policy_provider = lambda: policy
        with tempfile.TemporaryDirectory() as root:
            eng = SweepEngine(seq, hub, root)
            prof = sweep_profile()
            prof["params"][1].update(start="1", step="1", end="2")
            async def drive():
                await eng.start(prof, [(1, 1)], dict(_DEFAULTS))
                await _wait_task(eng)
            asyncio.run(drive())
        self.assertEqual(seen, [20, 20])

    def test_missing_planned_channel_cannot_be_all_pass(self):
        hub = _FakeHub()
        class MissingSeq(_FakeSeq):
            async def start(self, targets, batch, **kwargs):
                return await super().start(targets[:1], batch, **kwargs)
        seq = MissingSeq(hub, [(1, "PASS")])
        eng = SweepEngine(seq, hub, tempfile.mkdtemp())
        prof = sweep_profile()
        prof["params"][1].update(start="1", step="1", end="1")
        async def drive():
            await eng.start(prof, [(1, 1), (1, 2)], dict(_DEFAULTS))
            await _wait_task(eng)
        asyncio.run(drive())
        point = eng.status["results"][0]
        self.assertEqual((point["pass"], point["total"]), (1, 2))
        self.assertEqual(point["per_key"]["S01CH02"]["result"], "NOT_STARTED")


async def _wait_task(eng):
    if eng._task is not None:
        await asyncio.gather(eng._task, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
