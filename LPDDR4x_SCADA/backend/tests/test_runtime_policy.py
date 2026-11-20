"""Run guards, frozen policies and archives; all IO is fake or temporary loopback."""
import asyncio
import json
import math
import tempfile
import time
import unittest
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from app.runtimepolicy import RunPolicy, RunGuard, PolicyStore, PolicyConflict, PolicyUnavailable
from app.recorder import Recorder
from app.sequencer import Sequencer
from app.manualrun import ManualRunner
from app.protocol import Ack, TestDone, Progress, build_frame, DT_STRING
from app.ws import Hub
from tests.test_state_lifecycle import Power, until
from tests.test_manual_settings import FakeTransport, ready_frame, ack_frame, done_frame
from tests import test_profile_api as profile_api_fixture


class PolicyTests(unittest.TestCase):
    def test_default_preserves_existing_limits_and_version_behavior(self):
        p = RunPolicy()
        g = RunGuard(p, ["PL", "LK", "APK"], 100)
        self.assertIsNone(g.expired(10000))
        self.assertIsNone(p.version_failure(""))

    def test_duplicate_backward_unknown_reports_do_not_renew_stage_budget(self):
        g = RunGuard(RunPolicy(stageTimeoutSec={"PL": 10, "LK": 5, "APK": 20}), ["PL", "LK", "APK"], 100)
        g.ack()
        self.assertTrue(g.observe("PL", 101))
        self.assertFalse(g.observe("PL", 108))
        self.assertEqual(g.expired(111), "stage_timeout:PL")
        self.assertTrue(g.observe("LK", 112))
        self.assertFalse(g.observe("PL", 113))
        self.assertFalse(g.observe("unknown", 115))
        self.assertEqual(g.expired(117), "stage_timeout:LK")

    def test_ack_budget_independent_of_progress_and_zero_disables(self):
        g = RunGuard(RunPolicy(cfgAckTimeoutSec=3), ["PL"], 20)
        g.observe("PL", 22)
        self.assertEqual(g.expired(23), "cfg_ack_timeout")
        g.ack()
        self.assertIsNone(g.expired(1000))
        g.restart_cfg(1001)
        self.assertEqual(g.expired(1004), "cfg_ack_timeout")

    def test_exact_ready_identifier_missing_wrong_and_null_padding(self):
        p = RunPolicy(checkReadyVersion=True, expectedReadyVersion=" M80-_6785 ")
        self.assertIsNone(p.version_failure("M80-\x00_6785\x00"))
        self.assertIn("missing", p.version_failure(None))
        self.assertIn("version_mismatch", p.version_failure("M80-_6786"))
        self.assertIn("version_mismatch", p.version_failure("prefixM80-_6785"))

    def test_invalid_policy_cannot_be_silently_used(self):
        for bad in ({"cfgAckTimeoutSec": math.nan}, {"cfgRetryIntervalSec": True},
                    {"cfgAckTimeoutSec": -1}, {"stageTimeoutSec": {"PL": math.inf}},
                    {"stageTimeoutSec": {"AP": 1}}, {"checkReadyVersion": True},
                    {"expectedReadyVersion": "ABC\nDEF"}, {"unexpected": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                RunPolicy.model_validate(bad)

    def test_policy_atomic_save_snapshot_and_optimistic_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PolicyStore(Path(directory) / "runtime_policy.json")
            old = store.snapshot()
            rev = old.revision
            updated = RunPolicy(cfgAckTimeoutSec=12)
            store.save(updated, rev)
            self.assertEqual(PolicyStore(store.path).snapshot().cfgAckTimeoutSec, 12)
            self.assertEqual(old.cfgAckTimeoutSec, 0)
            with self.assertRaises(PolicyConflict): store.save(RunPolicy(), rev)
            with patch("app.runtimepolicy.os.replace", side_effect=OSError("disk")):
                with self.assertRaises(OSError): store.save(RunPolicy(cfgAckTimeoutSec=30))
            self.assertEqual(store.snapshot().cfgAckTimeoutSec, 12)
            self.assertEqual(PolicyStore(store.path).snapshot().cfgAckTimeoutSec, 12)

    def test_corrupt_store_blocks_new_runs_but_can_be_repaired(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "runtime_policy.json"
            file.write_text("{bad")
            store = PolicyStore(file)
            self.assertFalse(store.status()["valid"])
            with self.assertRaises(PolicyUnavailable): store.snapshot()
            store.save(RunPolicy())
            self.assertTrue(store.status()["valid"])

    def test_log_close_is_idempotent_and_same_second_runs_do_not_share_files(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = Recorder(directory)
            one, two = recorder.start_run(1, 1, "B"), recorder.start_run(1, 1, "B")
            one.close("first")
            one.close("second")
            two.close()
            self.assertNotEqual(one.path, two.path)
            self.assertEqual(Path(one.path).read_text().count("==== end"), 1)

    def test_archive_day_is_bound_to_admission_even_across_midnight(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = Recorder(directory)
            record = {"runId": "a" * 32, "startedAt": datetime(2026, 10, 1, 23, 59).timestamp()}
            first = recorder.write_run_record(record)
            record["outcome"] = {"result": "PASS"}
            second = recorder.write_run_record(record)
            self.assertEqual(first, second)
            self.assertEqual(Path(first).parent.name, "2026-10-01")
            self.assertEqual(len(list(Path(directory).rglob("*.run.json"))), 1)


class Session:
    site = slot = 1
    version = "M80-_6785"
    connected = True
    ready_generation = 1
    def __init__(self):
        self.sent = []
        self.queue = asyncio.Queue()
    def send(self, message): self.sent.append(message)
    def subscribe(self): return self.queue
    def unsubscribe(self, queue): pass


class AutomaticPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.hub = Hub()
        self.hub.update(1, 1, connected=True)
        self.sess = Session()
        self.recorder = Recorder(self.temporary.name)
        self.seq = Sequencer({"dut": {"test_timeout_sec": 1, "log_drain_sec": 0,
                                      "cfg_resend_sec": .01}},
                             SimpleNamespace(get=lambda site, slot: self.sess), self.hub, self.recorder)
        self.results = {}
    async def asyncTearDown(self):
        await self.seq.close()
        self.temporary.cleanup()
    async def begin(self, policy):
        self.seq.policy_provider = lambda: policy
        await self.seq.start([(1, 1)], "B", outcomes=self.results)
    async def complete(self):
        await until(lambda: bool(self.results))
        return self.results[(1, 1)]

    async def test_ack_timeout_stops_retry_and_has_specific_failure(self):
        await self.begin(RunPolicy(cfgAckTimeoutSec=.05))
        result = await self.complete()
        self.assertEqual(result["failItem"], "cfg_ack_timeout")
        before = len(self.sess.sent)
        await asyncio.sleep(.03)
        self.assertEqual(len(self.sess.sent), before)

    async def test_version_rejection_never_sends_cfg_even_during_log_drain(self):
        self.seq.log_drain_sec = .04
        await self.begin(RunPolicy(checkReadyVersion=True, expectedReadyVersion="WRONG",
                                   cfgRetryIntervalSec=.005))
        result = await self.complete()
        self.assertIn("version_mismatch", result["failItem"])
        self.assertEqual(self.sess.sent, [])

    async def test_pass_without_required_config_ack_cannot_be_success(self):
        await self.begin(RunPolicy(cfgAckTimeoutSec=.2))
        await until(lambda: bool(self.sess.sent))
        self.sess.queue.put_nowait(TestDone("PASS"))
        self.assertEqual((await self.complete())["failItem"], "cfg_ack_missing")

    async def test_repeated_stage_progress_does_not_extend_budget(self):
        await self.begin(RunPolicy(stageTimeoutSec={"PL": .06, "LK": 0, "APK": 0}))
        await until(lambda: bool(self.sess.sent))
        self.sess.queue.put_nowait(Ack(0x15, 0))
        for _ in range(4):
            self.sess.queue.put_nowait(Progress("same", "PL", 20, 1, 1))
            await asyncio.sleep(.018)
        self.assertEqual((await self.complete())["failItem"], "stage_timeout:PL")

    async def test_policy_and_cfg_are_frozen_and_archived_with_actual_identifier(self):
        policy = RunPolicy(cfgAckTimeoutSec=.2)
        self.seq.set_cfg_text("AgingTime=0\nPatternTest=1\n")
        await self.begin(policy)
        await until(lambda: bool(self.sess.sent))
        original_revision = policy.revision
        policy.cfgAckTimeoutSec = .001
        self.seq.set_cfg_text("AgingTime=999\n")
        self.sess.queue.put_nowait(Ack(0x15, 0))
        self.sess.queue.put_nowait(Progress("PL", "PL", 50, .01, 1))
        self.sess.queue.put_nowait(TestDone("PASS"))
        self.assertEqual((await self.complete())["result"], "PASS")
        record = json.loads(next(Path(self.temporary.name).rglob("*.run.json")).read_text())
        self.assertEqual(record["policyRevision"], original_revision)
        self.assertEqual(record["cfgText"], "AgingTime=0\nPatternTest=1\n")
        self.assertEqual(record["observedReadyVersion"], self.sess.version)
        self.assertTrue(record["cfgAcked"])
        self.assertEqual(record["outcome"]["result"], "PASS")
        self.assertEqual(record["stageEvents"][0]["stage"], "PL")


def progress_frame(stage):
    body = json.dumps(dict(stage=stage, step=stage, progress=10, durationSec=1, countdownSec=1)).encode()
    return build_frame(1, 0x18, bytes([1, DT_STRING]) + body)


class ManualPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.md = Power()
        self.md.ready_timeout_sec = .2
        self.md.power_off_on_fail = False
        self.hub = Hub()
        self.runner = ManualRunner(self.md, self.hub)
        self.runner._transports = {1: FakeTransport(), 2: FakeTransport()}
        self.runner.record_sink = Recorder(self.temporary.name)
    async def asyncTearDown(self):
        await self.runner.close()
        self.temporary.cleanup()

    async def test_manual_ignores_production_ready_version_policy(self):
        self.runner.production_policy_provider = lambda: RunPolicy(checkReadyVersion=True, expectedReadyVersion="WRONG")
        await self.runner.power(1, True)
        self.runner.on_datagram(1, ready_frame())
        self.assertEqual(self.runner.state(1)["state"], "cfg_sent")
        self.assertTrue(any(packet[0][4] == 0x15 for packet in self.runner._transports[1].sent))
        self.assertEqual(self.runner._st[1]['_policy'], RunPolicy())
        json.dumps(self.runner.snapshot())

    async def test_manual_uses_own_ready_timeout_not_production_ack_or_retry_limits(self):
        self.md.ready_timeout_sec = .5
        self.runner.production_policy_provider = lambda: RunPolicy(cfgAckTimeoutSec=.04, cfgRetryIntervalSec=.01)
        await self.runner.power(1, True)
        await asyncio.sleep(.12)
        self.runner.on_datagram(1, ready_frame())
        await asyncio.sleep(.055)
        self.assertEqual(self.runner.state(1)["state"], "cfg_sent")
        await until(lambda: self.runner.state(1)["state"] == "timeout")
        self.assertNotEqual(self.runner.state(1)["detail"], "cfg_ack_timeout")
        self.assertEqual(self.runner.state(1)['readyLimit'], self.md.ready_timeout_sec)
        self.assertEqual(self.runner.state(1)['runLimit'], self.md.test_timeout_sec)
        self.assertEqual(self.runner._st[1]['_policy'].cfgRetryIntervalSec, 0)

    async def test_manual_pass_does_not_inherit_production_ack_requirement(self):
        self.runner.production_policy_provider = lambda: RunPolicy(cfgAckTimeoutSec=.2)
        await self.runner.power(1, True)
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, done_frame())
        self.assertEqual(self.runner.state(1)["state"], "pass")

    async def test_manual_stage_progress_does_not_inherit_production_stage_limits(self):
        self.runner.production_policy_provider = lambda: RunPolicy(stageTimeoutSec={"PL": .5, "LK": .05, "APK": 0})
        await self.runner.power(1, True)
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, ack_frame())
        self.runner.on_datagram(1, progress_frame("PL"))
        await asyncio.sleep(.01)
        self.runner.on_datagram(1, progress_frame("LK"))
        for _ in range(3):
            await asyncio.sleep(.02)
            self.runner.on_datagram(1, progress_frame("LK"))
        self.assertEqual(self.runner.state(1)["state"], "running")
        self.assertEqual(self.runner._st[1]['_policy'].stageTimeoutSec.LK, 0)

    async def test_reboot_latches_failure_before_hard_deadline(self):
        await self.runner.power(1, True)
        self.runner._st[1]["runLimit"] = .08
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, ack_frame())
        await asyncio.sleep(.035)
        deadline = self.runner._st[1]["_hardDeadline"]
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, ack_frame())
        self.assertEqual(self.runner.state(1)["state"], "fail")
        self.assertEqual(self.runner._st[1]["_hardDeadline"], deadline)
        self.assertEqual(self.runner.state(1)["detail"], "dut_reboot")
        await asyncio.sleep(.06)  # 原运行期限经过也不能覆盖最初的重启原因。
        self.assertEqual(self.runner.state(1)["detail"], "dut_reboot")

    async def test_fast_reboot_before_watcher_scheduled_also_keeps_deadline(self):
        await self.runner.power(1, True)
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, ack_frame())
        first = self.runner._st[1]["_hardDeadline"]
        # 不yield：模拟同一批透传缓冲区里连续到达的READY/ACK。
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, ack_frame())
        self.assertEqual(self.runner._st[1]["_hardDeadline"], first)
        self.assertEqual(self.runner.state(1)["state"], "fail")
        self.assertEqual(self.runner.state(1)["detail"], "dut_reboot")

    async def test_reboot_does_not_open_another_handshake_window(self):
        await self.runner.power(1, True)
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, ack_frame())
        self.runner._st[1]["_readyStartedAt"] -= 10
        hard = self.runner._st[1]["_hardDeadline"]
        self.runner.on_datagram(1, ready_frame())
        await asyncio.sleep(.015)
        self.assertEqual(self.runner.state(1)["state"], "fail")
        self.assertEqual(self.runner._st[1]["_hardDeadline"], hard)
        self.runner.on_datagram(1, ack_frame())
        self.runner.on_datagram(1, done_frame())
        self.assertEqual(self.runner.state(1)["state"], "fail")
        self.assertEqual(self.runner.state(1)["detail"], "dut_reboot")

    async def test_manual_policy_snapshot_result_and_power_only_compatibility(self):
        policy = RunPolicy(cfgAckTimeoutSec=.2)
        self.runner.production_policy_provider = lambda: policy
        await self.runner.power(1, True)
        policy.expectedReadyVersion = "later"
        policy.checkReadyVersion = True
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, ack_frame())
        self.runner.on_datagram(1, done_frame())
        self.assertEqual(self.runner.state(1)["state"], "pass")
        record = json.loads(next(Path(self.temporary.name).rglob("*.run.json")).read_text())
        self.assertFalse(record["policy"]["checkReadyVersion"])
        self.assertEqual(record["outcome"]["result"], "PASS")
        await self.runner.power(1, False)
        self.md.run_mode = "power_only"
        self.runner.production_policy_provider = lambda: (_ for _ in ()).throw(PolicyUnavailable("invalid"))
        self.md.run_mode = "full_run"
        await self.runner.power(1, True)
        self.runner.on_datagram(1, ready_frame())
        self.assertEqual(self.runner.state(1)["state"], "cfg_sent")
        await self.runner.power(1, False)
        self.md.run_mode = "power_only"
        await self.runner.power(1, True)
        self.assertEqual(self.runner.state(1)["state"], "idle")


class RuntimePolicyApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = profile_api_fixture.ProductApiTests.asyncSetUp
    asyncTearDown = profile_api_fixture.ProductApiTests.asyncTearDown

    async def test_save_ack_roundtrip_and_stale_revision_rejected(self):
        original = self.main.run_policy_store.status()["revision"]
        reply = await self.client.post("/api/runtime-policy", RunPolicy(cfgAckTimeoutSec=30).model_dump(),
                                       {"If-Match": original})
        self.assertEqual(reply.status_code, 200)
        self.assertTrue(reply.json()["ok"])
        stale = await self.client.post("/api/runtime-policy", RunPolicy().model_dump(),
                                       {"If-Match": original})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.main.run_policy_store.snapshot().cfgAckTimeoutSec, 30)
        self.assertEqual(json.loads(self.main.settings_store.path.read_text())["runtimePolicy"]["cfgAckTimeoutSec"], 30)

    async def test_invalid_body_never_updates_policy(self):
        before = self.main.run_policy_store.status()
        for value in (True, math.nan, math.inf, -1):
            reply = await self.client.post("/api/runtime-policy", {"cfgAckTimeoutSec": value})
            self.assertEqual(reply.status_code, 422)
        self.assertEqual(self.main.run_policy_store.status(), before)
