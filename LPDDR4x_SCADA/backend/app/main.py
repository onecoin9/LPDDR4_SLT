"""FastAPI 入口：REST + WebSocket + 静态托管。

启动（backend/ 目录下）：
  python mock_dut.py                       # 先起 24 路 mock DUT
  python -m uvicorn app.main:app --port 8000
"""

import os
import json
import asyncio
import mimetypes
import time
import tempfile
from contextlib import asynccontextmanager
from typing import Optional

# [2026-10-29] Windows 注册表 MIME 防御：Python mimetypes 初始化时会读
# HKCR\<ext>\Content Type；部分机器该值异常/缺失（现场实机案例），导致
# StaticFiles 把 .js 伺服为非 JS 类型，WebView2 拒绝执行 module 脚本，
# 界面整页空白（"黑屏"）。显式注册前端资源 MIME，摆脱注册表依赖。
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")

import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler

from . import commboard as commboard_mod
from . import ws as ws_mod
from .cfg import base_cfg, build_cfg, cfg_from_profile, cfg_text, log_uart_warning, parse_cfg
from .connection import ConnectionManager
from .controlplane import ControlPlane, ControlPlaneError
from .boardlog import BoardLogClient
from .handler import HandlerService
from .logchannel import LogChannel
from .localdata import backend_data_dir
from .profileplan import compile_profile, require_profile, ProfileError
from .productcfg import profile_from_cfg, read_editor_cfg
from .runtimepolicy import RunPolicy, PolicyConflict, PolicyUnavailable
from .settingsstore import SettingsStore, SettingsPolicyStore, read_document, revision
from .license_core import LicenseDenied, LicenseService
from .license_api import denial_content, license_router
from .manual import ManualDebug, ManualDebugError
from .manualrun import BoardHealthMonitor, ManualRunner
from .fieldtest import FieldTests
from .models import IoControlConfig, MachineConfig, StartBody, StopBody, SweepStartBody
from .protocol import HsgCodec
from .recorder import Recorder
from .sequencer import Sequencer, SequencerBusyError
from .sweep import SweepEngine, SweepError

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # backend/
# 数据目录锚点（config.yaml / records / products）：缺省 = backend/；
# 桌面版打包用 SLT_DATA_DIR 指到 exe 旁（desktop/desktop.py 设置），冻结后
# backend 目录在 PyInstaller bundle 内不可写、也不便用户改配置
DATA_DIR = backend_data_dir(BASE_DIR)
CFG_PATH = os.path.join(DATA_DIR, "config.yaml")

with open(CFG_PATH, encoding="utf-8") as _f:
    CFG = yaml.safe_load(_f)

settings_store = SettingsStore(DATA_DIR, CFG)
run_policy_store = SettingsPolicyStore(settings_store)
CFG["handler"] = {"enabled": True, **settings_store.document.handler.model_dump()}

BASE_CFG = base_cfg(CFG)               # cfg 基线（config.yaml cfg_defaults）

hub = ws_mod.Hub()
recorder = Recorder(os.path.join(DATA_DIR, settings_store.document.basic.logPath))
conns = ConnectionManager(CFG, hub, HsgCodec())
license_service = LicenseService(os.path.join(DATA_DIR, "license"))
seq = Sequencer(CFG, conns, hub, recorder)
seq.policy_provider = run_policy_store.snapshot
seq.authorize_start = license_service.require_valid
sweep = SweepEngine(seq, hub, recorder.root)
logch = LogChannel(hub, conns, port=int(CFG.get("dut_log_port", 63001)))
MACHINE_CFG_PATH = os.path.join(DATA_DIR, "machine_settings.json")


def load_machine_config(path: str) -> MachineConfig:
    """启动加载机台配置（2026-10-10「设置保存 json，下次开启加载」）：
    product/workOrder/lotNo/operator/ioControl。文件缺失/坏 json/校验失败
    → 回落空配置；profile 不落盘也不恢复（产品档案在 products/ 目录）。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = {k: v for k, v in data.items() if k != "profile"}
            return MachineConfig(**data)
    except (OSError, ValueError):
        pass
    return MachineConfig()


def save_machine_config(path: str, cfg: MachineConfig) -> None:
    """Only session identity is separate; IO and products live in settings.json."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg.model_dump(exclude={"profile", "ioControl", "settingsRevision"}), f,
                      ensure_ascii=False, indent=2)
    except OSError:
        pass


machine = load_machine_config(MACHINE_CFG_PATH)   # 机台配置（POST /api/config 更新）
machine.ioControl = settings_store.document.ioControl.model_copy(deep=True)
if machine.product not in settings_store.document.products:
    machine.product = next(iter(settings_store.document.products), "")
cplane = ControlPlane(CFG)         # P3 控制面：通讯板 + 温控板（config 两节默认关闭）
mdbg = ManualDebug(CFG, data_dir=DATA_DIR)   # 手动版调试：1 原版通讯板 × N DUT 电源开关 + 设置区


def _active_product_plan():
    profile = settings_store.document.products.get(machine.product)
    if profile is None:
        raise HTTPException(409, '请先在产品设置选择有效产品 / Select a valid product first')
    return {**require_profile(profile, BASE_CFG), 'product': machine.product,
            'settingsRevision': revision(settings_store.document)}


mdbg.product_plan_provider = _active_product_plan
mdbg.file_sink = logch.file_sink             # 落盘钩子（runner 经 mdbg 取；running 才开文件）
runner = ManualRunner(mdbg, hub, HsgCodec())  # 手动版「完整运行」：READY→cfg→ACK 编排
runner.authorize_start = license_service.require_valid
runner.production_policy_provider = run_policy_store.snapshot
runner.record_sink = recorder
field_tests = FieldTests(CFG, runner, seq)
runner.on_production_result = lambda *args: seq.on_result(*args) if seq.on_result else None


def _manual_state_payload() -> dict:
    """manual_state WS 推送载荷 = 手动调试完整快照（事件驱动，2026-10-10
    用户指令「状态每次变动都跳转到 API 修改页面显示」，撤前端定时轮询）。
    字段命名与 GET /api/manual/info、/api/manual/run_state 一致（camelCase）：
    duts = 电源/线号/通道；run.duts = 状态机明细（sinceSec 冻结值 +
    enteredAt 服务端墙钟，前端活跃态本地平滑 tick）；手动轮次附带
    progress/step，避免依赖尚无 DUT 行的通用快照。"""
    duts = [] if not mdbg.enabled else [
        {"dut": d["dut"], "line": d["line"], "channel": d["channel"],
         "powerOn": d["powerOn"]} for d in mdbg.info()["duts"]]
    run = runner.snapshot()
    return {"enabled": mdbg.enabled, "duts": duts,
            "run": {"mode": run["mode"],
                    "duts": [{"dut": s["dut"], "channel": s["channel"],
                              "state": s["state"], "detail": s["detail"],
                              "sinceSec": s["sinceSec"],
                              "enteredAt": s["enteredAt"],
                              **{k: s[k] for k in ("progress", "step") if k in s},
                              "runId": s.get("runId", 0),
                              "active": s["state"] in ("wait_ready", "cfg_sent", "running"),
                              "powerAction": s.get("powerAction", ""),
                              "connected": bool(s.get("connected")) and runner._powered(s["dut"]) and runner.board_online,
                              "powerError": s.get("powerError", "") }
                             for s in run["duts"]]}}


def _push_manual_state() -> None:
    hub.manual_state(_manual_state_payload())


# 状态机每次转换后推送（_set 汇聚点；自动下电完成后也会再推一次）。
# 注入回调而非让 runner import ws/fastapi——与 file_sink 同一先例，可单测。
runner.on_change = _push_manual_state


def _running_dut_hint():
    """板日志流 DUT 归属：唯一处于活动态（等待 READY/已发 cfg/运行中）的 DUT
    真实通道号，否则系统级(None)。2026-09-23 两次扩展：
    ①原版只认 running——单 DUT 调试时开机横幅等 PL 期文本到于 running 前，
      归因 None 落不进 DUT 页签；扩为三种活动态。
    ②归因宽限——板卡 10080 桥有 ~0.5s 聚合延迟，快 FAIL 的 DUT（如接触不良
      座秒败）尾部文本晚于状态离开；全空后 3s 内沿用刚离开的 DUT。多 DUT 同时
      活动仍 None（不用宽限，防跨 DUT 误归）。"""
    active = [d for d in runner.snapshot()["duts"]
              if d.get("state") in ("wait_ready", "cfg_sent", "running")]
    if len(active) == 1:
        _hint_sticky["ch"] = active[0]["channel"]
        _hint_sticky["t0"] = time.monotonic()
        return _hint_sticky["ch"]
    if (not active and _hint_sticky["ch"] is not None
            and time.monotonic() - _hint_sticky["t0"] < 3.0):
        return _hint_sticky["ch"]
    return None


_hint_sticky = {"ch": None, "t0": 0.0}


async def _hint_sticker():
    """[10080 归因播种] 每 0.5s 记录唯一活动 DUT——板卡文本到来时才调 hint
    的话，开机横幅（首条文本，常晚于快 FAIL）到达时 sticky 从未种过。"""
    while True:
        active = [d for d in runner.snapshot()["duts"]
                  if d.get("state") in ("wait_ready", "cfg_sent", "running")]
        if len(active) == 1:
            _hint_sticky["ch"] = active[0]["channel"]
            _hint_sticky["t0"] = time.monotonic()
        await asyncio.sleep(0.5)


# 通讯板 TCP 10080 日志流（2026-09-18 实证：板卡轨迹 + DUT 全量文本混合流）
blog = BoardLogClient(hub, mdbg.board_host if mdbg.enabled else "192.168.50.100",
                      port=int((CFG.get("manual_debug") or {}).get("log_tcp_port", 10080)),
                      dut_hint=_running_dut_hint,
                      sink_write=logch.file_sink.write)   # 10080 腿落盘（本 rig 文本全走此腿）

# cfg 基线提醒（2026-09-16）：config.yaml 关掉 LOG_TO_UART1 时启动即告知，
# 避免现场把"串口日志静默"误判成停机（日志门控机制见 cfg.log_uart_warning）。
for _w in log_uart_warning(BASE_CFG):
    hub.syslog("WARN", f"cfg 基线告警：{_w}")


def batch_id() -> str:
    """批次标识 = 工单号-LOT号（SSOT §3）；缺省 NO-BATCH（mock 联调用）"""
    b = "-".join(x for x in (machine.workOrder, machine.lotNo) if x)
    return b or "NO-BATCH"


def _site_flags(site: int) -> str:
    """lotstart selfcheck 的 DUT 使能位串：在线且非测试中 = 可测 '1'"""
    ok = set(field_tests.available(site) if field_tests.enabled else conns.online_idle_slots(site))
    return "".join("1" if s in ok else "0" for s in range(1, 25))


async def _start_handler_test(targets, batch):
    if seq.reserved:
        raise SequencerBusyError("扫描作业进行中，暂不接纳 Handler 测试")
    document = settings_store.snapshot()
    profile = document.products.get(machine.product)
    if profile is None:
        raise HTTPException(409, "请选择有效产品配置 / Select a valid product")
    preview = require_profile(profile, BASE_CFG)
    seq.set_cfg_text(preview["cfgText"], preview)
    if field_tests.enabled:
        return await field_tests.start(targets, batch, preview['cfgText'], preview,
                                       origin='handler', io_control=machine.ioControl)
    return await seq.start(targets, batch)


def _make_handler(config):
    service = None

    async def start_current(targets, batch):
        if handler is not service:
            raise HTTPException(409, "Handler 配置切换中，请重试 / Handler changing; retry")
        return await _start_handler_test(targets, batch)

    service = HandlerService(config, hub, start_test=start_current,
                             get_site_flags=_site_flags, get_batch=batch_id)
    return service


handler = _make_handler(CFG)
if handler.enabled:
    seq.on_result = handler.notify_result   # 每通道终态 → Handler testend 聚合


settings_lock = asyncio.Lock()


def _settings_busy():
    return (seq.reserved or bool(seq._preparing)
            or any(not task.done() for task in seq.tasks.values())
            or sweep.status.get("running", False)
            or handler.has_pending_work
            or any(d.get("state") in ("wait_ready", "cfg_sent", "running")
                   or d.get("powerAction") for d in runner.snapshot()["duts"]))


async def _apply_settings(document, selected_path=None):
    """Validate/bind first, persist second, then publish one consistent runtime."""
    global handler
    changed = (document.handler != settings_store.document.handler
               or document.ioControl != settings_store.document.ioControl
               or document.basic.logPath != settings_store.document.basic.logPath)
    if (changed or selected_path is not None) and _settings_busy():
        raise HTTPException(409, "测试进行中，不能切换配置文件或修改 Handler/IO / Test active")
    root = os.path.join(DATA_DIR, document.basic.logPath)
    if root != recorder.root:
        os.makedirs(root, exist_ok=True)
        with tempfile.TemporaryFile(dir=root):
            pass
    next_handler = None
    if handler.rx_port != document.handler.rx_port:
        next_handler = _make_handler({"handler": {"enabled": True, "rx_host": handler.rx_host,
                                                   **document.handler.model_dump()}})
        try:
            await next_handler.start()  # A failed bind leaves the old listener intact.
        except OSError as exc:
            raise HTTPException(409, "Handler 监听端口不可用 / Handler port unavailable") from exc
    try:
        if (changed or selected_path is not None) and _settings_busy():
            raise HTTPException(409, "测试已开始，请结束后重新保存 / Test active")
        state = (settings_store.select(selected_path, document) if selected_path is not None
                 else settings_store.save(document))
    except BaseException:
        if next_handler:
            await next_handler.close()
        raise
    old = handler
    CFG["handler"] = {"enabled": True, **document.handler.model_dump()}
    if next_handler:
        handler = next_handler
    else:
        handler.tx_host, handler.tx_port = document.handler.tx_host, document.handler.tx_port
    seq.on_result = handler.notify_result
    machine.ioControl = document.ioControl.model_copy(deep=True)
    recorder.root, sweep.records_root = root, root
    if machine.product not in document.products:
        machine.product = next(iter(document.products), "")
    if next_handler:
        await old.close()
    return {"ok": True, **state, "handlerStatus": handler.snapshot()}


async def _update_settings(updates, expected_revision=None):
    async with settings_lock:
        document = settings_store.candidate(updates, revision(settings_store.document) if expected_revision is None else expected_revision)
        return await _apply_settings(document)


async def _power_sequence(targets) -> float:
    """通讯板上电前置流程（旧 DutsManager ST_WORKING 链移植）：
    断电 → 1s → 上电 →（IO 控制非"无操作"时）分批错峰按键 → 返回上电窗口秒。
    IO 动作取当前机台配置 machine.ioControl（设置页下拉）。"""
    io = machine.ioControl or IoControlConfig()
    by_site: dict = {}
    for site, slot in targets:
        by_site.setdefault(site, []).append(slot)
    window = 0.0
    for site, slots in by_site.items():
        groups = {"A": [s - 1 for s in slots if 1 <= s <= 12],
                  "B": [s - 13 for s in slots if 13 <= s <= 24]}
        for label, lines in groups.items():
            if not lines:
                continue

            def op(site=site, label=label, lines=lines):
                cplane.power_off(site, label, lines)
                time.sleep(1.0)                    # 旧链 ResetAllGpio 后延迟 1s
                cplane.power_on(site, label, lines)
                if io.action != "none":
                    group = (commboard_mod.IO_GROUP_MCU_PWR
                             if io.action == "power_key"
                             else commboard_mod.IO_GROUP_MCU_KPCOL)
                    cplane.boot_key(site, label, io.batch, io.startDelaySec,
                                    io.intervalSec, io.pulseMs, group)
                    hub.log(None, None, "INFO",
                            f"SITE{site:02d}-{label} 已下发分批按键"
                            f"（{io.action}，每批 {io.batch} 路 / 间隔 {io.intervalSec}s"
                            f"/ 脉宽 {io.pulseMs}ms）")

            async with runner.power_lock:
                await runner._io(op)
        window = max(window, io.startDelaySec + io.batch * io.intervalSec + 2)
    return window


async def _cancel_power_sequence(targets) -> None:
    by_board = {}
    for site, slot in targets:
        label = "A" if slot <= 12 else "B"
        line = slot - 1 if slot <= 12 else slot - 13
        by_board.setdefault((site, label), []).append(line)
    for (site, label), lines in by_board.items():
        async with runner.power_lock:
            await runner._io(cplane.power_off, site, label, lines)


if cplane.cb_enabled:
    seq.power_cancel_hook = _cancel_power_sequence
    seq.power_hook = _power_sequence   # 通讯板模式：启动测试先走上电链（旧逻辑）


async def _board_scan_loop():
    """常驻板卡扫描（旧 HsgBroadcast 语义，2026-09-07）：每 5s 广播一轮。
    过程静默——只在新发现通讯板时记一条 log（用户要求）。在线表粘性，
    板掉线不产生事件/日志（旧逻辑；测试中的通讯板离线由 ping 检查兜底）。"""
    while True:
        try:
            fresh = await asyncio.to_thread(cplane.scan_once)
            for b in fresh:
                hub.syslog("INFO",
                           f"发现通讯板 {b['addr']}"
                           + (f"（ID {b['device_id']}）" if b.get("device_id") else ""))
        except ControlPlaneError:
            pass                        # commboard 关闭等配置态静默
        except Exception:
            pass                        # 单轮失败不中断扫描
        await asyncio.sleep(5.0)


async def _startup_time_sync() -> None:
    """启动时给通讯板对时（2026-09-18）。

    固件把「对时」和「复位测试」合成一个命令，所以这一步同时会把 IO 恢复默认
    （PWR_EN=RESET），即 DUT 复位为断电态——正好作为每次启动的干净起点；
    板卡轨迹日志的时间戳也因此不再是 1970。板子不在线时只告警，不阻断启动。
    """
    try:
        async with runner.power_lock:
            r = await runner._io(mdbg.sync_board_time)
            for d in runner._duts:
                runner.disarm(d)
        hub.syslog("INFO", "通讯板对时完成："
                           f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(r['timestamp']))}"
                           "（该命令附带 IO 复位，DUT 回到断电态）")
    except ManualDebugError as e:
        hub.syslog("WARN", f"通讯板对时失败：{e}")
    except Exception as e:                       # noqa: BLE001 - 启动流程不因对时失败中断
        hub.syslog("WARN", f"通讯板对时异常：{type(e).__name__}: {e}")


async def _board_health_loop() -> None:
    """[2026-09-28 强逻辑] 通讯板健康监控：板坏 → 所连全部测试板立即离线。

    4s 一查（Modbus 0xF001，超时约 2s）；边沿触发（首查建基线不广播，
    掉线只广播一次，恢复打 INFO 等待自然回连）。监控自身异常不杀任务。
    """
    mon = BoardHealthMonitor(mdbg, hub, runner)
    while True:
        await asyncio.sleep(4)
        try:
            await mon.check()
        except Exception:                        # noqa: BLE001 监控兜底
            pass


async def _server_ip_sync_loop() -> None:
    """[2026-09-28 多路日志] 周期性把板子 server_ip 同步为本机（默认 5 分钟）。

    板子把 DUT 日志（63001，[DUTx] 前缀 = 唯一能按路归因的腿）发往它记住的
    server_ip，而 server_ip 学自"最后收到的广播包源 IP"——网段里任何其他
    机器广播一次就会抢走转发目标（2026-09-28 实证：同步后 63001 恢复 35KB
    流量，数分钟后被再抢停）。周期广播保持本机为转发目标；同步成功静默，
    板子不在线或失败每 5 轮提示一次。
    """
    interval = int((CFG.get("manual_debug") or {}).get("server_ip_sync_sec", 300))
    if interval <= 0:
        return
    fails = 0
    while True:
        try:
            await asyncio.to_thread(mdbg.sync_server_ip, 3.0)
            fails = 0
        except Exception as e:                   # noqa: BLE001
            fails += 1
            if fails == 1 or fails % 5 == 0:
                hub.syslog("WARN", f"日志接收地址同步失败（连续 {fails} 次）：{e}")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    background_tasks = []
    scan_task = None
    if cplane.cb_enabled:
        scan_task = asyncio.create_task(_board_scan_loop())
        background_tasks.append(scan_task)
    await hub.start()
    if not field_tests.enabled:
        await conns.start()
    await logch.start()
    if mdbg.enabled:
        logch.file_sink.set_dir(mdbg.log_dir_abs())   # 手动调试「Log 保存路径」
        await runner.start()                          # 完整运行透传监听 2001-2004
        blog.start()                                  # 通讯板 TCP 10080 日志流
        background_tasks.append(asyncio.create_task(_startup_time_sync()))      # 启动对时（含 IO 复位）
        background_tasks.append(asyncio.create_task(_hint_sticker()))           # [10080 归因] 播种唯一活动 DUT
        # [2026-09-28 强逻辑] 通讯板健康监控：板坏 → 所连全部测试板立即离线
        background_tasks.append(asyncio.create_task(_board_health_loop()))
        # [2026-09-28 多路日志] 周期同步 server_ip，保住 63001 [DUTx] 按路转发
        background_tasks.append(asyncio.create_task(_server_ip_sync_loop()))
    await handler.start()
    hub.syslog("INFO", "测试服务已就绪，等待设备连接")
    yield
    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)
    await blog.close()
    if field_tests.enabled:
        await field_tests.stop()
    await runner.close()
    await sweep.stop()
    await seq.close()
    await handler.close()
    await conns.close()
    await logch.close()
    await hub.close()


app = FastAPI(title="LPDDR4x SLT 上位机后端", version="0.1.0", lifespan=lifespan)
app.include_router(license_router(license_service))


@app.exception_handler(ProfileError)
async def invalid_profile_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": exc.preview})


@app.exception_handler(PolicyUnavailable)
async def invalid_policy_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(request, exc):
    if request.url.path not in ("/api/runtime-policy", "/api/settings", "/api/settings/select"):
        return await request_validation_exception_handler(request, exc)
    # 不回显NaN/Inf或异常对象，避免校验错误本身在JSON序列化时变成500。
    return JSONResponse(status_code=422, content={"detail": [
        {key: row[key] for key in ("loc", "msg", "type")} for row in exc.errors()]})


@app.exception_handler(PolicyConflict)
async def policy_conflict_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/api/runtime-policy")
async def get_runtime_policy():
    return run_policy_store.status()


@app.post("/api/runtime-policy")
async def save_runtime_policy(policy: RunPolicy, if_match: Optional[str] = Header(None)):
    async with settings_lock:
        if if_match is not None and if_match != settings_store.document.runtimePolicy.revision:
            raise PolicyConflict("运行保护已被修改，请重新读取 / Policy changed; reload")
        candidate = settings_store.candidate({"runtimePolicy": policy.model_dump()}, revision(settings_store.document))
        await _apply_settings(candidate)
        state = run_policy_store.status()
    hub.syslog("INFO", f"运行保护已保存，后续新轮生效 · {state['revision'][:12]}")
    return {"ok": True, **state}


@app.exception_handler(SequencerBusyError)
async def busy_job_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": {
        "messageZh": str(exc), "messageEn": "The test engine is reserved by another job"}})


@app.exception_handler(LicenseDenied)
async def license_denied_handler(request, exc):
    return JSONResponse(status_code=403, content=denial_content(exc))

# 开发期前端 dev server（:3000）跨域访问；生产由本服务托管前端静态产物，同源免 CORS
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


# ---------------------------------------------------------------- REST

@app.exception_handler(OSError)
async def settings_io_error(request, exc):
    # Do not report successful saves or expose raw filesystem errors.
    return JSONResponse(status_code=500, content={"detail": "文件操作失败，未完成保存 / File operation failed"})


@app.get("/api/settings")
async def get_settings():
    return {**settings_store.status(), "handlerStatus": handler.snapshot()}


@app.post("/api/settings")
async def patch_settings(updates: dict = Body(...), if_match: Optional[str] = Header(None)):
    if if_match is None:
        raise HTTPException(428, "需要设置版本 / Settings revision required")
    try:
        return await _update_settings(updates, if_match)
    except ValueError as exc:
        if isinstance(exc, (PolicyConflict, PolicyUnavailable)):
            raise
        raise HTTPException(422, "设置格式或数值无效 / Invalid settings") from exc


@app.post("/api/settings/select")
async def select_settings(body: dict = Body(...)):
    if set(body) != {"path"} or not isinstance(body["path"], str) or not body["path"].strip():
        raise HTTPException(400, "请选择 JSON 设置文件 / Select a JSON settings file")
    path = os.path.abspath(os.path.join(DATA_DIR, body["path"]))
    async with settings_lock:
        try:
            document = read_document(path)
        except (OSError, ValueError) as exc:
            raise HTTPException(422, "设置文件不可用或格式错误 / Invalid settings file") from exc
        return await _apply_settings(document, path)


@app.get("/api/settings/browse")
async def browse_settings(path: Optional[str] = None):
    result = await asyncio.to_thread(mdbg.browse_dir, str(settings_store.path.parent) if path is None else path, "json")
    if result["path"]:
        # Keep directories inside the application data root portable after relocation.
        relative = os.path.relpath(result["path"], DATA_DIR) if os.path.splitdrive(result["path"])[0].lower() == os.path.splitdrive(DATA_DIR)[0].lower() else None
        result["selectionPath"] = (relative if relative is not None and relative != ".." and not relative.startswith(".." + os.sep)
                                   else result["path"])
    return result

@app.get("/api/duts")
async def get_duts():
    """全部工位状态快照（前端初始化用）"""
    return hub.snapshot()


@app.post('/api/timing/preview')
async def timing_preview(profile: dict = Body(...)):
    from .timing_ns import table
    try:
        result=table(profile,int(BASE_CFG.get('Freq',4266)))
        plan=compile_profile(profile,BASE_CFG)
        from .timing_reports import fingerprint
        result['tag']=fingerprint(plan['cfgText']) if plan['valid'] else None
        return result
    except (ValueError,TypeError,KeyError,AttributeError):
        raise HTTPException(422, 'Invalid timing configuration or clock') from None


@app.get('/api/timing/readback')
async def timing_readback(tag: str = ''):
    if len(tag)!=8 or any(ch not in '0123456789abcdefABCDEF' for ch in tag):
        return {'rows':[]}
    return {'rows':hub.timing_reports.snapshot(tag.lower())}


@app.post("/api/config")
async def post_config(cfg: MachineConfig):
    """设置机台表单；批次标识 = 工单号-LOT号。
    带产品档案时编译为 .cfg，同时保存到选中的统一设置 JSON。"""
    global machine
    if seq.reserved:
        raise SequencerBusyError("扫描作业进行中，不能更换生产配置")
    if cfg.settingsRevision is not None and cfg.settingsRevision != revision(settings_store.document):
        raise PolicyConflict("设置已被修改，请重新读取后启动 / Settings changed; reload before starting")
    preview = require_profile(cfg.profile, BASE_CFG) if cfg.profile is not None else None
    updates = {}
    if preview:
        updates["products"] = {**settings_store.document.products, cfg.profile["name"]: cfg.profile}
    if cfg.ioControl is not None and cfg.ioControl != settings_store.document.ioControl:
        updates["ioControl"] = cfg.ioControl.model_dump()
    if updates:
        await _update_settings(updates)
    if preview:
        path = str(settings_store.path)
        seq.set_cfg_text(preview["cfgText"], preview)
    cfg.ioControl = settings_store.document.ioControl.model_copy(deep=True)
    machine = cfg
    save_machine_config(MACHINE_CFG_PATH, cfg)   # 持久化：下次启动自动恢复
    parts = [f"机台配置已更新：产品名: {cfg.product}，"
             f"batch={batch_id()}，操作员: {cfg.operator}"]
    if cfg.ioControl is not None and cfg.ioControl.action != "none":
        io = cfg.ioControl
        names = {"power_key": "测试板开机（MCU_PWR 分批按键）",
                 "download": "测试板进入下载模式（MCU_KPCOL）"}
        parts.append(f"IO 控制：{names.get(io.action, io.action)}，"
                     f"每批 {io.batch} 路 / 延迟 {io.startDelaySec}s / "
                     f"间隔 {io.intervalSec}s / 脉宽 {io.pulseMs}ms")
        if not cplane.cb_enabled:
            hub.syslog("WARN", "通讯板控制未启用，本次不执行电源和按键控制")
    if cfg.profile is not None:
        stages_note = f"阶段 {seq.stages}"
        parts.append(f"产品档案已编译（留档 {path or '失败'}），{stages_note}")
        for w in preview["warnings"]:
            hub.syslog("WARN", f"产品档案编译告警：{w.get('field','')} {w['messageZh']}")
    hub.syslog("INFO", "；".join(parts))
    return {"ok": True, "batch": batch_id(), "plan": preview,
            "settingsRevision": revision(settings_store.document)}


@app.post("/api/test/start")
async def test_start(body: StartBody):
    if field_tests.enabled:
        if body.site is not None and body.site != 1:
            raise HTTPException(400, '现场通讯板只配置在 SITE 01 / Field board is configured for SITE 01')
        targets = ([(1, slot) for slot in body.slots] if body.slots
                   else list(field_tests.mapping()))
        profile = settings_store.document.products.get(machine.product)
        if profile is None:
            raise HTTPException(409, '请选择有效产品配置 / Select a valid product')
        preview = require_profile(profile, BASE_CFG)
        started = await field_tests.start(targets, batch_id(), preview['cfgText'], preview,
                                          io_control=machine.ioControl)
        hub.syslog('INFO', f'开始现场测试：{started}，产品 {machine.product}，批次 {batch_id()}')
        return {'started': started}
    if body.site is not None:
        if body.site not in hub.site_ids:
            raise HTTPException(400, f"无效的 site: {body.site}")
        # 工程师单站测试：该 site 的（指定或全部）在线空闲通道
        slots = body.slots or conns.online_idle_slots(body.site)
        targets = [(body.site, s) for s in slots]
        scope = f"SITE {body.site:02d}"
    elif body.slots:
        targets = [(1, s) for s in body.slots]
        scope = "SITE 01"
    else:
        targets = [(sid, slot) for sid in hub.site_ids
                   for slot in conns.online_idle_slots(sid)]
        scope = "ALL"
    if not targets:
        raise HTTPException(400, "没有可启动的通道（需在线且空闲）")
    started = await seq.start(targets, batch_id())
    hub.syslog("INFO", f"开始测试：{scope}（{len(started)} 个通道），批次 {batch_id()}")
    return {"started": started}


@app.post("/api/test/stop")
async def test_stop(body: StopBody):
    if field_tests.enabled and not sweep.status.get('running'):
        if body.site is not None and body.site != 1:
            raise HTTPException(400, '现场通讯板只配置在 SITE 01 / Field board is configured for SITE 01')
        targets = [(1, slot) for slot in body.slots] if body.slots else None
        stopped = await field_tests.stop(targets)
        hub.syslog('WARN', f'已停止现场测试：{stopped}')
        return {'stopped': stopped}
    if sweep.status.get("running"):
        targets = list(seq.tasks)
        await sweep.stop()
        return {"stopped": targets, "sweepStopped": True}
    if body.site is not None:
        if body.site not in hub.site_ids:
            raise HTTPException(400, f"无效的 site: {body.site}")
        slots = body.slots or [slot for (site, slot) in seq.tasks if site == body.site]
        targets = [(body.site, s) for s in slots]
    elif body.slots:
        targets = [(1, s) for s in body.slots]
    else:
        targets = list(seq.tasks)
    stopped = await seq.stop(targets)
    hub.syslog("WARN", "断开机台测试流程！" if stopped else "没有测试中的通道")
    return {"stopped": stopped}


@app.post("/api/sweep/start")
async def sweep_start(body: SweepStartBody):
    """时序/参数扫描（Phase 2）：主轴 = params 中填了起始/步进/结束的勾选行。

    逐点「编译 cfg → 下发 → 快测 → 收结果」，产物见 records/sweeps/；
    quick=True（默认）时每点只跑 PL+LK 快测，完整配置扫描传 quick=False。"""
    if any(d.get("active") or d.get("state") in ("wait_ready", "cfg_sent", "running")
           for d in runner.snapshot()["duts"]):
        raise SequencerBusyError("手动测试正在运行，请先结束后扫描")
    if body.site is not None:
        if body.site not in hub.site_ids:
            raise HTTPException(400, f"无效的 site: {body.site}")
        slots = body.slots or conns.online_idle_slots(body.site)
        targets = [(body.site, s) for s in slots]
        scope = f"SITE {body.site:02d}"
    else:
        targets = [(sid, slot) for sid in hub.site_ids
                   for slot in conns.online_idle_slots(sid)]
        scope = "ALL"
    if not targets:
        raise HTTPException(400, "没有可启动的通道（需在线且空闲）")
    if list(seq.tasks):
        raise HTTPException(400, "有通道正在测试，先停止再扫描")
    try:
        st = await sweep.start(body.profile, targets, BASE_CFG,
                               quick=body.quick, stop_on_fail=body.stop_on_fail,
                               batch_prefix=batch_id())
    except SweepError as exc:
        raise HTTPException(400, str(exc)) from exc
    hub.syslog("INFO", f"开始扫描：{scope}（{len(targets)} 通道），"
                       f"轴 {st['axis']}，{len(st['points'])} 点，"
                       f"{'快测' if body.quick else '完整配置'}")
    return st


@app.get("/api/sweep/status")
async def sweep_status():
    return sweep.snapshot()


@app.post("/api/sweep/stop")
async def sweep_stop():
    stopped = await sweep.stop()
    hub.syslog("WARN", "手动停止扫描" if stopped else "没有进行中的扫描")
    return {"stopped": stopped}


@app.get("/api/records")
async def get_records(date: str = None, batch: str = None):
    """查询 CSV 记录：date/batch 逐级缺省时先返回可用日期/批次列表"""
    return recorder.query(date, batch)


@app.get("/api/products")
async def get_products():
    """Product library from the active settings document."""
    return settings_store.snapshot().products


@app.post("/api/products/preview")
async def preview_product(profile: dict = Body(...)):
    return compile_profile(profile, BASE_CFG)


@app.get('/api/products/context')
async def product_context():
    return {'product': machine.product, 'baseCfg': BASE_CFG}


@app.post('/api/products/select')
async def select_product(body: dict = Body(...)):
    """Select a shared product without starting a test or sending hardware IO."""
    global machine
    product = body.get('product')
    async with settings_lock:
        expected = body.get('settingsRevision')
        if expected is not None and expected != revision(settings_store.document):
            raise PolicyConflict('设置已被修改，请重新读取后选择 / Settings changed; reload before selecting')
        if not isinstance(product, str) or product not in settings_store.document.products:
            raise HTTPException(409, '请选择现有产品 / Select an existing product')
        machine = machine.model_copy(update={'product': product, 'profile': None})
        save_machine_config(MACHINE_CFG_PATH, machine)
    return {'product': product, 'settingsRevision': revision(settings_store.document)}


@app.post('/api/products/import-cfg')
async def import_product_cfg(body: dict = Body(...)):
    async with settings_lock:
        product = body.get('product', machine.product)
        if not isinstance(product, str) or product != machine.product or product not in settings_store.document.products:
            raise HTTPException(409, '当前产品已改变，请重新读取 / Active product changed; reload')
        expected = body.get('settingsRevision')
        if not isinstance(expected, str) or expected != revision(settings_store.document):
            raise PolicyConflict('设置已被修改，请重新读取后导入 / Settings changed; reload before import')
        profile, preview = profile_from_cfg(body.get('cfgText'), settings_store.document.products[product], BASE_CFG)
        document = settings_store.candidate({'products': {**settings_store.document.products, product: profile}}, expected)
        await _apply_settings(document)
    hub.syslog('INFO', f'CFG 已同步到产品设置：{product}')
    return {'product': product, 'profile': profile, 'preview': preview,
            'settingsRevision': revision(settings_store.document)}


@app.post('/api/manual/cfg_file')
async def save_manual_cfg_file(body: dict = Body(...)):
    # text（可选）= 用户编辑的原文：按导入同一严格解析校验后逐字写盘（2026-11-18 契约：
    # 文件保留客户字面内容，产品编译结果仍是唯一下发来源）。缺省回退编译产物（旧客户端）。
    text = body.get('text')
    if text is not None and (not isinstance(text, str) or not text.strip()):
        raise HTTPException(400, 'CFG 文本无效 / Invalid CFG text')
    if isinstance(text, str):
        read_editor_cfg(text)
    async with settings_lock:
        if body.get('product') != machine.product or body.get('settingsRevision') != revision(settings_store.document):
            raise PolicyConflict('产品配置已改变，请重新读取 / Product changed; reload before saving')
        plan = _active_product_plan()
        written = text if isinstance(text, str) else plan['cfgText']
        try:
            path = await runner._io(mdbg.save_cfg_file, body.get('path'), written)
        except ManualDebugError as error:
            _md_raise(error)
    return {'path': path, 'cfgContent': written, 'settingsRevision': plan['settingsRevision']}


@app.post("/api/products")
async def post_product(profile: dict = Body(...)):
    """Validate and save a product in the active settings document."""
    if not isinstance(profile, dict) or not profile.get("name"):
        raise HTTPException(400, "profile 必须是含 name 字段的 JSON 对象")
    preview = require_profile(profile, BASE_CFG)
    await _update_settings({"products": {**settings_store.document.products, profile["name"]: profile}})
    hub.syslog("INFO", f"产品配置已保存：{profile.get('name')}")
    return {"ok": True, "name": profile["name"], "plan": preview}


# -------------------------------------------------- P3 控制面（通讯板/温控板）
# controlplane.py 全是阻塞 socket 调用 → 一律 asyncio.to_thread 进线程池；
# ControlPlaneError(status,msg) → HTTPException。config.yaml 两节默认 enabled: false。

def _cp_raise(e: ControlPlaneError):
    raise HTTPException(e.status, str(e))


@app.get("/api/boards")
async def api_boards():
    """通讯板清单（enabled=false 时 boards 为空）。scanned = 常驻扫描累计
    发现的板（粘性在线表，first/last_seen；旧 HsgBroadcast 语义）。"""
    return {"enabled": cplane.cb_enabled,
            "boards": cplane.boards() if cplane.cb_enabled else [],
            "scanned": cplane.scanned_boards() if cplane.cb_enabled else []}


@app.post("/api/boards/discover")
async def api_boards_discover(timeout: float = 3.0):
    """UDP 60000 广播发现在线通讯板。"""
    try:
        return await asyncio.to_thread(cplane.discover, timeout)
    except ControlPlaneError as e:
        _cp_raise(e)


@app.post("/api/boards/{site}/{board}/power_on")
async def api_board_power_on(site: int, board: str, stagger_sec: int = 0):
    """整板（或指定 lines）分批错峰上电（0xF000 cmd7 IO 安全分批）。"""
    license_service.require_valid()
    if seq.reserved:
        raise SequencerBusyError("扫描作业进行中，请先停止扫描")
    try:
        r = await asyncio.to_thread(cplane.power_on, site, board, None, stagger_sec)
    except ControlPlaneError as e:
        _cp_raise(e)
    hub.syslog("INFO", f"通讯板 SITE{site:02d}-{board.upper()} 错峰上电 "
                       f"（{len(r['lines'])} 路，间隔 {stagger_sec}s）")
    return r


@app.post("/api/boards/{site}/{board}/power_off")
async def api_board_power_off(site: int, board: str):
    try:
        r = await asyncio.to_thread(cplane.power_off, site, board)
    except ControlPlaneError as e:
        _cp_raise(e)
    hub.syslog("INFO", f"通讯板 SITE{site:02d}-{board.upper()} 下电（{len(r['lines'])} 路）")
    return r


@app.post("/api/boards/{site}/{board}/reboot")
async def api_board_reboot(site: int, board: str):
    """通讯板重启——真机首联第一个验证命令（验 Modbus 参数字节序）。"""
    license_service.require_valid()
    if seq.reserved:
        raise SequencerBusyError("扫描作业进行中，请先停止扫描")
    try:
        r = await asyncio.to_thread(cplane.reboot, site, board)
    except ControlPlaneError as e:
        _cp_raise(e)
    hub.syslog("WARN", f"通讯板 SITE{site:02d}-{board.upper()} 已下发重启")
    return r


@app.get("/api/boards/{site}/{board}/state")
async def api_board_state(site: int, board: str):
    """轮询 0xF001 动作状态：NONE/RUN/FAIL/SUCCESS/ERROR。"""
    try:
        return await asyncio.to_thread(cplane.action_state, site, board)
    except ControlPlaneError as e:
        _cp_raise(e)


@app.get("/api/temp")
async def api_temp():
    """温控板 24 路温度 + 风扇转速；配了 target_celsius 时附带 ready 判定。"""
    try:
        return await asyncio.to_thread(cplane.temp_status)
    except ControlPlaneError as e:
        _cp_raise(e)


@app.post("/api/temp/set")
async def api_temp_set(celsius: float = Body(..., embed=True)):
    """设定目标温度（℃）。"""
    try:
        r = await asyncio.to_thread(cplane.set_temp, celsius)
    except ControlPlaneError as e:
        _cp_raise(e)
    hub.syslog("INFO", f"温控目标温度设定：{celsius}℃")
    return r


@app.post("/api/temp/onoff")
async def api_temp_onoff(on: bool = Body(..., embed=True)):
    """温控开关。"""
    try:
        r = await asyncio.to_thread(cplane.set_temp_on, on)
    except ControlPlaneError as e:
        _cp_raise(e)
    hub.syslog("INFO", f"温控{'开启' if on else '关闭'}")
    return r


# -------------------------------------------------- 手动版调试（/manual 页）
# 1 块原版通讯板 + N 块测试主板；电源 = Modbus cmd7 PWR_EN 单路开关。
# ManualDebugError(status,msg) → HTTPException；阻塞 socket 走 to_thread。

def _md_raise(e: ManualDebugError):
    raise HTTPException(e.status, str(e))


@app.get("/api/handler/settings")
async def get_handler_settings():
    """Handler 分选机对接：当前配置与运行状态（设置页「Handler 设置」分区）"""
    if hasattr(handler, "snapshot"):
        return handler.snapshot()
    return {"enabled": handler.enabled, "available": False,
            "rx_host": handler.rx_host, "rx_port": handler.rx_port,
            "tx_host": handler.tx_host, "tx_port": handler.tx_port}


@app.post("/api/handler/settings")
async def post_handler_settings(body: dict = Body(...)):
    """Handler is always enabled; persist in the active settings JSON."""
    updates = dict(body)
    if "enabled" in updates:
        if updates.pop("enabled") is not True:
            raise HTTPException(400, "Handler 始终启用 / Handler is always enabled")
    if not updates or set(updates) - {"rx_port", "tx_host", "tx_port"}:
        raise HTTPException(400, "无效的 Handler 设置 / Invalid Handler settings")
    try:
        await _update_settings({"handler": updates})
    except ValueError as exc:
        if isinstance(exc, (PolicyConflict, PolicyUnavailable)):
            raise
        raise HTTPException(400, "Handler 参数无效 / Invalid Handler values") from exc
    return {"ok": True, **handler.snapshot()}


@app.get("/api/manual/info")
async def api_manual_info():
    """手动调试信息：是否启用、通讯板地址、每路 DUT 的线号与电源状态。"""
    return mdbg.info()


@app.get("/api/manual/board_state")
async def api_manual_board_state():
    """通讯板链路心跳：读 0xF001 动作状态（NONE/RUN/FAIL/SUCCESS/ERROR）。"""
    try:
        return await asyncio.to_thread(mdbg.board_state)
    except ManualDebugError as e:
        _md_raise(e)


@app.post("/api/manual/sync_server_ip")
async def api_manual_sync_server_ip():
    """[多路日志] 手动同步板子 server_ip 为本机（定向广播）。

    板子把 63001 的 [DUTx] 日志转发到它记住的 server_ip；网段里其他机器
    广播会抢走转发目标。后端已有周期自动同步（_server_ip_sync_loop），
    此端点供现场排障立即触发。
    """
    try:
        return await asyncio.to_thread(mdbg.sync_server_ip, 3.0)
    except ManualDebugError as e:
        _md_raise(e)


@app.post("/api/manual/power")
async def api_manual_power(body: dict = Body(...)):
    """单路电源开关：body = {"dut": 1..N, "on": true|false}。
    full_run 模式下：上电后自动进入「等 READY → 下发 cfg」编排，下电解除。"""
    if not isinstance(body.get("on"), bool) or isinstance(body.get("dut"), bool):
        raise HTTPException(400, "on 须为 JSON 布尔值，dut 须为 DUT 序号")
    if body.get("on") and seq.reserved:
        raise SequencerBusyError("扫描作业进行中，请先停止扫描")
    try:
        r = await runner.power(int(body.get("dut", 0)), bool(body.get("on")))
    except (ManualDebugError, TypeError, ValueError) as e:
        if isinstance(e, ManualDebugError):
            _md_raise(e)
        raise HTTPException(400, f"body 须含 dut(int)/on(bool)：{e}")
    ch = mdbg.ch(r["dut"])
    hub.syslog("INFO", f"DUT{ch:02d} {'已上电' if r['powerOn'] else '已下电'}")
    _push_manual_state()     # 电源已变：事件驱动推送（不等前端轮询）
    return r


@app.post("/api/manual/duts/add")
async def api_manual_duts_add():
    """新增一路 DUT（界面「+」卡片；路数由 config 决定、最多 8 路）：
    线号/通道取最小未占用值，持久化回 config.yaml；返回最新 info（同
    GET /api/manual/info）。runner.sync_duts() 现场补状态机 + 绑新 DUT 的
    透传端口——添加后无需重启后端。"""
    try:
        async with runner.power_lock:
            info = mdbg.add_dut(CFG_PATH)
    except ManualDebugError as e:
        _md_raise(e)
    await runner.sync_duts()
    # info.duts 按通道号排序返回，新 DUT 不一定在末尾——dut 序号才是身份，
    # 新增者恒为最大序号（追加在 dut_lines 末尾）
    new = max(info["duts"], key=lambda d: d["dut"])
    hub.syslog("INFO", f"已添加 DUT{mdbg.ch(new['dut']):02d}，共 {len(info['duts'])} 个通道")
    _push_manual_state()     # DUT 列表已变：推送新快照（其他在线客户端同步）
    return info


@app.post("/api/manual/duts/remove")
async def api_manual_duts_remove(body: dict = Body(...)):
    """移除一路 DUT（卡片「−」）：body = {"dut": n}（dut_lines 列表序号，
    身份标识）。安全约束在 mdbg.remove_dut：电源开着/完整运行活动态 → 400。
    其余 DUT 的 线号↔通道↔端口 配对不变；返回最新 info。"""
    try:
        dut = int(body.get("dut", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, f"body 须含 dut(int)：{body!r}")

    def is_active(d: int) -> bool:
        st = runner._st.get(d)
        return st is not None and st["state"] not in (
            "idle", "offline", "pass", "fail", "timeout")

    try:
        async with runner.power_lock:
            info = mdbg.remove_dut(dut, CFG_PATH, is_active)
            runner.drop_dut(dut)
    except ManualDebugError as e:
        _md_raise(e)
    hub.syslog("INFO", f"手动调试：移除 DUT 序号 {dut}（剩 {len(info['duts'])} 路）")
    _push_manual_state()     # DUT 列表已变：推送新快照
    return info


@app.post("/api/manual/power_all")
async def api_manual_power_all(body: dict = Body(...)):
    """整组电源开关（0xA2 位掩码，原子一包）：body = {"on": true|false}。"""
    if not isinstance(body.get("on"), bool):
        raise HTTPException(400, "on 须为 JSON 布尔值")
    if body.get("on") and seq.reserved:
        raise SequencerBusyError("扫描作业进行中，请先停止扫描")
    try:
        r = await runner.power(0, bool(body.get("on")), all_duts=True)
    except ManualDebugError as e:
        _md_raise(e)

    hub.syslog("INFO", f"全部 DUT {'已上电' if r['powerOn'] else '已下电'}")
    _push_manual_state()     # 整组电源已变：事件驱动推送
    return r


@app.post("/api/manual/sync_time")
async def api_manual_sync_time(body: dict = Body({})):
    """给通讯板对时：body 可带 {"timestamp": <unix秒>}，缺省取本机当前时间。

    固件的对时命令附带 IO 复位（PWR_EN 回默认断电态），所以调用后 DUT 一律断电。
    启动流程已自动调用一次；这里是现场手动补对时的入口。
    """
    ts = body.get("timestamp")
    try:
        async with runner.power_lock:
            r = await runner._io(mdbg.sync_board_time, int(ts) if ts is not None else None)
            for d in range(1, len(mdbg.dut_lines) + 1):
                runner.disarm(d)
    except (ManualDebugError, TypeError, ValueError) as e:
        if isinstance(e, ManualDebugError):
            _md_raise(e)
        raise HTTPException(400, f"timestamp 须为整数秒：{e}")
    for d in range(1, len(mdbg.dut_lines) + 1):
        runner.disarm(d)
    hub.syslog("INFO", "手动调试：通讯板对时 "
                       f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(r['timestamp']))}"
                       "（附带 IO 复位，DUT 回到断电态）")
    _push_manual_state()     # 对时附带 IO 复位 → 全部断电，推送电源新态
    return r


@app.get("/api/manual/settings")
async def api_manual_settings():
    """手动调试「设置」区当前值（IP / 日志路径 / cfg 内容 / 运行模式）。"""
    return mdbg.settings()


@app.get("/api/manual/settings_file")
async def api_manual_read_settings_file():
    """读取 session_settings.json 内容（「读取设置」按钮的文件预览数据源）。"""
    sf = os.path.join(mdbg.data_dir, "session_settings.json")
    if not os.path.isfile(sf):
        return {"path": sf, "content": "", "exists": False}
    with open(sf, encoding="utf-8") as f:
        return {"path": sf, "content": f.read(), "exists": True}


@app.get("/api/manual/read_file")
async def api_manual_read_file(path: str = ""):
    """Read a selected settings/CFG file without changing the active product."""
    if not path or not path.lower().endswith((".json", '.cfg')):
        raise HTTPException(400, "请选择 JSON 或 CFG 文件 / Select a JSON or CFG file")
    import os as _os
    if not _os.path.isfile(path):
        return {"path": path, "content": "", "exists": False}
    if path.lower().endswith('.cfg') and _os.path.getsize(path) > 65536:
        raise HTTPException(400, 'CFG 文件不能超过 64 KiB / CFG file is too large')
    with open(path, encoding="utf-8") as f:
        return {"path": path, "content": f.read(), "exists": True}


@app.get("/api/manual/browse")
async def api_manual_browse(path: str = "", files: str = ""):
    """目录浏览（设置区路径选择器后端）：空 path → 驱动器；有效 → 子目录。
    files=cfg → 同时列出 .cfg 文件。"""
    try:
        return await asyncio.to_thread(mdbg.browse_dir, path, files)
    except ManualDebugError as e:
        _md_raise(e)


@app.post("/api/manual/settings")
async def api_manual_settings_save(body: dict = Body(...)):
    """保存独立手动运行设置；CFG 通过产品导入接口管理。
    唯一副作用：切到只开机时解除全部已布防会话（防 wait_ready 期间切模式
    导致 READY 到来后仍下发 cfg）。不做 server_ip 广播/对时。"""
    async with runner.power_lock:
        if ('runMode' in body and body['runMode'] != mdbg.run_mode
                and any(c.get('origin') in ('monitor', 'handler')
                        and c['state'] in ('wait_ready', 'cfg_sent', 'running')
                        for c in getattr(runner, '_st', {}).values())):
            raise HTTPException(409, '生产测试进行中，不能切换调试运行模式 / Production test active')
        old_mode = mdbg.run_mode
        old_dir = mdbg.log_dir_abs()
        mappings = {"boardHost": mdbg.board_host, "board_host": mdbg.board_host,
                    "dutLines": mdbg.dut_lines, "dut_lines": mdbg.dut_lines,
                    "dutChannels": mdbg.dut_channels, "dut_channels": mdbg.dut_channels}
        changing_mapping = any(key in body and body[key] != value for key, value in mappings.items())
        if changing_mapping and any(mdbg._power.values()):
            raise HTTPException(400, "请先全部下电，再修改通讯板或 DUT 通道映射")
        try:
            settings = await runner._io(mdbg.apply_settings, body, CFG_PATH)
        except ManualDebugError as e:
            _md_raise(e)
        # 不改路径时不能 set_dir 清空活动日志会话。
        if old_dir != mdbg.log_dir_abs():
            logch.file_sink.set_dir(mdbg.log_dir_abs())
            for d in runner._duts:
                if runner._powered(d):
                    logch.file_sink.begin_run(runner._ch(d))
        if any(key in body for key in ("dutLines", "dut_lines", "dutChannels", "dut_channels")) and changing_mapping:
            await runner.resync()
        if old_mode == "full_run" and mdbg.run_mode != "full_run":
            for d in list(runner._duts):
                if runner.state(d)["state"] in ("wait_ready", "cfg_sent", "running"):
                    runner.disarm(d, powered_off=False)
        _push_manual_state()
    return {"ok": True, "settings": settings}


@app.get("/api/manual/run_state")
async def api_manual_run_state():
    """完整运行每路 DUT 状态：idle/wait_ready/cfg_sent/running/timeout/pass/fail。"""
    return runner.snapshot()


# ---------------------------------------------------------------- WebSocket

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await hub.connect(websocket)
    try:
        hub.send_to(websocket, [hub.snapshot(),
            {"type": "manual_state", **_manual_state_payload()}])
        # 手动调试快照随连接即下发（事件驱动：前端无需 REST 首屏轮询，
        # 断线重连后电源/运行状态也从这份快照自然恢复）
        while True:
            await websocket.receive_text()           # 保活；客户端消息暂不处理
    except WebSocketDisconnect:
        hub.disconnect(websocket)
    except Exception:
        hub.disconnect(websocket)


# ---------------------------------------------------------------- 静态托管（P6 浏览器形态）
# SLT_FRONTEND_DIST 环境变量可覆盖前端产物目录（桌面版打包用：dist 随 exe 走，见 desktop/）
DIST = os.environ.get("SLT_FRONTEND_DIST") or os.path.join(BASE_DIR, "..", "frontend", "dist")


@app.get("/manual")
async def manual_page():
    """/manual 是前端 SPA 路由：直接访问/刷新时回 index.html 由前端路由接管
    （StaticFiles 不做 history 回退，显式补这一条）。"""
    index = os.path.join(DIST, "index.html")
    if not os.path.isfile(index):
        raise HTTPException(404, "前端产物缺失（先构建 frontend/dist）")
    return FileResponse(index)


if os.path.isdir(DIST):
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
