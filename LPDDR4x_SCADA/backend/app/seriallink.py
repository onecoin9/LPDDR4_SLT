"""流式 DUT 会话公共层 + 串口直连实现（sites.mode=serial）。

链路事实（固件实证，2026-09-07 上机链路调试结论的权威沉淀）：
  - UART1（115200-8N1）上**文本日志与 0xAF 协议帧混流**（LOG_TO_UART1=1 生效后
    全平台日志镜像到测试口）→ StreamParser 流式分离（跨包缓存、假帧头回退）
  - 固件 send_command_with_ack 每帧（0x10/0x11/0x16/0x17/0x18）后**阻塞等上位机
    ACK**（AF 02 00 00 <cmd> 00 00 55 EF），收不到每 ~3s 重发无限重试——mock 不等
    ACK 所以 UDP 联调发现不了；本会话在读线程里收到即回（auto_ack 默认开）
  - 0x15 cfg 载荷上限 505B（固件 512B 收包缓冲），超限由 cfg.py/cfg_text 侧约束

与 UDP 版 DutSession 的关键语义差异（真机行为，非偷懒）：
  - **无心跳**：真实协议无心跳命令，DUT ACK 完 0x10 后静默等 cfg 属正常状态，
    UDP 版的"6s 无数据判离线"会把等 cfg 的 DUT 误判离线——流式会话的在线判定 =
    收到过 0x10；离线 = 传输断开（串口异常 / TCP 断连的物理语义）
  - 文本日志经行拼装后 cat="dut" 推 hub，同时入订阅队列（sequencer 落盘），
    UDP 架构里文本走 63001 日志通道，流式直连没有那条腿

结构：BaseStreamSession 承载解析/路由/行拼装/自动 ACK 决策（串口与 TCP 共用，
见 tcplink.py）；子类只实现传输（读循环怎么拿字节、怎么写、怎么把事件送回
asyncio 线程）。
"""

import asyncio
import codecs
import threading
import time
from typing import Any, List, Optional, Set, Tuple

import serial  # pyserial

from .protocol import (Ack, DramInfo, DutLog, Progress, Ready, TestDone,
                       build_frame, ROLE_SERVER)

HEAD_B, TAIL_B = 0xAF, 0xEF


class _Offline:
    """内部事件：链路断开（推给测试任务，使其以 FAIL(连接断开) 收尾）。
    定义在此处供 connection/sequencer 复用（sequencer 从 connection 导入）。"""


class _DutReboot:
    """内部事件：测试中收到 0x10 READY —— DUT 重启（旧上位机 DutMaster 语义：
    ST_TEST_START 收 EVT_SLAVE_READY → FAIL2 + SCODE_DUT_REBOOT 0xFE"测试板重启"）。"""


def _checksum_ok(frame: bytes) -> bool:
    plen = frame[1] | (frame[2] << 8)
    c = 0x55
    for b in frame[5:5 + plen]:
        c ^= b
    return c == frame[5 + plen]


class StreamParser:
    """字节流 → ('text', str) / ('frame', bytes) 事件（跨包缓存、增量解码）。

    文本里碰巧出现 0xAF 按帧头候选逐个验证（长度/尾标/校验和），失败回退 1 字节。
    MAX_FRAME 为线侧防御上限（固件 TX 载荷 ≤255，PC→DUT cfg ≤505）。
    """

    MAX_FRAME = 1024

    def __init__(self):
        self._buf = bytearray()
        self._dec = codecs.getincrementaldecoder("utf-8")("replace")

    def reset(self) -> None:
        self._buf.clear()
        self._dec.reset()

    def _text(self, seg, events: list) -> None:
        if seg:
            s = self._dec.decode(bytes(seg))
            if s:
                events.append(("text", s))

    def feed(self, data: bytes) -> List[Tuple[str, Any]]:
        events: List[Tuple[str, Any]] = []
        self._buf += data
        buf = self._buf
        pos, n = 0, len(buf)
        while pos < n:
            i = buf.find(HEAD_B, pos)
            if i < 0:                                   # 无帧头候选：全部按文本
                self._text(buf[pos:], events)
                del buf[:]
                return events
            if i + 3 > n:                               # len 字段未到齐
                self._text(buf[pos:i], events)
                del buf[:i]                             # 保留候选头等下一包
                return events
            plen = buf[i + 1] | (buf[i + 2] << 8)
            if plen > self.MAX_FRAME:                   # 假帧头（文本里的 0xAF）
                self._text(buf[pos:i + 1], events)
                pos = i + 1
                continue
            total = plen + 7
            if i + total > n:                           # 帧未到齐
                self._text(buf[pos:i], events)
                del buf[:i]
                return events
            cand = bytes(buf[i:i + total])
            if cand[-1] == TAIL_B and _checksum_ok(cand):
                self._text(buf[pos:i], events)
                events.append(("frame", cand))
                pos = i + total
            else:                                       # 校验失败 → 回退 1 字节
                self._text(buf[pos:i + 1], events)
                pos = i + 1
        del buf[:]
        return events


class _UnknownFrame:
    """校验合法但 codec 不认识的帧（未知命令/长度）——按 WARN 日志呈现"""

    def __init__(self, frame: bytes):
        self.frame = frame
        self.cmd = frame[4]
        self.payload = frame[5:-2]

    def __str__(self):
        return f"未知帧 cmd=0x{self.cmd:02X} len={len(self.payload)} {self.payload[:48].hex(' ')}"


def resolve_port(port: str) -> str:
    """'auto' → 枚举第一个 COM 口；显式端口名原样返回"""
    if port and port.lower() != "auto":
        return port
    import serial.tools.list_ports as lp
    ports = [p.device for p in lp.comports()]
    if not ports:
        raise OSError("未发现任何串口设备（USB 串口适配器未插入？）")
    return ports[0]


class BaseStreamSession:
    """流式 DUT 会话公共层：解析、事件路由（Hub/订阅队列）、行拼装、自动 ACK 决策。

    子类契约：
      _send_bytes(frame)   —— 同步写线（自动 ACK 在读上下文即时发）
      _schedule(fn, *args) —— 把事件处理送到 asyncio 线程（串口=call_soon_threadsafe，
                              TCP=直接调用，读循环本就在 asyncio 里）
      _feed(data)          —— 读循环每拿到一段字节调一次（子类负责调用）
    """

    def __init__(self, site: int, slot: int, codec, hub, cfg: Optional[dict] = None):
        cfg = cfg or {}
        self.site, self.slot = site, slot
        self.auto_ack = bool(cfg.get("auto_ack", True))
        self.codec = codec
        self.hub = hub
        self.connected = False
        self.version = ""
        self.ready_generation = 0
        self._awaiting_ready = False
        self._ignore_frames = False
        self.dram_info = ""
        self.rx_bytes = 0
        self.tx_bytes = 0
        self._parser = StreamParser()
        self._line = ""                             # DUT 文本行拼装缓冲
        self._queues: Set[asyncio.Queue] = set()

    # ---- 子类实现 ----

    def _send_bytes(self, frame: bytes) -> None:
        raise NotImplementedError

    def _schedule(self, fn, *args) -> None:
        fn(*args)

    # ---- 解析与路由（读上下文调用） ----

    def _feed(self, data: bytes) -> None:
        for kind, payload in self._parser.feed(data):
            if kind == "text":
                self._on_text(payload)
            else:
                # 帧边界：先冲刷未换行的半行文本，再处理帧
                self._flush_line()
                self._on_frame(payload)

    def _on_frame(self, frame: bytes) -> None:
        msg = self.codec.decode(frame)
        if not isinstance(msg, Ack):
            # 固件每帧阻塞等 ACK：读上下文立即回（语义未知的帧也回，防卡死）
            if self.auto_ack:
                try:
                    self._send_bytes(
                        build_frame(ROLE_SERVER, frame[4], bytes([0x00, 0x00])))
                except Exception as e:
                    self._schedule(
                        self.hub.log, self.site, self.slot, "WARN",
                        f"CH{self.slot:02d} 自动 ACK 发送失败: {e}")
            if msg is None:
                msg = _UnknownFrame(frame)
        self._schedule(self._dispatch, msg)

    def _on_text(self, s: str) -> None:
        self._line += s.replace("\r\n", "\n").replace("\r", "\n")
        while "\n" in self._line:
            line, self._line = self._line.split("\n", 1)
            if line:
                self._schedule(self._dispatch, DutLog("INFO", line.rstrip()))
        if len(self._line) > 4096:                  # 无换行超长行兜底
            self._flush_line()

    def _flush_line(self) -> None:
        if self._line:
            line, self._line = self._line, ""
            self._schedule(self._dispatch, DutLog("INFO", line.rstrip()))

    # ---- asyncio 线程：事件路由（与 UDP DutSession._on_data 同构） ----

    def _dispatch(self, msg: Any) -> None:
        if self._ignore_frames:
            return
        hub = self.hub
        if isinstance(msg, Ready):
            self.ready_generation += 1
            # 测试中收到 0x10 = DUT 重启（旧上位机判 FAIL dut_reboot 0xFE）；
            # 非测试态才是正常上线
            if hub.ensure(self.site, self.slot)["state"] == "TESTING" and not self._awaiting_ready:
                hub.log(self.site, self.slot, "ERROR",
                        f"CH{self.slot:02d} 测试中收到 0x10 —— DUT 已重启", cat="conn")
                for q in list(self._queues):
                    q.put_nowait(_DutReboot())
                return
            self.version = msg.version
            if not self.connected:
                self.connected = True
                state = hub.ensure(self.site, self.slot)
                if state["state"] == "OFFLINE":
                    hub.update(self.site, self.slot, connected=True, state="IDLE",
                               step="-", progress=0, countdownSec=0.0, testInfo="")
                else:
                    hub.update(self.site, self.slot, connected=True)
                hub.log(self.site, self.slot, "INFO",
                        f"CH{self.slot:02d} 上线 · 版本 {msg.version}", cat="conn")
            return
        if isinstance(msg, Ack):
            hub.log(self.site, self.slot, "INFO",
                    f"CH{self.slot:02d} 命令确认 ACK 0x{msg.cmd:02X} status={msg.status}")
            # 入订阅队列：sequencer 以 0x15 ACK 作为停止配置重发的依据（旧上位机语义）
            for q in list(self._queues):
                q.put_nowait(msg)
            return
        if isinstance(msg, DramInfo):
            self.dram_info = str(msg)
            hub.log(self.site, self.slot, "INFO", f"CH{self.slot:02d} {msg}")
            return
        if isinstance(msg, _UnknownFrame):
            hub.log(self.site, self.slot, "WARN", f"CH{self.slot:02d} {msg}")
            return
        if isinstance(msg, DutLog):
            hub.log(self.site, self.slot, msg.level, f"CH{self.slot:02d} {msg.msg}")
        if isinstance(msg, (Progress, DutLog, TestDone)):
            for q in list(self._queues):
                q.put_nowait(msg)

    def _on_link_dead(self, reason: str) -> None:
        self.connected = False
        st = self.hub.ensure(self.site, self.slot)
        was_testing = self.hub.ensure(self.site, self.slot)["state"] == "TESTING" and not self._awaiting_ready
        self.hub.update(self.site, self.slot, connected=False, state=st["state"] if st["state"] in ("PASS", "FAIL") else "OFFLINE",
                        testInfo=st["testInfo"] if st["state"] in ("PASS", "FAIL") else "连接断开")
        self.hub.log(self.site, self.slot, "ERROR", f"CH{self.slot:02d} {reason}",
                     cat="conn")
        if was_testing:
            for q in list(self._queues):
                q.put_nowait(_Offline())

    # ---------------- 事件订阅（sequencer 用，与 DutSession 一致） ----------------

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)


class SerialDutSession(BaseStreamSession):
    """单颗 DUT 的串口直连会话（接口与 UDP 版 DutSession 同构）。

    cfg 取 serial_dut 节：{port: auto|COMx, baudrate: 115200, auto_ack: true}
    线程模型：start() 开 1 个 reader 线程（阻塞读 + 解析 + 自动 ACK 写），
    事件经 loop.call_soon_threadsafe 送回 asyncio 线程（Hub/queue 都是 loop 上下文）。
    """

    def __init__(self, site: int, slot: int, port: str, codec, hub, cfg: dict):
        super().__init__(site, slot, codec, hub, cfg)
        self.port = str(port)
        self.baudrate = int(cfg.get("baudrate", 115200))
        self.transport = None                       # 仅为 duck-type 兼容
        self._ser: Optional[serial.SerialBase] = None
        self._thread: Optional[threading.Thread] = None
        self._close_req = threading.Event()
        self._wr_lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ---------------- 生命周期 ----------------

    async def start(self) -> None:
        port = resolve_port(self.port)
        ser = serial.Serial(port=port, baudrate=self.baudrate,
                            bytesize=8, parity="N", stopbits=1,
                            timeout=0.1, write_timeout=3.0,
                            rtscts=False, dsrdtr=False)
        self._ser = ser
        self.port = port
        self._loop = asyncio.get_running_loop()
        self._close_req.clear()
        self._thread = threading.Thread(target=self._reader, daemon=True,
                                        name=f"serial-{port}")
        self._thread.start()
        self.hub.ensure(self.site, self.slot)
        self.hub.log(None, None, "INFO",
                     f"串口直连模式：{port} @ {self.baudrate}（SITE{self.site:02d} "
                     f"CH{self.slot:02d}，自动 ACK {'开' if self.auto_ack else '关'}）",
                     cat="conn")

    async def close(self) -> None:
        ser, self._ser = self._ser, None
        self._close_req.set()
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self.connected:
            self.connected = False
            self.hub.update(self.site, self.slot, connected=False,
                            state="OFFLINE", testInfo="后端关闭串口")

    # ---------------- 传输实现（BaseStreamSession 契约） ----------------

    def _send_bytes(self, frame: bytes) -> None:
        ser = self._ser
        if ser is None or not ser.is_open:
            raise RuntimeError("串口未连接")
        with self._wr_lock:
            ser.write(frame)
        self.tx_bytes += len(frame)

    def _schedule(self, fn, *args) -> None:
        self._loop.call_soon_threadsafe(fn, *args)

    # ---- 发送（asyncio 线程上下文调用，sequencer 用） ----

    def send(self, msg: Any) -> None:
        payload = self.codec.encode(msg)
        if not payload:
            return                                  # 协议不承载（心跳/停止）
        try:
            self._send_bytes(payload)
        except Exception as e:
            self._loop.call_soon_threadsafe(self._on_link_dead, f"串口写入失败: {e}")

    # ---------------- reader 线程 ----------------

    def _reader(self) -> None:
        ser = self._ser
        parser = self._parser
        while not self._close_req.is_set():
            try:
                data = ser.read(4096)
            except Exception as e:
                if self._close_req.is_set():
                    break
                self._loop.call_soon_threadsafe(self._on_link_dead, f"串口异常: {e}")
                return
            if not data:
                continue
            self.rx_bytes += len(data)
            self._feed(data)
