"""测试流程引擎（cfg 驱动）。

- 下发内容 = .cfg 文本（0x15，见 cfg.py）；软件执行阶段序列（PL→LK→APK）
  由 cfg 键推导，与 mt6785 三级测试链语义一致。测试节奏由 DUT 侧驱动
  （进度经 0x18 上报），引擎负责编排、超时、落盘、广播。
- P4 真实化：在 cfg.py 接前端 ProductProfile；测试项插件注册表在此恢复
  （Step 基类 + @register，映射 .cfg 测试项与三级链判定），引擎结构不变。

计数与状态：successCount/totalCount 由 Hub 维护。
"""

import asyncio
import time
import hashlib
import uuid
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

from .cfg import build_cfg, stages_from_cfg_text
from .timing_catalog import firmware_error as timing_firmware_error
from .connection import ConnectionManager, DutSession, _DutReboot, _Offline
from .protocol import Ack, DutLog, Progress, StartTest, StopTest, TestDone
from .recorder import Recorder
from .ws import Hub
from .runtimepolicy import RunPolicy, RunGuard

Key = Tuple[int, int]   # (site, slot)


class SequencerBusyError(RuntimeError):
    """An exclusive scan owns the automatic test engine."""

PowerHook = Callable[[List[Key]], Awaitable[float]]
"""上电前置钩子：对 targets 执行通讯板断电→上电→(IO 控制) 流程，
返回上电窗口秒数（首批延迟 + 批数×批间隔）。由 main.py 在
commboard.enabled 时注入（控制面阻塞 I/O 走 to_thread）。"""


class Sequencer:
    def __init__(self, cfg: dict, conns: ConnectionManager, hub: Hub, recorder: Recorder):
        self.cfg = cfg
        self.conns = conns
        self.hub = hub
        self.recorder = recorder
        # 每通道终态回调（Handler 聚合上报用；None 安全）。签名 (site, slot, result)
        self.on_result: Optional[Callable[[int, int, str], None]] = None
        self.cfg_text = build_cfg(cfg)
        self.configuration_plan = None
        self.stages = stages_from_cfg_text(self.cfg_text)
        self.test_timeout = float(cfg.get("dut", {}).get("test_timeout_sec", 600))
        # 0x15 配置重发间隔：旧上位机 DutMaster 语义——StartRetryTimer(5000,
        # EVT_SND_CONFIG)，每 5s 重发 0x15 直到收到 DUT 的 0x15 ACK 才停
        self.log_drain_sec = float(cfg.get("dut", {}).get("log_drain_sec", 2.0))
        self.cfg_resend_sec = float(cfg.get("dut", {}).get("cfg_resend_sec", 5.0))
        # 上电后等 0x10 的窗口（旧 DutManagerCfg.DutConnectTimeoutSecond"启动超时"）
        self.boot_timeout_sec = float(cfg.get("dut", {}).get("boot_timeout_sec", 60))
        # 通讯板上电前置钩子（旧 DutsManager ST_WORKING 链：断电→上电→IO 控制）；
        # None = 无通讯板（TCP/串口直连/纯 mock），沿用"仅在线通道可启动"
        self.power_hook: Optional[PowerHook] = None
        self.tasks: Dict[Key, asyncio.Task] = {}
        self._contexts: Dict[Key, dict] = {}
        self._preparing: set[asyncio.Task] = set()
        self._reservation = None
        self.power_cancel_hook: Optional[Callable[[List[Key]], Awaitable[None]]] = None
        # 生产装配注入同一授权服务；只在接纳新轮次时判定。
        self.authorize_start: Optional[Callable[[], None]] = None
        self.policy_provider = RunPolicy


    def set_cfg_text(self, cfg_text: str, plan=None) -> None:
        """POST /api/config 带产品档案时换下发配置（P4）。已在测通道不受影响：
        start() 时已按当时的 cfg/stages 捕获进各自任务。"""
        if self._reservation is not None:
            raise SequencerBusyError("扫描作业进行中，不能更换生产配置")
        self.cfg_text = cfg_text
        import copy
        self.configuration_plan = copy.deepcopy({key:plan.get(key) for key in
            ('configurationStatus','rejectedParameters','timing')} if plan else None)
        self.stages = stages_from_cfg_text(cfg_text)

    # ---------------- 启停入口 ----------------

    @property
    def reserved(self):
        return self._reservation is not None

    def reserve(self, owner):
        if self._reservation is not None or any(not t.done() for t in self.tasks.values()) or self._preparing:
            raise SequencerBusyError("测试引擎已被其他作业占用")
        self._reservation = owner

    def release(self, owner):
        if self._reservation is owner:
            self._reservation = None

    async def start(self, targets: List[Key], batch: str, *, cfg_text=None,
                    owner=None, outcomes=None, run_policy=None) -> List[Key]:
        if self._reservation is not None and self._reservation is not owner:
            raise SequencerBusyError("扫描作业进行中，暂不接纳普通测试")
        # 先去重并预约，再进行任何 await / 电源副作用。
        keys = [key for key in dict.fromkeys(targets)
                if self.conns.get(*key) is not None
                and (key not in self.tasks or self.tasks[key].done())
                and (self.power_hook is not None or self.hub.ensure(*key).get("connected"))]
        if not keys:
            return []
        if self.authorize_start is not None:
            self.authorize_start()
        policy = (run_policy or self.policy_provider()).model_copy(deep=True)
        cfg_text = self.cfg_text if cfg_text is None else cfg_text
        stages = stages_from_cfg_text(cfg_text)
        contexts = {key: {"cancelled": False, "outcomes": outcomes,
                          "runId": uuid.uuid4().hex, "startedAt": time.time(),
                          "cfg": cfg_text, "stages": list(stages), "_policy": policy,
                          "configurationPlan": self.configuration_plan if cfg_text==self.cfg_text else None,
                          "batch": batch,
                          "ready": getattr(self.conns.get(*key), "ready_generation", 0)}
                    for key in keys}
        self._contexts.update(contexts)
        for key, ctx in contexts.items():
            self._record_context(key, ctx)
        prepare = asyncio.create_task(self._prepare(keys, contexts, batch))
        self._preparing.add(prepare)
        prepare.add_done_callback(self._preparing.discard)
        for key in keys:
            task = asyncio.create_task(self._lifecycle(key, contexts[key], prepare, batch, cfg_text, stages))
            task.add_done_callback(self._log_task_crash)
            self.tasks[key] = task
            self.hub.update(*key, state="TESTING", step="准备上电" if self.power_hook else "准备测试",
                            progress=0, durationSec=0, countdownSec=0, result=None, failItem=None, testInfo="")
        online = await asyncio.shield(prepare)
        return [key for key in keys if key in online and not contexts[key]["cancelled"]]

    async def _prepare(self, keys, contexts, batch) -> set:
        if self.power_hook is None:
            return set(keys)
        try:
            for key in keys:
                sess = self.conns.get(*key)
                sess._ignore_frames = False
                sess._awaiting_ready = True
                sess.connected = False
                self.hub.update(*key, connected=False, step="等待 READY")
            window = await self.power_hook(keys)
            online = await self._wait_online(keys, window + self.boot_timeout_sec, contexts)
            for key in keys:
                if not contexts[key]["cancelled"] and key not in online:
                    self._boot_timeout(key, batch)
            return online
        except Exception as exc:
            self.hub.syslog("ERROR", f"通讯板上电流程失败：{exc}")
            for key in keys:
                if not contexts[key]["cancelled"]:
                    self.hub.update(*key, connected=False)
                    self._boot_timeout(key, batch, f"power_control_error: {exc}")
            return set()

    async def _lifecycle(self, key, ctx, prepare, batch, cfg_text, stages):
        try:
            online = await asyncio.shield(prepare)
            if ctx["cancelled"]:
                raise asyncio.CancelledError
            if key in online and not ctx["cancelled"]:
                self.conns.get(*key)._awaiting_ready = False
                await self._run_test(*key, batch, cfg_text, stages)
            if (self.power_hook and self.power_cancel_hook
                    and not ctx["cancelled"] and self.hub.ensure(*key)["state"] == "FAIL"):
                try:
                    await self.power_cancel_hook([key])
                except Exception as exc:
                    self.hub.update(*key, testInfo=self.hub.ensure(*key)["testInfo"] + f" · 自动下电失败: {exc}")
                else:
                    self.conns.get(*key)._ignore_frames = True
                    self.conns.get(*key).connected = False
                    self.hub.update(*key, connected=False)
        except asyncio.CancelledError:
            ctx["cancelled"] = True
            ctx.setdefault("outcome", {"result": "CANCEL", "failItem": "cancelled", "durationSec": 0.0})
            # 已经提交的电源线程必须结束，随后补偿下电；不会继续下发 cfg。
            await asyncio.shield(prepare)
            try:
                if self.power_hook and self.power_cancel_hook:
                    await self.power_cancel_hook([key])
                    self.conns.get(*key)._ignore_frames = True
                    self.conns.get(*key).connected = False
                    self.hub.update(*key, connected=False)
            except Exception as exc:
                self.hub.update(*key, state="FAIL", testInfo=f"停止后下电失败: {exc}")
                self.hub.syslog("ERROR", f"{key} 停止后下电失败：{exc}")
            else:
                state = "IDLE" if self.hub.ensure(*key).get("connected") else "OFFLINE"
                self.hub.update(*key, state=state, step="-", progress=0, countdownSec=0, testInfo="手动停止")
            # 在准备阶段取消，_run_test 尚未运行，仍要通知 Handler 收尾。
            if not ctx.get("cancel_reported") and self.on_result:
                self.on_result(*key, "CANCEL")
            raise
        finally:
            if ctx.get("outcomes") is not None:
                ctx["outcomes"][key] = dict(ctx.get("outcome", {
                    "result": "UNKNOWN", "failItem": "missing_result", "durationSec": 0.0}))
            ctx["finishedAt"] = time.time()
            self._record_context(key, ctx)
            sess = self.conns.get(*key)
            sess._awaiting_ready = False
            if self.tasks.get(key) is asyncio.current_task():
                self.tasks.pop(key, None)
                self._contexts.pop(key, None)

    def _record_context(self, key, ctx):
        if not ctx.get("runId") or not hasattr(self.recorder, "write_run_record"):
            return
        guard = ctx.get("_guard")
        record = {"schemaVersion": 1, "runId": ctx["runId"], "origin": "automatic",
                  "site": key[0], "slot": key[1], "batch": ctx["batch"],
                  "startedAt": ctx["startedAt"], "finishedAt": ctx.get("finishedAt"),
                  "cfgSentAt": ctx.get("cfgSentAt"),
                  "cfgText": ctx["cfg"], "cfgSha256": hashlib.sha256(ctx["cfg"].encode()).hexdigest(),
                  "stages": ctx["stages"], "policy": ctx["_policy"].model_dump(),
                  "policyRevision": ctx["_policy"].revision,
                  "observedReadyVersion": ctx.get("observedReadyVersion"),
                  "cfgAcked": bool(guard and guard.acked),
                  "stageEvents": guard.observations if guard else [],
                  "outcome": ctx.get("outcome")}
        from .timing_reports import for_run
        record['configurationPlan']=ctx.get('configurationPlan')
        record['timingReadbacks']=for_run(self.hub,ctx['cfg'],key[0],key[1],ctx['startedAt'])
        try:
            self.recorder.write_run_record(record)
        except Exception as exc:
            self.hub.syslog("ERROR", f"{key} 本轮快照保存失败: {exc}")

    async def _wait_online(self, targets: List[Key], timeout_sec: float, contexts=None) -> set:
        pending = set(targets)
        online = set()
        deadline = asyncio.get_running_loop().time() + timeout_sec
        while pending and asyncio.get_running_loop().time() < deadline:
            for key in list(pending):
                ctx = contexts.get(key, {}) if contexts else {}
                if ctx.get("cancelled"):
                    pending.discard(key)
                    continue
                sess = self.conns.get(*key)
                fresh = contexts is None or getattr(sess, "ready_generation", 0) > ctx.get("ready", 0)
                if fresh and self.hub.ensure(*key).get("connected"):
                    pending.discard(key)
                    online.add(key)
            if pending:
                await asyncio.sleep(0.05)
        return online

    def _boot_timeout(self, key: Key, batch: str, fail_item: str = "dut_conn_timeout") -> None:
        """上电窗口内未收到 0x10 —— 旧码 ExcuteConnTimeout：
        ERR_CODE_TIMEOUT + SCODE_DUT_CONN_TIMEOUT(0xFD)「测试板启动超时」"""
        site, slot = key
        ctx = self._contexts.get(key, {})
        if ctx.get("finalized"):
            return
        ctx["finalized"] = True
        ctx["outcome"] = {"result": "FAIL", "failItem": fail_item, "durationSec": 0.0}
        self.hub.log(site, slot, "ERROR",
                     f"CH{slot:02d} 测试板启动超时（上电后未收到 0x10）", cat="conn")
        self.hub.result(site, slot, "FAIL", fail_item, 0.0)
        try:
            self.recorder.append_result(batch, site, slot, "FAIL", fail_item, 0.0)
        except Exception as exc:
            self.hub.syslog("ERROR", f"{key} 失败结果落盘失败: {exc}")
        if self.on_result:
            self.on_result(site, slot, "FAIL")

    def _log_task_crash(self, task: asyncio.Task) -> None:
        """任务异常必须可见（create_task 持有引用时 asyncio 不会打印）"""
        if not task.cancelled() and task.exception() is not None:
            self.hub.syslog("ERROR", f"测试任务异常退出: {task.exception()!r}")

    async def stop(self, targets: List[Key]) -> List[Key]:
        stopped = []
        tasks = []
        for key in dict.fromkeys(targets):
            task = self.tasks.get(key)
            if (task and not task.done()
                    and self.hub.ensure(*key)["state"] not in ("PASS", "FAIL")):
                self._contexts.get(key, {})["cancelled"] = True
                stopped.append(key)
                tasks.append(task)
        # 让刚预约、尚未执行第一行的任务进入其 try/finally，再取消。
        await asyncio.sleep(0)
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return stopped

    async def close(self) -> None:
        await self.stop(list(self.tasks))
        await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
        await asyncio.gather(*list(self._preparing), return_exceptions=True)

    # ---------------- 单工位测试主流程 ----------------

    async def _run_test(self, site: int, slot: int, batch: str,
                        cfg_text: str, stages: List[str]) -> None:
        sess: DutSession = self.conns.get(site, slot)
        first = stages[0] if stages else "-"
        writer = None
        q = None
        finished = False
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        cfg_acked = asyncio.Event()
        resend_task = None
        ctx = self._contexts.get((site, slot), {})
        policy = ctx.get("_policy") or self.policy_provider()
        guard = RunGuard(policy, stages, t0)
        ctx["_guard"] = guard
        try:
            writer = self.recorder.start_run(site, slot, batch)
            q = sess.subscribe()
            self.hub.update(site, slot, state="TESTING", step=first, progress=0,
                            durationSec=0.0, countdownSec=0.0, result=None,
                            failItem=None, testInfo=first)
            sess._testing_since = time.monotonic()   # dut_reboot 2s 宽限起点
            ctx["observedReadyVersion"] = str(getattr(sess, "version", "") or "").replace("\x00", "").strip()
            writer.write_log("INFO", f"@START_TEST batch={batch} stages={stages} runId={ctx.get('runId', '-')}")
            failure = (timing_firmware_error(cfg_text, ctx["observedReadyVersion"])
                       or policy.version_failure(ctx["observedReadyVersion"]))
            if failure:
                finished = True
                await self._finish(site, slot, batch, TestDone(result="FAIL", failItem=failure,
                                   durationSec=loop.time() - t0), writer, q)
                return
            ctx["cfgSentAt"] = time.time()
            guard.sent_at = guard.cfg_sent_at = loop.time()
            sess.send(StartTest(cfg=cfg_text))
            resend_task = asyncio.create_task(self._resend_cfg_loop(
                sess, cfg_text, cfg_acked, q, policy.cfgRetryIntervalSec or self.cfg_resend_sec))

            async with asyncio.timeout(self.test_timeout):
                while True:
                    failure = guard.expired(loop.time())
                    if failure:
                        raise TimeoutError(failure)
                    left = guard.remaining(loop.time())
                    evt = await asyncio.wait_for(q.get(), left) if left is not None else await q.get()
                    if isinstance(evt, Progress):
                        if guard.observe(evt.stage, loop.time()):
                            writer.write_log("INFO", f"@STAGE_ENTER {evt.stage}")
                            self._record_context((site, slot), ctx)
                        self.hub.update(site, slot, state="TESTING", step=evt.step,
                                        progress=evt.progress,
                                        durationSec=evt.durationSec,
                                        countdownSec=evt.countdownSec,
                                        testInfo=evt.stage or evt.step)
                    elif isinstance(evt, Ack):
                        # DUT 确认 0x15 → 停止配置重发（旧上位机 StopTimeoutRetry）
                        if evt.cmd == 0x15:
                            if evt.status != 0:
                                finished = True
                                await self._finish(site, slot, batch, TestDone(result="FAIL", failItem=f"cfg_ack_rejected:{evt.status}", durationSec=loop.time() - t0), writer, q)
                                return
                            if not cfg_acked.is_set():
                                cfg_acked.set()
                                guard.ack()
                                self.hub.log(site, slot, "INFO",
                                             f"CH{slot:02d} DUT 已确认配置（0x15 ACK），停止重发")
                            writer.write_log("INFO", f"@CFG_ACK status={evt.status}")
                    elif isinstance(evt, DutLog):
                        writer.write_log(evt.level, evt.msg)
                    elif isinstance(evt, TestDone):
                        if evt.result == "PASS" and policy.cfgAckTimeoutSec > 0 and not guard.acked:
                            evt = TestDone(result="FAIL", failItem="cfg_ack_missing",
                                           durationSec=loop.time() - t0)
                        if evt.durationSec <= 0:
                            evt.durationSec = loop.time() - t0
                        finished = True
                        await self._finish(site, slot, batch, evt, writer, q)
                        return
                    elif isinstance(evt, _DutReboot):
                        # 测试中 DUT 重启（0x10 复现）——旧上位机 FAIL2/0xFE 语义
                        evt = TestDone(result="FAIL", failItem="dut_reboot",
                                       durationSec=loop.time() - t0)
                        finished = True
                        await self._finish(site, slot, batch, evt, writer, q)
                        return
                    elif isinstance(evt, Exception):
                        raise evt
                    elif isinstance(evt, _Offline):
                        evt = TestDone(result="FAIL", failItem="连接断开",
                                       durationSec=loop.time() - t0)
                        finished = True
                        await self._finish(site, slot, batch, evt, writer, q)
                        return
        except TimeoutError:
            evt = TestDone(result="FAIL", failItem=guard.expired(loop.time()) or "timeout",
                           durationSec=loop.time() - t0)
            finished = True
            await self._finish(site, slot, batch, evt, writer, q)
        except asyncio.CancelledError:
            # 操作员手动结束：不写 CSV（见 README），状态回 IDLE
            try:
                sess.send(StopTest())
            except Exception:
                pass
            #             # 真实协议无停止命令（不发线包），P3 经通讯板复位
            self.hub.update(site, slot, state="IDLE" if self.hub.ensure(site, slot).get("connected") else "OFFLINE", step="-", progress=0,
                            countdownSec=0.0, testInfo="手动停止")
            self.hub.log(site, slot, "WARN", f"CH{slot:02d} 操作员结束测试")
            if writer is not None:
                writer.close(note="手动停止，不生成记录")
            self._contexts.get((site, slot), {})["cancel_reported"] = True
            if self.on_result:
                self.on_result(site, slot, "CANCEL")   # Handler 聚合按 0（未完成）计
            raise
        except Exception as exc:
            self.hub.syslog("ERROR", f"S{site} CH{slot} 测试执行异常: {exc}")
            if not finished:
                finished = True
                await self._finish(site, slot, batch, TestDone(result="FAIL", failItem=f"runtime_error:{exc}", durationSec=loop.time() - t0), writer, q)
        finally:
            if resend_task is not None:
                resend_task.cancel()
                await asyncio.gather(resend_task, return_exceptions=True)
            if q is not None:
                sess.unsubscribe(q)
            if writer is not None:
                writer.close()
            key = (site, slot)
            if self.tasks.get(key) is asyncio.current_task() and key not in self._contexts:
                self.tasks.pop(key, None)

    async def _drain_log(self, sess, q, writer):
        deadline = asyncio.get_running_loop().time() + self.log_drain_sec
        while q is not None and writer is not None:
            left = deadline - asyncio.get_running_loop().time()
            if left <= 0:
                return
            try:
                evt = await asyncio.wait_for(q.get(), left)
            except TimeoutError:
                return
            if isinstance(evt, DutLog):
                writer.write_log(evt.level, evt.msg)

    async def _resend_cfg_loop(self, sess: DutSession, cfg_text: str,
                               acked: asyncio.Event, q=None, interval=None) -> None:
        """0x15 每 cfg_resend_sec 重发直到 DUT ACK（旧上位机 5s 重发语义；
        总时长仍受 test_timeout 约束，不会无限重发）"""
        try:
            while not acked.is_set():
                try:
                    await asyncio.wait_for(acked.wait(), interval or self.cfg_resend_sec)
                except TimeoutError:
                    if acked.is_set():
                        return
                    sess.send(StartTest(cfg=cfg_text))
                    self.hub.log(sess.site, sess.slot, "WARN",
                                 f"CH{sess.slot:02d} 未收到 0x15 ACK，重发配置")
        except asyncio.CancelledError:
            return
        except Exception as exc:
            if q is None:
                raise
            q.put_nowait(exc)

    async def _finish(self, site: int, slot: int, batch: str,
                      evt: TestDone, writer, q=None) -> None:
        self._contexts.get((site, slot), {})["outcome"] = {
            "result": evt.result, "failItem": evt.failItem, "durationSec": evt.durationSec}
        self.hub.result(site, slot, evt.result, evt.failItem, evt.durationSec)
        self.hub.log(site, slot,
                     "INFO" if evt.result == "PASS" else "ERROR",
                     f"@TEST_DONE S{site:02d} CH{slot:02d} {evt.result}"
                     + ("" if evt.result == "PASS" else f" · fail_item={evt.failItem}")
                     + f" · 耗时 {evt.durationSec:.1f}s")
        await self._drain_log(self.conns.get(site, slot), q, writer)
        if writer is not None:
            writer.write_log("INFO", f"@TEST_DONE {evt.result} failItem={evt.failItem} "
                                 f"duration={evt.durationSec:.1f}s")
            writer.close()
        self.recorder.append_result(batch, site, slot, evt.result,
                                    evt.failItem, evt.durationSec)
        if self.on_result:
            self.on_result(site, slot, evt.result)
