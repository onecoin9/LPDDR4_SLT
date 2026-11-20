"""手动调试「完整运行」编排（debug/manual-4dut）：READY → cfg → ACK 状态机。

握手语义与旧上位机 BLL/Model/DutMaster.StateMachine.cs 逐条对齐：
  - DUT 上电后自发 0x10 READY（16B：apHWCode/apHWSubCode/apHWVer/apSWVer
    u16 LE + sfData[4] + sfVer[4]）——旧码 ST_WAIT_BEGING + EVT_SLAVE_READY；
  - 上位机回 0x15 START_TEST（载荷 = 整份 cfg 文本，旧码
    DutProtocol.GenerateStartTestPackage(_testBoardCfg.ConfigBytes)），
    每 5s 重发直到收到 DUT 的 0x15 ACK（旧码 StartRetryTimer(5000,
    EVT_SND_CONFIG)；ACK 帧 len=2 data=[0x00,status]，status=0 成功）；
  - 收到 ACK → 运行中（旧码 DoActionRecvStartAck「测试板收到参数开始执行」），
    随后测试日志经 UDP 63001 上来；
  - 等 READY + cfg ACK 的总窗口 = manual_debug.ready_timeout_sec（默认 180s，
    旧码 DutConnectTimeoutSecond「启动超时」语义），超时标记 timeout；
  - 完整运行中再收 0x10 = DUT 重启，锁存 FAIL(dut_reboot)，停止计时，
    不自动重新下发 cfg；只有显式开启新轮才重新测试。

传输（背景已实证）：上位机 → 通讯板 UDP 2000+dut（板转发到 DUT 的 UART）；
DUT 回的 0xAF 帧 → 板转发到 server_ip:2000+dut。本类为每路 DUT 绑定本地
UDP 2000+dut 收发（与板侧端口语义一致），收发同 socket。
"""
from __future__ import annotations

import asyncio
import re
import time
import hashlib
import uuid
from typing import Dict, Optional

from .protocol import (CMD_AGING_REQ, CMD_READY, CMD_START_TEST, Ack,
                       AgingTimeAnswer, AgingTimeRequest, DramInfo, DutLog,
                       HsgCodec, Progress, PwrKeySet, Ready, StartTest,
                       TestDone)
from .cfg import stages_from_cfg_text
from .timing_catalog import firmware_error as timing_firmware_error
from .runtimepolicy import RunPolicy, RunGuard

ST_IDLE = "idle"                # 未在完整运行中
ST_WAIT_READY = "wait_ready"    # 已上电，等待 DUT 0x10 READY
ST_CFG_SENT = "cfg_sent"        # 已下发 cfg，等 0x15 ACK（每 5s 重发）
ST_RUNNING = "running"          # 收到 ACK，测试运行中（日志走 63001）
ST_TIMEOUT = "timeout"          # ready_timeout_sec 内未就绪
ST_PASS = "pass"
ST_FAIL = "fail"
ST_OFFLINE = "offline"
ACTIVE = (ST_WAIT_READY, ST_CFG_SENT, ST_RUNNING)
TERMINAL = (ST_PASS, ST_FAIL, ST_TIMEOUT)

RESEND_SEC = 5.0   # 旧上位机 StartRetryTimer(5000, EVT_SND_CONFIG)
PRODUCTION_RESET_SEC = 1.0


class BoardHealthMonitor:
    """通讯板健康监控（2026-09-28 用户指令「强逻辑」）：

    通讯板坏了 → 该板连接的**所有测试板立即标记离线**——手动链路没有心跳
    会话，DUT 卡的在线态原本没有失效机制（板挂后可能一直亮"在线"）。
    恢复只打日志：DUT 由下一次上电/回帧自然回连（与 runner 语义一致）。
    掉线事件交给 runner 收尾；未开始或已结束的结果不会被连接状态覆盖。
    main.py 在 manual_debug 启用时周期调 check()。
    """

    def __init__(self, mdbg, hub, runner=None):
        self.mdbg = mdbg
        self.hub = hub
        self.runner = runner
        self.online: Optional[bool] = None   # None=未知（首查建基线，不广播）

    def _channels(self) -> list:
        return [self.mdbg.ch(i + 1) for i in range(len(self.mdbg.dut_lines))]

    async def check(self) -> bool:
        try:
            await asyncio.to_thread(self.mdbg.board_state)
            online = True
        except Exception:                    # noqa: BLE001 Modbus 无应答等
            online = False
        prev, self.online = self.online, online
        chs = self._channels()
        if not online and prev is not False:
            if self.runner is not None:
                self.runner.board_offline()
            for ch in ([] if self.runner is not None else chs):
                self.hub.update(1, ch, connected=False, state="OFFLINE",
                                step="-", progress=0, testInfo="通讯板离线")
            self.hub.syslog(
                "ERROR",
                f"通讯板 {self.mdbg.board_host} 无应答：所连 {len(chs)} 路测试板"
                f"（通道 {chs}）全部离线")
        elif prev is False and online:
            self.hub.syslog(
                "INFO", "通讯板链路恢复：测试板将在下一次上电/回帧后重新在线")
        if self.runner is not None:
            self.runner.board_online = online
        return online


class _Proto(asyncio.DatagramProtocol):
    def __init__(self, runner: "ManualRunner", dut: int):
        self.runner, self.dut = runner, dut

    def datagram_received(self, data: bytes, addr) -> None:
        self.runner.on_datagram(self.dut, data)


class ManualRunner:
    """每路 DUT 独立的完整运行状态机（asyncio；arm/disarm 须在事件循环内调用）。"""

    def __init__(self, mdbg, hub, codec: Optional[HsgCodec] = None,
                 port_base: Optional[int] = None):
        self.mdbg = mdbg
        self.hub = hub
        self.codec = codec or HsgCodec()
        self.port_base = port_base or mdbg.passthrough_base
        # 落盘钩子（logchannel.DutLogFileSink：running 起点开新文件；缺省取
        # mdbg.file_sink——main.py 注入；None=不落盘，单测夹具不传也安全）
        self.file_sink = getattr(mdbg, "file_sink", None)
        self._duts = list(range(1, len(mdbg.dut_lines) + 1))
        self._st: Dict[int, dict] = {
            d: {"state": ST_IDLE, "detail": "", "t0": 0.0, "wall0": 0.0}
            for d in self._duts}
        self._transports: Dict[int, asyncio.DatagramTransport] = {}
        self._resend: Dict[int, asyncio.Task] = {}
        self._timer: Dict[int, asyncio.Task] = {}
        self._runwatch: Dict[int, asyncio.Task] = {}
        # 进度（2026-09-24）：节拍任务 + 0x18 Progress 真值缓存 dut→(pct, t)
        self._progtask: Dict[int, asyncio.Task] = {}
        self._prog: Dict[int, tuple] = {}
        self.power_lock = asyncio.Lock()  # API 上下电、复位、自动下电共享；线程 I/O 结束才释放
        self.board_online = True
        self._run_serial = 0
        self._production_io_serial = (time.time_ns() // 1_000_000) & 0xFFFF
        self._drain_tasks: Dict[int, asyncio.Task] = {}
        self._effects: set[asyncio.Task] = set()
        self.authorize_start = None  # main.py 注入；已接纳轮次的重发/收尾不再验期
        self.production_policy_provider = RunPolicy
        self.record_sink = None
        for d, st in self._st.items():
            st.update(channel=self._ch(d), runId=0, accept_frames=getattr(self.mdbg, "_power", None) is None)


    # ---------------- 生命周期 ----------------

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        bound = []
        for d in self._duts:
            port = self.mdbg.dut_port(d)
            try:
                tr, _ = await loop.create_datagram_endpoint(
                    lambda d=d: _Proto(self, d), local_addr=("0.0.0.0", port))
                self._transports[d] = tr
                bound.append(port)
            except OSError as e:
                self.hub.syslog(
                    "ERROR", f"完整运行：DUT{d} 透传端口 {port} 绑定失败"
                             f"（{e}），该路完整运行不可用")
        if bound:
            self.hub.syslog(
                "INFO", f"完整运行透传监听：UDP {','.join(map(str, bound))}"
                        f"（DUT 0xAF 回帧 → 本机这些端口）")

    async def close(self) -> None:
        for d in self._duts:
            self.disarm(d)
        for tr in self._transports.values():
            tr.close()
        self._transports.clear()
        pending = list(self._effects)
        for t in list(self._drain_tasks.values()):
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def sync_duts(self) -> None:
        """新增 DUT 后同步（POST /api/manual/duts/add 调用）：补状态表并为
        新 DUT 绑定透传 UDP 端口。

        背景：_duts/_transports 在 __init__/start 时按当时的 dut_lines 快照
        建立——运行期 add_dut 后若不调用本方法，新 DUT 的 arm() 会被静默忽略
        （dut not in _st）、透传端口也未绑定，完整运行要等后端重启才生效。
        已存在的 DUT 不重复绑定（幂等）。须在事件循环内调用。"""
        loop = asyncio.get_running_loop()
        for d in range(1, len(self.mdbg.dut_lines) + 1):
            if d not in self._st:
                self._duts.append(d)
                self._st[d] = {"state": ST_IDLE, "detail": "", "t0": 0.0,
                               "wall0": 0.0, "channel": self._ch(d),
                               "runId": 0, "accept_frames": False}
            if d in self._transports:
                continue
            port = self.mdbg.dut_port(d)
            try:
                tr, _ = await loop.create_datagram_endpoint(
                    lambda d=d: _Proto(self, d), local_addr=("0.0.0.0", port))
                self._transports[d] = tr
                self.hub.syslog(
                    "INFO", f"完整运行透传监听新增：UDP {port}（DUT{d}）")
            except OSError as e:
                self.hub.syslog(
                    "ERROR", f"完整运行：DUT{d} 透传端口 {port} 绑定失败"
                             f"（{e}），该路完整运行不可用")

    def drop_dut(self, dut: int) -> None:
        """移除一路后的 runner 同步（POST /api/manual/duts/remove 在
        mdbg.remove_dut 收缩列表之后调用）。

        前提已由 remove_dut 的安全约束保证：被移除路电源关、状态机非活动态。
        列表收缩使其后的 DUT 序号位移（旧 od → 新 od-1），但每路的 线号↔
        通道↔端口 配对不变——所以**不需要重新绑定**：旧 transport 监听的端口
        对新序号依然正确，只把 状态表/transport/定时器/进度缓存 的键按位置
        平移，并修正 transport 协议对象里的 dut 号。被移除路的 transport
        关闭、定时器取消。须在事件循环内调用（与 arm/disarm 同约束）。"""
        self._cancel(dut)
        self._cancel_drain(self._st.get(dut, {}))
        old_st = self._st.pop(dut, None)
        if old_st and old_st["state"] in (ST_FAIL, ST_TIMEOUT):
            self.hub.syslog("WARN", f"DUT{old_st.get('channel', dut):02d} 已移除，跳过自动下电")
        del old_st                                   # 被移除路的状态丢弃（必为 idle）
        old_tr = self._transports.pop(dut, None)
        if old_tr is not None:
            old_tr.close()
        shift = lambda od: od if od < dut else od - 1
        self._st = {shift(od): st for od, st in self._st.items()}
        trs = self._transports
        self._transports = {}
        for od, tr in trs.items():
            nd = shift(od)
            self._transports[nd] = tr
            proto = getattr(tr, "get_protocol", None)
            proto = proto() if callable(proto) else None
            if isinstance(proto, _Proto):
                proto.dut = nd                       # 回帧归属改到新序号
        for tab in (self._resend, self._timer, self._runwatch,
                    self._progtask, self._prog):
            remapped = {shift(od): v for od, v in tab.items() if od != dut}
            tab.clear()
            tab.update(remapped)
        self._duts = list(range(1, len(self.mdbg.dut_lines) + 1))

    async def resync(self) -> None:
        """dut_lines/dut_channels 整体替换后（apply_settings 导入 dutLines）
        的全量对齐：关闭全部 transport、取消所有定时器，按新表重建状态机
        并重新绑定透传端口。

        与 sync_duts（增量补新）/drop_dut（移除一路、配对不变只做键位平移）
        不同：线表整体替换后既有序号的 通道↔端口 配对可能全部改变，旧
        transport 监听的端口不再正确，必须全量重绑。前提由 apply_settings
        保证：所有 DUT 已下电、无活动状态机（终态残余统一归 idle）。
        须在事件循环内调用。"""
        for tr in self._transports.values():
            tr.close()
        self._transports.clear()
        for tab in (self._resend, self._timer, self._runwatch, self._progtask):
            for t in tab.values():
                t.cancel()
            tab.clear()
        self._prog.clear()
        for st in self._st.values():
            self._cancel_drain(st)
        # 状态表清空后交给 sync_duts 统一补建（它只处理 _st 里缺失的 dut，
        # 先填 _st 会被它全部跳过、端口不绑）
        self._duts = []
        self._st = {}
        await self.sync_duts()

    # ---------------- 状态 ----------------

    def _ch(self, dut: int) -> int:
        """DUT 序号 → 真实通道号：日志归属（hub slot）/CH 标签/落盘/状态展示
        统一用通道号（2026-09-23「界面 DUT 改真实值」，与 63001 [DUTx] 前缀、
        界面页签对齐）。mdbg 未配置 dut_channels（单测夹具）时回退序号。"""
        ctx = self._st.get(dut) if hasattr(self, "_st") else None
        if ctx and "channel" in ctx:
            return ctx["channel"]
        chans = getattr(self.mdbg, "dut_channels", None) or []
        return chans[dut - 1] if 1 <= dut <= len(chans) else dut

    def state(self, dut: int) -> dict:
        return dict({k: v for k, v in self._st[dut].items() if not k.startswith("_")},
                    dut=dut, channel=self._ch(dut))

    def snapshot(self) -> dict:
        now = time.monotonic()

        def since(st: dict) -> int:
            if not st["t0"]:
                return 0
            # 冻结态（终态/idle）用停表时刻 t1，计数不随下电后继续增长
            t1 = st.get("t1")
            return round((t1 if t1 is not None else now) - st["t0"])

        return {
            "mode": self.mdbg.run_mode,
            # enteredAt = 状态进入时刻的服务端墙钟（time.time()），供前端在
            # 活跃态本地平滑 tick（事件驱动方案，2026-10-10）；0 → None
            "duts": [dict(self.state(d), sinceSec=since(self._st[d]),
                          enteredAt=self._st[d].get("wall0") or None)
                     for d in self._duts],
        }

    def _set(self, dut: int, state: str, detail: str = "") -> None:
        ctx = self._st[dut]
        previous = ctx["state"]
        if ctx["state"] in TERMINAL and state in TERMINAL:
            return  # 终态锁存，同一轮只计数一次
        now = time.monotonic()
        if not ctx["t0"]:
            ctx.update(t0=now, wall0=time.time())
        ctx.update(state=state, detail=detail, phaseEnteredAt=time.time())
        elapsed = now - ctx["t0"]
        if state in (*TERMINAL, ST_IDLE, ST_OFFLINE):
            ctx["t1"] = now
        else:
            ctx.pop("t1", None)
        ch = self._ch(dut)
        if state in ACTIVE:
            steps = {ST_WAIT_READY: "等待 READY", ST_CFG_SENT: "下发配置", ST_RUNNING: "测试运行中"}
            if ctx.get("origin", "manual") == "manual":
                ctx.update(progress=0, step=steps[state])
            self.hub.update(1, ch, state="TESTING", connected=state != ST_WAIT_READY,
                            step=steps[state], progress=0, durationSec=elapsed,
                            countdownSec=0, testInfo=detail, result=None, failItem=None)
        elif state in TERMINAL:
            if ctx.get("origin", "manual") == "manual" and state == ST_PASS:
                ctx["progress"] = 100
            self._cancel(dut)
            self.hub.result(1, ch, "PASS" if state == ST_PASS else "FAIL",
                            "" if state == ST_PASS else detail or "ready 超时", elapsed)
            self._schedule_terminal(ctx)
        elif state in (ST_IDLE, ST_OFFLINE):
            if ctx.get("origin", "manual") == "manual":
                ctx.update(progress=0, step="-")
            connected = (state == ST_IDLE and self._powered(dut)
                         and bool(ctx.get("connected")))
            self.hub.update(1, ch, connected=connected,
                            state="IDLE" if connected else "OFFLINE", step="-",
                            progress=0, durationSec=elapsed, countdownSec=0, testInfo=detail)
            if self.file_sink is not None:
                self.file_sink.end_run(ch)
        if state == ST_RUNNING and self.file_sink is not None:
            self.file_sink.begin_run(ch)
        self._record_context(ctx)
        writer = ctx.get('_writer')
        if writer is not None and not writer._closed:
            writer.write_log('INFO', f'@STATE {state} {detail}')
        if state in TERMINAL:
            self._complete_production(ctx, 'PASS' if state == ST_PASS else 'FAIL')
        elif previous in ACTIVE and state in (ST_IDLE, ST_OFFLINE):
            self._complete_production(ctx, 'CANCEL')
            self._close_writer(ctx)
        self._notify_change()

    def _complete_production(self, ctx, result):
        if ctx.get('origin', 'manual') == 'manual' or ctx.get('_completionNotified'):
            return
        ctx['_completionNotified'] = True
        if self.record_sink is not None and result != 'CANCEL':
            try:
                self.record_sink.append_result(ctx['batch'], 1, ctx['channel'], result,
                                               ctx['detail'] if result == 'FAIL' else '',
                                               ctx.get('t1', time.monotonic()) - ctx['t0'])
            except Exception as exc:
                self.hub.syslog('ERROR', f"CH{ctx['channel']:02d} 结果保存失败: {exc}")
        cb = getattr(self, 'on_production_result', None)
        if cb is not None:
            cb(1, ctx['channel'], result)

    @staticmethod
    def _close_writer(ctx):
        writer = ctx.pop('_writer', None)
        if writer is not None:
            writer.close()

    def _run_mode(self, dut):
        if self._st[dut].get('origin') in ('monitor', 'handler'):
            return 'full_run'
        return getattr(self.mdbg, 'run_mode', 'full_run')

    def _record_context(self, ctx):
        if self.record_sink is None or not ctx.get("recordId"):
            return
        guard = ctx.get("_guard")
        cfg = ctx.get("cfg", "")
        state = ctx["state"]
        outcome = None
        if state in TERMINAL:
            outcome = {"result": "PASS" if state == ST_PASS else "FAIL",
                       "failItem": "" if state == ST_PASS else ctx["detail"],
                       "durationSec": ctx.get("t1", ctx["t0"]) - ctx["t0"]}
        elif state in (ST_IDLE, ST_OFFLINE):
            outcome = {"result": "CANCEL", "failItem": ctx["detail"],
                       "durationSec": ctx.get("t1", ctx["t0"]) - ctx["t0"]}
        record = {"schemaVersion": 1, "runId": ctx["recordId"], "origin": ctx.get('origin', 'manual'),
                  "site": 1, "slot": ctx["channel"], "batch": ctx.get('batch', 'manual'),
                  "startedAt": ctx["wall0"], "finishedAt": time.time() if outcome else None,
                  "cfgSentAt": ctx.get("cfgSentAt"),
                  "state": state, "cfgText": cfg,
                  "cfgSha256": hashlib.sha256(cfg.encode()).hexdigest(),
                  "stages": stages_from_cfg_text(cfg), "policy": ctx["_policy"].model_dump(),
                  "policyRevision": ctx["_policy"].revision,
                  "observedReadyVersion": ctx.get("readyVersion"),
                  "cfgAcked": bool(guard and guard.acked),
                  "stageEvents": guard.observations if guard else [], "outcome": outcome}
        from .timing_reports import for_run
        record['timingReadbacks']=for_run(self.hub,cfg,1,ctx['channel'],ctx['wall0'])
        record['configurationPlan'] = ctx.get('configurationPlan')
        try:
            self.record_sink.write_run_record(record)
        except Exception as exc:
            self.hub.syslog("ERROR", f"CH{ctx['channel']:02d} 本轮快照保存失败: {exc}")

    def _resolve(self, ctx: dict) -> Optional[int]:
        return next((d for d, current in self._st.items() if current is ctx), None)

    def _powered(self, dut: int) -> bool:
        power = getattr(self.mdbg, "_power", None)
        return bool(power.get(dut, False)) if power is not None else True

    def _cancel_drain(self, ctx: dict) -> None:
        task = self._drain_tasks.pop(id(ctx), None)
        if task and task is not asyncio.current_task():
            task.cancel()

    def _schedule_terminal(self, ctx: dict) -> None:
        self._cancel_drain(ctx)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self._terminal_drain(ctx))
        self._drain_tasks[id(ctx)] = task
        self._effects.add(task)
        task.add_done_callback(self._effects.discard)

    def _auto_off_states(self) -> tuple:
        """终态自动下电开关（2026-10-10 用户拍板 PASS 也断电）：
        fail/timeout 受 power_off_on_fail、pass 受 power_off_on_pass，
        两开关各自独立，默认都开。"""
        states = []
        if getattr(self.mdbg, "power_off_on_fail", True):
            states += [ST_FAIL, ST_TIMEOUT]
        if getattr(self.mdbg, "power_off_on_pass", True):
            states.append(ST_PASS)
        return tuple(states)

    async def _terminal_drain(self, ctx: dict) -> None:
        # 控制帧/文本日志分链：保留短暂尾日志窗口，旧轮不得关闭新轮文件或电源。
        try:
            await asyncio.sleep(float(getattr(self.mdbg, "log_drain_sec", 2.0)))
            dut = self._resolve(ctx)
            if dut is None or ctx["state"] not in TERMINAL:
                return
            if (ctx["state"] in self._auto_off_states()
                    and getattr(self.mdbg, "set_power", None)):
                await self._power_off_task(ctx)
            if self._resolve(ctx) is not None and self.file_sink is not None:
                self.file_sink.end_run(ctx["channel"])
        except asyncio.CancelledError:
            return
        finally:
            self._close_writer(ctx)
            self._drain_tasks.pop(id(ctx), None)

    async def _io(self, fn, *args):
        # cancel(to_thread) 不能停止已发出的 Modbus：等待真实调用结束，避免后续命令越过。
        task = asyncio.create_task(asyncio.to_thread(fn, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            return await task

    async def _power_off_task(self, ctx: dict) -> None:
        async with self.power_lock:
            dut = self._resolve(ctx)
            if dut is None or ctx["state"] not in self._auto_off_states():
                return
            ctx["accept_frames"] = False
            ctx.update(connected=False, powerAction="turning_off")
            self.hub.update(1, ctx["channel"], connected=False)
            self._notify_change()
            try:
                await self._io(self.mdbg.set_power, dut, False)
            except Exception as exc:
                ctx["powerError"] = str(exc)
                self.hub.syslog("ERROR", f"DUT{ctx['channel']:02d} 自动下电失败：{exc}")
                self.hub.update(1, ctx["channel"], connected=False,
                                testInfo=f"FAIL: {ctx['detail']} · 自动下电失败: {exc}")
            else:
                ctx["connected"] = False
                self.hub.update(1, ctx["channel"], connected=False)
                result = "PASS" if ctx["state"] == ST_PASS else "FAIL"
                self.hub.syslog("INFO", f"DUT{ctx['channel']:02d} 测试 {result}，已自动下电")
            ctx["powerAction"] = ""
            self._notify_change()

    def start_production(self, duts, cfg_text, batch, plan, *, origin, io_control,
                         ready_limit, run_limit):
        """Freeze an admitted production batch; reuse the existing physical sockets."""
        import copy
        self.mdbg._require()
        if self.authorize_start is not None:
            self.authorize_start()
        policy = self.production_policy_provider().model_copy(deep=True)
        contexts = []
        for d in duts:
            self._arm_admitted(d, cfg_text=cfg_text, policy=policy, origin=origin,
                               batch=batch, plan=copy.deepcopy(plan),
                               ready_limit=ready_limit, run_limit=run_limit)
            ctx = self._st[d]
            ctx.update(accept_frames=False, power_pending=True, powerAction='preparing')
            contexts.append(ctx)
        self._notify_change()
        task = asyncio.create_task(self._prepare_production(contexts, copy.deepcopy(io_control)))
        self._effects.add(task)
        task.add_done_callback(self._effects.discard)

    async def _prepare_production(self, contexts, io_control):
        async with self.power_lock:
            def live(ctx):
                return self._resolve(ctx) is not None and not ctx.get('_stopRequested') and ctx['state'] in ACTIVE

            if not any(live(ctx) for ctx in contexts):
                return
            try:
                await self._io(self.mdbg.board_state)
                self.board_online = True
                # Reset only explicitly configured target lines, never the whole board.
                for ctx in contexts:
                    if live(ctx):
                        await self._io(self.mdbg.set_power, self._resolve(ctx), False)
                await asyncio.sleep(PRODUCTION_RESET_SEC)
                for index, ctx in enumerate(contexts):
                    if not live(ctx):
                        continue
                    d = self._resolve(ctx)
                    ctx.update(accept_frames=True, powerAction='turning_on')
                    if self.file_sink is not None:
                        self.file_sink.begin_run(ctx['channel'])
                    await self._io(self.mdbg.set_power, d, True)
                    if io_control is not None and io_control.action != 'none' and live(ctx):
                        from .commboard import IoControl, IO_GROUP_MCU_PWR, IO_GROUP_MCU_KPCOL
                        group = IO_GROUP_MCU_PWR if io_control.action == 'power_key' else IO_GROUP_MCU_KPCOL
                        delay = io_control.startDelaySec + (index % io_control.batch) * io_control.intervalSec
                        self._production_io_serial = (self._production_io_serial + 1) & 0xFFFF
                        controls = [IoControl(group_id=group, line=self.mdbg.dut_key_lines[d-1],
                                              start_status=0, start_sec=delay,
                                              duration_msec=io_control.pulseMs)]
                        await self._io(self.mdbg._client().io_security_set, controls,
                                       self._production_io_serial)
                    ctx.update(power_pending=False, powerAction='')
                    self._notify_change()
            except Exception as exc:
                self.hub.syslog('ERROR', f'现场测试上电失败: {exc}')
                for ctx in contexts:
                    if live(ctx):
                        ctx.update(accept_frames=False, connected=False, powerError=str(exc))
                        self._set(self._resolve(ctx), ST_FAIL, f'power_control_error: {exc}')
            finally:
                for ctx in contexts:
                    ctx.update(power_pending=False, powerAction='')
                self._notify_change()

    async def power(self, dut: int, on: bool, *, all_duts: bool = False) -> dict:
        async with self.power_lock:
            ds = list(self._duts) if all_duts else [dut]
            self.mdbg._require()
            if any(d not in self._st for d in ds):
                from .manual import ManualDebugError
                raise ManualDebugError(404, f"无此 DUT: {dut}")
            # 重复上电幂等；只对原来关闭的通道开启新轮。
            new = [d for d in ds if on and not self._powered(d)]
            if new and self.authorize_start is not None:
                self.authorize_start()  # 在状态、日志和硬件副作用之前拒绝
            # Freeze one validated product for the whole admission before touching
            # state, log files or power. A product error is not a power failure.
            options = self._manual_cfg_options() if new and self.mdbg.run_mode == 'full_run' else {}
            try:
                for d in new:
                    if self.mdbg.run_mode == "full_run":
                        self._arm_admitted(d, **options)
                    else:
                        self._new_idle(d)
                    self._st[d].update(power_pending=True, powerAction="turning_on")
                    if self.file_sink is not None:
                        self.file_sink.begin_run(self._ch(d))
                if not on:
                    for d in ds:
                        self.disarm(d, powered_off=True)
                        self._st[d]["powerAction"] = "turning_off"
                self._notify_change()
                result = await self._io(self.mdbg.set_power_all, on) if all_duts else await self._io(self.mdbg.set_power, dut, on)
            except Exception as exc:
                for d in (new if on else ds):
                    self._st[d].update(power_pending=False, accept_frames=False,
                                       connected=False, powerAction="", powerError=str(exc))
                    self.hub.update(1, self._ch(d), connected=False)
                    if self._st[d]["state"] not in TERMINAL:
                        self._set(d, ST_FAIL, f"power_control_error: {exc}")
                    else:
                        self._st[d]["powerError"] = str(exc)
                        self.hub.update(1, self._ch(d), testInfo=f"{self._st[d]['detail']} · 电源控制失败: {exc}")
                self._notify_change()
                raise
            for d in ds:
                self._st[d]["power_pending"] = False
                self._st[d]["powerAction"] = ""
                if self._st[d].pop("powerError", None) is not None:
                    ctx = self._st[d]
                    text = "PASS" if ctx["state"] == ST_PASS else f"FAIL: {ctx['detail']}" if ctx["state"] in TERMINAL else ctx["detail"]
                    self.hub.update(1, self._ch(d), testInfo=text)
            self._notify_change()
            return result

    def _new_idle(self, dut: int) -> None:
        self._new_run(dut)
        self._set(dut, ST_IDLE, "只开机，等待连接")

    def _manual_cfg_options(self):
        get_plan = getattr(self.mdbg, 'get_product_plan', None)
        plan = get_plan() if get_plan is not None else None
        return {'cfg_text': plan['cfgText'], 'plan': plan} if plan is not None else {'cfg_text': self.mdbg.get_cfg_text()}

    def _new_run(self, dut: int, *, cfg_text=None, policy=None, origin='manual', batch='manual',
                 plan=None, ready_limit=None, run_limit=None) -> None:
        full_run = cfg_text is not None or self.mdbg.run_mode == 'full_run'
        if full_run and cfg_text is None:
            options = self._manual_cfg_options()
            cfg_text, plan = options['cfg_text'], options.get('plan')
        cfg = cfg_text if cfg_text is not None else ''
        # Manual runs use their own ready/run limits, never the production policy store.
        policy = RunPolicy() if origin == 'manual' else (policy or RunPolicy())
        self._cancel(dut)
        old = self._st[dut]
        self._cancel_drain(old)
        self._close_writer(old)
        # 上次尾日志窗口不与新轮文件共用。
        if self.file_sink is not None:
            self.file_sink.end_run(old["channel"])
        self.hub.update(1, old["channel"], result=None, failItem=None, connected=False, progress=0, durationSec=0, testInfo="")
        self._run_serial += 1
        self._st[dut] = dict(state=ST_IDLE, detail="", t0=time.monotonic(), wall0=time.time(),
                            channel=old["channel"], runId=self._run_serial,
                            accept_frames=True, connected=False, origin=origin, batch=batch,
                            mode='full_run' if full_run else 'power_only')
        match = re.search(r"^\s*AgingTime\s*=\s*(\d+)", cfg, re.M | re.I)
        aging = int(match.group(1)) if match else 5
        user = float(getattr(self.mdbg, "test_timeout_sec", 0) or 0)
        self._st[dut].update(cfg=cfg, aging=aging,
                             _policy=policy.model_copy(deep=True), _guardChanged=asyncio.Event(),
                             _readyStartedAt=self._st[dut]["t0"],
                             recordId=uuid.uuid4().hex if full_run else None,
                             configurationPlan=plan,
                             readyLimit=float(ready_limit if ready_limit is not None else self.mdbg.ready_timeout_sec),
                             runLimit=(run_limit if run_limit is not None else
                                       user if user > 0 else aging * 60 + 300 + 900))
        if origin != 'manual' and self.record_sink is not None:
            self._st[dut]['_writer'] = self.record_sink.start_run(1, self._ch(dut), batch)

    def board_offline(self) -> None:
        self.board_online = False
        for d in list(self._duts):
            ctx = self._st[d]
            ctx.update(connected=False, accept_frames=False)
            self.hub.update(1, self._ch(d), connected=False)
            if ctx["state"] in ACTIVE:
                self._set(d, ST_FAIL, "commboard_offline")
            elif ctx["state"] not in TERMINAL:
                self._set(d, ST_OFFLINE, "通讯板离线")
        self._notify_change()

    def _notify_change(self) -> None:
        cb = getattr(self, "on_change", None)
        if cb is not None:
            cb()


    # ---------------- 武装 / 解除 ----------------

    def arm(self, dut: int) -> None:
        """发上电指令前布防；运行期电源操作必须通过 power() 串行执行。"""
        if dut not in self._st:
            return
        if self.authorize_start is not None:
            self.authorize_start()
        self._arm_admitted(dut)

    def _arm_admitted(self, dut: int, **run_options) -> None:
        """仅由已通过门禁的 arm/power 调用；不对活动轮次反复检查到期。"""
        self._new_run(dut, **run_options)
        self._set(dut, ST_WAIT_READY)
        ch = self._ch(dut)
        self.hub.log(1, ch, "INFO",
                     f"CH{ch:02d} 完整运行：等待 DUT 0x10 READY"
                     f"（超时 {self.mdbg.ready_timeout_sec}s）", cat="conn")
        self._timer[dut] = asyncio.create_task(self._timeout_watch(dut, self._st[dut]))
        self._progtask[dut] = asyncio.create_task(self._progress_loop(dut, self._st[dut]))

    def disarm(self, dut: int, *, powered_off: bool = True) -> None:
        """下电 / 切回只开机：状态归 idle，停所有定时器。"""
        if dut not in self._st:
            return
        self._cancel(dut)
        ctx = self._st[dut]
        self._cancel_drain(ctx)
        ctx.update(accept_frames=not powered_off, connected=False)
        self.hub.update(1, self._ch(dut), connected=False)
        if ctx["state"] not in TERMINAL:
            self._set(dut, ST_IDLE, "已下电" if powered_off else "只开机")
        else:
            self._notify_change()
        if self.file_sink is not None:
            self.file_sink.end_run(self._ch(dut))

    def _cancel(self, dut: int) -> None:
        for tab in (self._resend, self._timer, self._runwatch, self._progtask):
            t = tab.pop(dut, None)
            if t and t is not asyncio.current_task():
                t.cancel()
        self._prog.pop(dut, None)

    async def _timeout_watch(self, dut: int, ctx=None) -> None:
        ctx = ctx or self._st[dut]
        limit = ctx.get("readyLimit", self.mdbg.ready_timeout_sec)
        policy = ctx.get("_policy", RunPolicy())
        cfg_phase = ctx["state"] == ST_CFG_SENT and policy.cfgAckTimeoutSec > 0
        deadline = (ctx["_guard"].cfg_sent_at + policy.cfgAckTimeoutSec
                    if cfg_phase else ctx.get("_readyStartedAt", ctx["t0"]) + limit)
        hard = ctx.get("_hardDeadline")
        if hard is not None:
            deadline = min(deadline, hard)
        guard = ctx.get("_guard")
        remaining = guard.remaining(time.monotonic()) if guard else None
        if remaining is not None:
            deadline = min(deadline, time.monotonic() + remaining)
        try:
            await asyncio.sleep(max(0, deadline - time.monotonic()))
        except asyncio.CancelledError:
            return
        dut = self._resolve(ctx)
        if dut is not None and ctx["state"] in (ST_WAIT_READY, ST_CFG_SENT):
            self._cancel(dut)
            reason = ("timeout" if hard is not None and time.monotonic() >= hard
                      else (guard.expired(time.monotonic()) if guard else None)
                      or ("cfg_ack_timeout" if cfg_phase else f"{limit}s 内未就绪"))
            self._set(dut, ST_TIMEOUT,
                      reason)
            ch = self._ch(dut)
            self.hub.log(1, ch, "ERROR",
                         f"CH{ch:02d} 完整运行超时：{reason}", cat="conn")

    # ---------------- 收发 ----------------

    def _send_cfg(self, dut: int) -> None:
        tr = self._transports.get(dut)
        if tr is None:
            return
        frame = self.codec.encode(StartTest(self._st[dut]["cfg"] if "cfg" in self._st[dut] else self.mdbg.get_cfg_text()))
        if frame:
            tr.sendto(frame, (self.mdbg.board_host, self.mdbg.dut_port(dut)))

    async def _resend_loop(self, dut: int, ctx=None) -> None:
        """旧码 StartRetryTimer(5000, EVT_SND_CONFIG)：每 5s 重发 cfg 直到 ACK。"""
        ctx = ctx or self._st[dut]
        ch = ctx["channel"]
        try:
            while True:
                await asyncio.sleep(ctx.get("_policy", RunPolicy()).cfgRetryIntervalSec or RESEND_SEC)
                dut = self._resolve(ctx)
                if dut is None or ctx["state"] != ST_CFG_SENT:
                    return
                self._send_cfg(dut)
                self.hub.log(1, ch, "INFO",
                             f"CH{ch:02d} 等待 0x15 ACK，重发 cfg", cat="conn")
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            dut = self._resolve(ctx)
            if dut is not None:
                self._set(dut, ST_FAIL, f"cfg_send_error: {exc}")

    def _begin_cfg_phase(self, dut: int, detail: str) -> None:
        """收到 READY → 下发 cfg 并启动重发（超时看门狗已在 arm 时启动；
        DUT 重启路径由调用方先重启看门狗）。0x10 的 ACK 由 on_datagram 的
        通用应答先行发出（同窗 ACK+cfg，TBSM02 实证时序）。
        模式强制总闸（2026-09-29 用户拍板）：只开机模式任何路径都不下发
        cfg——重启重发分支另有前置门，这里是双保险。"""
        if self._run_mode(dut) != "full_run":
            ch = self._ch(dut)
            self.hub.log(1, ch, "WARN",
                         f"CH{ch:02d} 只开机模式：不下发 cfg（{detail}）", cat="conn")
            return
        ctx = self._st[dut]
        ctx.setdefault("cfgSentAt", time.time())
        if "_guard" not in ctx:
            ctx["_guard"] = RunGuard(ctx.get("_policy", RunPolicy()),
                                     stages_from_cfg_text(ctx["cfg"]), time.monotonic())
        else:
            ctx["_guard"].restart_cfg(time.monotonic())
        self._set(dut, ST_CFG_SENT, detail)
        if ctx.get("_policy", RunPolicy()).cfgAckTimeoutSec > 0:
            previous = self._timer.pop(dut, None)
            if previous is not None:
                previous.cancel()
            self._timer[dut] = asyncio.create_task(self._timeout_watch(dut, ctx))
        try:
            self._send_cfg(dut)
        except Exception as exc:
            self._set(dut, ST_FAIL, f"cfg_send_error: {exc}")
            return
        self._resend[dut] = asyncio.create_task(self._resend_loop(dut, self._st[dut]))

    def _ack(self, dut: int, cmd: int, status: int = 0) -> None:
        """固定 9 字节 ACK：AF 02 00 00 cmd 00 status 55^status EF
        （旧码 GenerateAckPackage；DUT 只认这个 2 字节数据形态）。"""
        tr = self._transports.get(dut)
        if tr is None:
            return
        xor = 0x55 ^ (status & 0xFF)
        frame = bytes([0xAF, 0x02, 0x00, 0x00, cmd & 0xFF,
                       0x00, status & 0xFF, xor, 0xEF])
        tr.sendto(frame, (self.mdbg.board_host, self.mdbg.dut_port(dut)))

    def _aging_min(self, dut: Optional[int] = None) -> int:
        """cfg 文本里的 AgingTime（分钟）；缺省 5。"""
        if dut is not None and "aging" in self._st[dut]:
            return self._st[dut]["aging"]
        m = re.search(r"^\s*AgingTime\s*=\s*(\d+)", self.mdbg.get_cfg_text(),
                      re.M | re.I)
        return int(m.group(1)) if m else 5

    def _schedule_power_key(self, dut: int, msg: PwrKeySet) -> None:
        """0x13 → 通讯板 MCU_PWR 组按键预约（旧码 DutsManager:918 同语义）。
        dut_key_lines 未配置（空）时只记录不执行——按键线号需现场实证。"""
        span_ms = msg.span100ms * 100
        lines = getattr(self.mdbg, "dut_key_lines", None) or []
        line = lines[dut - 1] if 1 <= dut <= len(lines) else None
        ch = self._ch(dut)
        if line is None:
            self.hub.log(1, ch, "WARN",
                         f"CH{ch:02d} 0x13 按键预约({msg.startSecond}s 后 "
                         f"{span_ms}ms)：dut_key_lines 未配置，仅记录未执行",
                         cat="conn")
            return
        board = self.mdbg.board_host
        mb = self.mdbg.mb_port

        def _press():
            from .commboard import CommBoard
            CommBoard(board, mb_port=mb).press_key(
                line, start_sec=msg.startSecond, span_ms=span_ms)

        ctx = self._st[dut]

        async def _go():
            try:
                async with self.power_lock:
                    if self._resolve(ctx) is None or ctx["state"] not in ACTIVE or not ctx.get("accept_frames"):
                        return
                    await self._io(_press)
                self.hub.log(1, ch, "INFO",
                             f"CH{ch:02d} 0x13 按键预约已下发通讯板："
                             f"{msg.startSecond}s 后按 {span_ms}ms（线 {line}）",
                             cat="conn")
            except Exception as e:                      # noqa: BLE001
                self.hub.log(1, ch, "ERROR",
                             f"CH{ch:02d} 0x13 按键预约下发失败：{e}",
                             cat="conn")
        asyncio.get_event_loop().create_task(_go())

    async def _run_timeout_watch(self, dut: int, ctx=None) -> None:
        """运行中看门狗：用户设置 test_timeout_sec>0 优先；0=自适应
        （老化分钟数×60 + 300s 启动裕量 + 900s 当前轮收尾预算）。超时判 FAIL(timeout)
        （旧码 EVT_SLAVE_TEST_TIMEOUT / ERR_CODE_TIMEOUT=0x06 语义）"""
        ctx = ctx or self._st[dut]
        user = int(getattr(self.mdbg, "test_timeout_sec", 0) or 0)
        limit = ctx.get("runLimit", user if user > 0 else self._aging_min(dut) * 60 + 1200)
        ch = self._ch(dut)
        deadline = ctx.setdefault("_hardDeadline", time.monotonic() + limit)
        try:
            while True:
                dut = self._resolve(ctx)
                if dut is None or ctx["state"] != ST_RUNNING:
                    return
                now = time.monotonic()
                guard = ctx.get("_guard")
                failure = "timeout" if now >= deadline else guard.expired(now) if guard else None
                if failure:
                    self._set(dut, ST_FAIL, failure)
                    self.hub.log(1, ch, "ERROR", f"CH{ch:02d} 运行保护超时：{failure}", cat="conn")
                    return
                remaining = guard.remaining(now) if guard else None
                wait = min(deadline - now, remaining) if remaining is not None else deadline - now
                changed = ctx.setdefault("_guardChanged", asyncio.Event())
                try:
                    await asyncio.wait_for(changed.wait(), wait)
                    changed.clear()
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass

    async def _progress_loop(self, dut: int, ctx=None) -> None:
        """进度节拍（2026-09-24 卡片进度条数据源）：时间基线
        elapsed/(AgingTime×60) 封顶 99%（100% 只属于 PASS 终态）；30s 内收到
        过 0x18 Progress 真值则优先用真值。等待/配置阶段只更新计时、进度为0。
        手动轮次同时推送本轮进度快照，生产轮次保持原状态流。"""
        ctx = ctx or self._st[dut]
        total = max(ctx.get("aging", self._aging_min(dut)) * 60, 1)
        ch = self._ch(dut)
        t0 = ctx["t0"]
        try:
            while True:
                await asyncio.sleep(2.0)
                dut = self._resolve(ctx)
                if dut is None or ctx["state"] not in ACTIVE:
                    return
                hint = self._prog.get(dut)
                if ctx['state'] != ST_RUNNING:
                    pct = 0
                elif hint and time.monotonic() - hint[1] < 30.0:
                    pct = hint[0]
                else:
                    pct = min(99, int((time.monotonic() - t0) * 100 / total))
                self.hub.update(1, ch, progress=min(pct, 99), durationSec=time.monotonic() - t0)
                if ctx.get("origin", "manual") == "manual":
                    # 手动页不再依赖首页快照中是否已存在该通道。
                    ctx["progress"] = min(pct, 99)
                    self._notify_change()
        except asyncio.CancelledError:
            pass

    def on_datagram(self, dut: int, data: bytes) -> None:
        try:
            self._handle_datagram(dut, data)
        except Exception as exc:
            if dut in self._st and self._st[dut]["state"] in ACTIVE:
                self._set(dut, ST_FAIL, f"protocol_io_error: {exc}")
            self.hub.syslog("ERROR", f"DUT 协议处理失败（序号 {dut}）：{exc}")

    def _handle_datagram(self, dut: int, data: bytes) -> None:
        if dut not in self._st:
            return
        ctx = self._st[dut]
        if (not self.board_online or not ctx.get("accept_frames", True)
                or (not self._powered(dut) and not ctx.get("power_pending"))):
            return
        msg = self.codec.decode(data)
        ch = self._ch(dut)
        if msg is None:
            self.hub.log(1, ch, "WARN",
                         f"CH{ch:02d} 透传口收到无法解析的报文({len(data)}B)，已丢弃",
                         cat="conn")
            return
        st = self._st[dut]["state"]
        writer = ctx.get('_writer')
        if writer is not None and not writer._closed:
            writer.write_log('INFO', str(msg))

        # 任一有效 0xAF 帧 = DUT 协议在线:power_only 模式没有后续状态机,
        # IDLE 态收到的 READY 也要点亮 /manual 卡片连接灯（2026-09-24）
        ctx["connected"] = True
        if st == ST_IDLE:
            self.hub.update(1, ch, connected=True, state="IDLE", testInfo="")
            self._notify_change()
        else:
            self.hub.update(1, ch, connected=True)

        # 2026-09-18 实证：旧上位机对 DUT 的每条上报都回 ACK（DutMaster.RecvDataHandle）。
        # DUT 每帧阻塞等 ACK——不回 0x11 的 ACK 它会 3s 一条无限重发，
        # 整个测试卡死在容量上报（当晚实测：CH01 容量行刷屏、流程不前进）。
        # 例外：0x12 用带老化值的数据应答（旧码 GenerateAginTimeAckPackage），
        # 不发裸 ACK。idle 态不回（disarm 后的杂散帧不惊动 DUT）。
        # 模式强制（2026-09-29 用户拍板）：只开机=除上电指令外什么都不发，
        # ACK 也不回（残留终态通道上的 DUT 同样不惊动）。
        if (not isinstance(msg, Ack) and st != ST_IDLE
                and len(data) >= 5 and data[0] == 0xAF and data[3] == 0x01
                and data[4] != CMD_AGING_REQ
                and self._run_mode(dut) == "full_run"):
            self._ack(dut, data[4])

        # 0x12 老化时长应答（2026-09-19 恢复；值取 cfg 的 AgingTime，缺省 5 分钟）。
        # 模式强制（2026-09-29 用户拍板）：只开机/idle 不续测试链——与
        # "idle 态不回 ACK 不惊动 DUT"同一原则。
        if isinstance(msg, AgingTimeRequest):
            if st not in ACTIVE or self._run_mode(dut) != "full_run":
                return
            tr = self._transports.get(dut)
            if tr is not None:
                tr.sendto(AgingTimeAnswer(self._aging_min(dut)).encode_frame(),
                          (self.mdbg.board_host, self.mdbg.dut_port(dut)))
                self.hub.log(1, ch, "INFO",
                             f"CH{ch:02d} 0x12 老化时长请求 → 应答 "
                             f"{self._aging_min(dut)} 分钟", cat="conn")
            return

        # 0x13 开机键预约（2026-09-19 恢复；旧码 DutsManager 转通讯板
        # SWITCH_GROUP_MCU_PWR 组 IO：startSec 秒后按键 span×100ms）
        # 模式强制（2026-09-29）：同 0x12，只开机/idle 不续链。
        if isinstance(msg, PwrKeySet):
            if st not in ACTIVE or self._run_mode(dut) != "full_run":
                return
            self._schedule_power_key(dut, msg)
            return

        if isinstance(msg, Ready):
            if st in ACTIVE and self._run_mode(dut) == "full_run":
                ctx["readyVersion"] = msg.version.replace("\x00", "").strip()
                failure = (timing_firmware_error(ctx.get("cfg", ""), msg.version)
                           or ctx.get("_policy", RunPolicy()).version_failure(msg.version))
                if failure:
                    self._set(dut, ST_FAIL, failure)
                    self.hub.log(1, ch, "ERROR", failure, cat="conn")
                    return
            if st == ST_WAIT_READY:
                self.hub.log(1, ch, "INFO",
                             f"CH{ch:02d} 收到 READY · 版本 {msg.version}，下发 cfg",
                             cat="conn")
                self._begin_cfg_phase(dut, f"版本 {msg.version}")
            elif st in TERMINAL:
                self.hub.log(1, ch, "WARN", f"CH{ch:02d} 终态已锁存，忽略 READY（只开机模式同样不续测）", cat="conn")
            elif st == ST_RUNNING:
                # 模式强制（2026-09-29 用户拍板）：只开机=只发上电指令——
                # DUT 重启的 READY 只记录，不重新下发 cfg、不动状态/看门狗
                if self._run_mode(dut) != "full_run":
                    self.hub.log(1, ch, "WARN",
                                 f"CH{ch:02d} 只开机模式：DUT 重启，不重新下发 cfg",
                                 cat="conn")
                    return
                if ctx.get('origin', 'manual') != 'manual':
                    self._set(dut, ST_FAIL, 'dut_reboot')
                    return
                # READY ACK 已在上方发送；恢复引导不能使失败的本轮自动续测。
                self.hub.log(1, ch, "ERROR",
                             f"CH{ch:02d} 测试中收到 READY：DUT 已重启，本轮 FAIL（dut_reboot），停止自动续测",
                             cat="conn")
                self._set(dut, ST_FAIL, 'dut_reboot')
            # ST_CFG_SENT 中重复 READY：忽略（重发循环进行中）
            return

        if isinstance(msg, Ack):
            if msg.cmd == CMD_START_TEST and st == ST_CFG_SENT:
                self._cancel(dut)
                if msg.status == 0:
                    if "_guard" in ctx:
                        ctx["_guard"].ack()
                    ctx.setdefault("_hardDeadline", time.monotonic() + ctx["runLimit"])
                    self._set(dut, ST_RUNNING)
                    self.hub.log(1, ch, "INFO",
                                 f"CH{ch:02d} DUT 已收到参数（0x15 ACK），开始执行"
                                 f"——日志走 UDP 63001", cat="conn")
                    # 运行看门狗（2026-09-19：旧码 EVT_SLAVE_TEST_TIMEOUT 语义）
                    self._runwatch[dut] = asyncio.create_task(
                        self._run_timeout_watch(dut, self._st[dut]))
                    # 进度节拍（2026-09-24）：时间基线 + Progress 真值覆盖
                    self._progtask[dut] = asyncio.create_task(
                        self._progress_loop(dut, self._st[dut]))
                else:
                    self._set(dut, ST_FAIL, f"cfg ACK status={msg.status}")
                    self.hub.log(1, ch, "ERROR",
                                 f"CH{ch:02d} DUT 拒绝 cfg（ACK status={msg.status}）",
                                 cat="conn")
            return

        if isinstance(msg, TestDone):
            if st in (ST_RUNNING, ST_CFG_SENT):
                if (msg.result == "PASS" and ctx.get("_policy", RunPolicy()).cfgAckTimeoutSec > 0
                        and not (ctx.get("_guard") and ctx["_guard"].acked)):
                    msg = TestDone("FAIL", "cfg_ack_missing")
                self._cancel(dut)
                w = self._runwatch.pop(dut, None)
                if w:
                    w.cancel()
                if msg.result == "PASS":
                    self._set(dut, ST_PASS)
                    self.hub.log(1, ch, "INFO", f"CH{ch:02d} 测试 PASS", cat="conn")
                else:
                    self._set(dut, ST_FAIL, msg.failItem)
                    self.hub.log(1, ch, "ERROR",
                                 f"CH{ch:02d} 测试 FAIL：{msg.failItem}", cat="conn")
            return

        if isinstance(msg, DramInfo):
            self.hub.log(1, ch, "INFO", f"CH{ch:02d} {msg}")
            return
        if isinstance(msg, Progress):
            pct = max(0, min(99, round(msg.progress)))
            self._prog[dut] = (pct, time.monotonic())
            if st == ST_RUNNING:      # 真值立即上屏（非运行态忽略）
                guard = ctx.get("_guard")
                if guard and guard.observe(msg.stage, time.monotonic()):
                    ctx["_guardChanged"].set()
                    self._record_context(ctx)
                self.hub.update(1, ch, progress=pct, step=str(msg.step))
                if ctx.get("origin", "manual") == "manual":
                    ctx.update(progress=pct, step=str(msg.step))
                    self._notify_change()
            self.hub.log(1, ch, "INFO",
                         f"CH{ch:02d} 进度 {msg.step} {msg.progress:.0f}%")
            return
        if isinstance(msg, DutLog):
            self.hub.log(1, ch, msg.level, f"CH{ch:02d} {msg.msg}")
