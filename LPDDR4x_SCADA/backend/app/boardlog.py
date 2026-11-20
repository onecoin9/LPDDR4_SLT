"""通讯板 TCP 10080 日志流接入(2026-09-18 实证发现)。

板子在 :10080 上提供 CH9434 日志桥——混合流,包含:
  - DUT 测试日志(带 [TST]/[SYS]/[ERR] 行标签,HSG-LOG 设计)
  - 板卡自身轨迹(RemoteIoCtrThreadMain / GpioStatus 等带时间戳行)
任何客户端直连即可读;断线自动重连。

行分类 → 面板 cat:
  [TST] → dut(主控板测试日志)   [SYS] → sys(主控板系统日志)
  [ERR] → ERROR 级(dut)         板卡轨迹 → sys / INFO
DUT 行归属(2026-09-29 抓包定案): 帧类型即通道号——type 高 4 位=通道-1、
低 4 位=1 为文本流(CH5→0x41/CH6→0x51/CH7→0x61,与 UDP 通道上线时间对齐
实证),按流精确分流,多 DUT 并发不串台;[DUTx] 前缀优先;形态不认识的
文本帧才退回 dut_hint()(唯一活动 DUT)。
落盘(2026-09-29 用户拍板"全部落盘"): 有通道 → dutN.log;无通道文本行、
板卡 0xC0/0xC1 轨迹、0xN0 通道 LOG BEGIN → 同轮目录 system.log。
"""
from __future__ import annotations

import asyncio
import re
from typing import Callable, Optional


_LINE_BREAK = re.compile(r"\r\n|\r|\n")


class BoardLogClient:
    def __init__(self, hub, host: str, port: int = 10080,
                 dut_hint: Optional[Callable[[], Optional[int]]] = None,
                 max_line: int = 4000, sink_write=None,
                 sink_write_system=None):
        self.hub = hub
        self.host = host
        self.port = port
        self.dut_hint = dut_hint or (lambda: None)
        # 落盘回调（2026-09-24）：本 rig 板卡文本实测全走 10080 腿（63001 零包，
        # RAW 诊断实证），而 DutLogFileSink 原只挂在 logchannel——导致 manual_logs
        # 永远为空。归因到 DUT 的行补写 [DUTx] 前缀后交落盘（与 63001 行同格式）。
        self.sink_write = sink_write
        # 系统行落盘（2026-09-29 用户拍板"全部落盘"）：显式传入优先；缺省从
        # sink_write 的绑定对象取 write_system——main.py 只传了 sink_write 也能
        # 接上（该文件当时有未提交 WIP，避免为其加参数）。
        if sink_write_system is not None:
            self.sink_write_system = sink_write_system
        else:
            owner = getattr(sink_write, "__self__", None)
            self.sink_write_system = getattr(owner, "write_system", None)
        self.max_line = max_line
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        # 分帧状态（2026-09-18 实证）：帧 = AF <type> <len16 LE> <payload>
        #   0x41/0x61 均为文本日志帧（2026-09-28 实证：板卡 CH9434 日志桥有
        #   多条 TCP 连接，type 低 4 位 1=文本流；只认 0x41 会整股丢另一条流
        #   ——DUT6-8 的日志全在 0x61 里被静默丢弃的根因）；0x03 之类为空帧
        # 因此必须先把二进制帧头吃掉再拼文本行，不能按换行切原始字节流。
        self._rx = b""          # 未消费完的原始字节
        self._texts = {}        # 流类型 → 半行缓冲（每条流独立拼行）
        self.max_frame = 4096
        self.max_pending = max_line
        self._dbg_n = {}        # [临时诊断] 帧类型计数

    @property
    def _text(self) -> str:
        """单流兼容视图（遗留字段读法，缺省 0x41 流）。"""
        return self._texts.get(0x41, "")

    @_text.setter
    def _text(self, v: str) -> None:
        self._texts[0x41] = v

    # ---------------- 生命周期 ----------------

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run())

    async def close(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ---------------- 主循环 ----------------

    async def _run(self) -> None:
        fail_n = 0
        while not self._stop.is_set():
            try:
                reader, _ = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), timeout=3)
                if fail_n:
                    self.hub.syslog("INFO",
                                    f"通讯板日志流已恢复（此前失败 {fail_n} 次）")
                    fail_n = 0
                self.hub.syslog("INFO",
                                f"通讯板日志流已连接 {self.host}:{self.port}")
                await self._pump(reader)
            except (OSError, asyncio.TimeoutError) as e:
                fail_n += 1
                # 节流（2026-09-28）：首条 + 每 20 次（约 1 分钟）一条——
                # 演示/无板机 3s 一条会刷屏，治具上首条+周期条足够排障
                if fail_n == 1 or fail_n % 20 == 0:
                    self.hub.syslog("WARN",
                                    f"通讯板日志流连接失败({e})，已重试 {fail_n} 次"
                                    f"（每 3s 重连）")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=3)
                except asyncio.TimeoutError:
                    pass
            except asyncio.CancelledError:
                raise

    async def _pump(self, reader: asyncio.StreamReader) -> None:
        self._rx = b""
        self._texts = {}
        while not self._stop.is_set():
            chunk = await reader.read(65536)
            if not chunk:
                for t, buf in list(self._texts.items()):   # 断开前吐残留半行
                    if buf.strip():
                        self._emit(buf.rstrip("\r\n"), t)
                    self._texts[t] = ""
                self._rx = b""
                self.hub.syslog("WARN", "通讯板日志流断开,重连中")
                return
            self._feed(chunk)

    # ---------------- 分帧 ----------------

    @staticmethod
    def _is_text_frame(ftype: int) -> bool:
        """文本日志帧判定：板卡日志桥（CH9434 转发）对每条 TCP 连接用一个
        流类型，bit0=1 为文本（0x41/0x61 实证；2026-09-28 DUT6-8 的日志全在
        0x61 流，只认 0x41 会整股静默丢弃）。0x03 空/0xCx 板轨迹排除：
        0x03 bit0=1 但载荷恒空且无行结构，0xC0/0xC1 bit0=0。"""
        return (ftype & 0x01) == 0x01 and not (ftype & 0x80) and ftype != 0x03

    def _feed(self, chunk: bytes) -> None:
        """把原始字节按 AF <type> <len16> 切帧；文本帧的载荷交给 _accept。"""
        buf = self._rx + chunk if self._rx else chunk
        i, n = 0, len(buf)
        while i < n:
            if buf[i] != 0xAF:
                nxt = buf.find(b"\xaf", i)
                if nxt < 0:
                    i = n
                    break
                i = nxt
                continue
            if i + 4 > n:                       # 帧头还没收全
                break
            ln = buf[i + 2] | (buf[i + 3] << 8)
            if ln > self.max_frame:             # 假帧头，往下找
                i += 1
                continue
            if i + 4 + ln > n:                  # 载荷还没收全
                break
            ftype = buf[i + 1]
            if self._is_text_frame(ftype):      # 文本日志帧（多流，各自拼行）
                self._accept(buf[i + 4:i + 4 + ln], ftype)
            else:
                self._dbg_frame(ftype, buf[i + 4:i + 4 + ln])
                self._board_trace(ftype, buf[i + 4:i + 4 + ln])
            i += 4 + ln
        self._rx = buf[i:] if i < n else b""

    def _dbg_frame(self, ftype, payload) -> None:
        """[临时诊断] 非文本帧样本落盘（0xC1 板日志记录——查 CH9434 端口读取）。"""
        try:
            self._dbg_n[ftype] = self._dbg_n.get(ftype, 0) + 1
            cap = 500 if ftype == 0xC1 else 20
            if self._dbg_n[ftype] <= cap:
                text = payload.decode("utf-8", "replace")[:150].replace("\n", "\\n").replace("\r", "")
                with open("boardlog_frames.log", "a", encoding="utf-8") as f:
                    f.write(f"type={ftype:#04x} n={self._dbg_n[ftype]} "
                            f"len={len(payload)}: {text}\n")
        except OSError:
            pass

    def _board_trace(self, ftype: int, payload: bytes) -> None:
        """非文本帧中的板卡轨迹/通道 LOG BEGIN → system.log（2026-09-29 用户
        拍板"全部落盘"）。只落盘不上面板（0xC1 轨迹量大，上 WS 会刷屏）：
        - 0xC0/0xC1：板卡自身轨迹（RemoteIo/Gpio/LOG BEGIN 头，带板内时间戳）；
        - 0xN0（bit7=0 且低 4 位=0）：通道 N+1 的 LOG BEGIN 标记帧（2026-09-29
          抓包实证与 0xN1 文本流成对出现），补 [CHn] 前缀；
        - 0x03 心跳与其余未知帧：不落（_dbg_frame 的限量样本仍留档排障）。"""
        if self.sink_write_system is None or not payload:
            return
        if ftype in (0xC0, 0xC1):
            self._sys_lines(payload)
        elif not (ftype & 0x80) and (ftype & 0x0F) == 0:
            self._sys_lines(payload, prefix=f"[CH{(ftype >> 4) + 1}] ")

    def _sys_lines(self, payload: bytes, prefix: str = "") -> None:
        """按行拆非文本帧载荷，逐行交 system.log（NUL 行滤掉）。"""
        for ln in _LINE_BREAK.split(payload.decode("utf-8", "replace")):
            if ln.strip():
                self.sink_write_system(prefix + ln.rstrip("\r"))

    def _accept(self, payload: bytes, ftype: int = 0x41) -> None:
        """载荷是字节流的一段，可能半行开始/结束，按行拼接后再上报。
        每条流（帧类型）独立缓冲——两条流的半行混在一个缓冲里会互相撕碎。"""
        buf = self._texts.get(ftype, "") + payload.decode("utf-8", errors="replace")
        # DUT 侧行尾不统一：\r\r\n 为主，也有单独的 \r —— 两种都当换行处理
        parts = _LINE_BREAK.split(buf)
        self._texts[ftype] = parts.pop()
        for line in parts:
            if line.strip():
                self._emit(line, ftype)
        if len(self._texts[ftype]) > self.max_pending:  # 长期不换行的兜底
            self._emit(self._texts[ftype].rstrip("\r"), ftype)
            self._texts[ftype] = ""

    # ---------------- 行分类 ----------------

    _DUT_PREFIX_RE = re.compile(r"^\[DUT(\d{1,2})\]\s*(.*)$", re.S)

    @staticmethod
    def _slot_from_ftype(ftype: Optional[int]) -> Optional[int]:
        """帧类型 → 通道号（2026-09-29 抓包实证）：type 高 4 位=通道号-1、
        低 4 位=1 为文本流——CH5→0x41 / CH6→0x51 / CH7→0x61（三路首帧时间
        与 UDP 2005-2007 通道上线时间一一对齐）。只认已证实的形态；bit7=1
        （0xC1 板卡轨迹）与低 4 位≠1 的不认，交回 dut_hint() 兜底。"""
        if ftype is None or (ftype & 0x0F) != 0x01 or (ftype & 0x80):
            return None
        ch = ((ftype >> 4) & 0x0F) + 1
        return ch if ch <= 12 else None

    def _emit(self, line: str, ftype: Optional[int] = None) -> None:
        if not line.replace("\x00", "").strip():
            return
        # [2026-09-28 对齐旧上位机] 板卡转发器分包可能把 63001 风格的
        # [DUTx] 前缀带进 10080 流（旧机 FlushMalformedLeadingToken 同款
        # 场景）：行首有前缀时按前缀精确分路，多 DUT 并发也不串台。
        m = self._DUT_PREFIX_RE.match(line)
        if m:
            slot = int(m.group(1))
            line = m.group(2)
            if not line.strip():
                return
            self._emit_body(line, slot)
            return
        # 2026-09-29 抓包定案：文本帧类型即通道号，多 DUT 并发精确分流；
        # 认不出的形态才退回单 DUT 启发式（多 DUT 活动时为 None=系统级）。
        slot = self._slot_from_ftype(ftype)
        if slot is None:
            slot = self.dut_hint()
        self._emit_body(line, slot)

    def _emit_body(self, line: str, slot) -> None:
        if line.startswith("[ERR]"):
            self.hub.log(1, slot, "ERROR", line[5:].strip() or line, cat="dut")
        elif line.startswith("[TST]"):
            self.hub.log(1, slot, "INFO", line[5:].strip(), cat="dut")
        elif line.startswith("[SYS]"):
            self.hub.log(1, slot, "INFO", line[5:].strip(), cat="sys")
        elif line.startswith("[HSG]") or line.startswith("[AC]") or line.startswith("=========="):
            # DUT preloader 横幅/流程行 —— 无标签时也归 dut（[HSG]→[AC] 合规更名
            # 后前缀同步，2026-09-23：漏了这半边导致 [AC] 行被归系统级且不进 DUT 页签）
            self.hub.log(1, slot, "INFO", line, cat="dut")
        else:
            # 板卡轨迹(RemoteIo/Gpio/时间戳行)与其余杂项 → 系统级
            self.hub.log(1, None, "INFO", line, cat="sys")
        # 落盘（2026-09-29 用户拍板"全部落盘"）：通道已知 → dutN.log——无标签
        # 杂行也在该 DUT 自己的流上，照落；通道未知（真未归属文本）→ system.log，
        # 一条不丢。面板分类（cat）与此独立：无标签杂行面板仍走系统页签。
        if slot is not None:
            if self.sink_write:
                self.sink_write(f"[DUT{slot}] {line}")
        elif self.sink_write_system is not None:
            self.sink_write_system(line)
