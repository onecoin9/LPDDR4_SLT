"""DUT 运行日志通道（UDP 63001）。

真实链路：DUT/MTK 的运行日志经通讯板转发到 PC 的 UDP 63001 端口，
每行以 `[DUTx]` 前缀标识通道（旧上位机 CommBoardLogService 的行为）。
多 site 扩展：本工程约定 mock/新固件使用 `[S<site>DUT<slot>]` 前缀；
裸 `[DUTxx]` 视为 SITE 1（兼容旧固件）。来源 IP 区分板卡的能力待 P3
真机联调时接入（mock 全部来自 127.0.0.1，无法区分，靠前缀）。
"""

import asyncio
import os
import re
import time
from typing import Optional

from .connection import ConnectionManager
from .ws import Hub

_TAG = re.compile(r"^\[(?:S(\d{1,2}))?DUT(\d{1,2})\]\s*(.*)")

# [HSG-LOG 2026-09-16] DUT 文本行行首分类标签（固件 PL/LK/Android 输出层打上）：
#   [SYS] 主控板系统运行日志 → cat="sys"（与上位机自身 system 分开）
#   [TST] 测试进度/结果 → cat="dut"（级别仍按 fail/error 关键词推导）
#   [ERR] 失败/错误 → cat="dut" + level=ERROR
# 无标签 = 旧固件行，保持原行为（cat="dut" + 关键词级别推导）。
_CLS_TAG = re.compile(r"^\[(SYS|TST|ERR)\]\s*(.*)")


def _apply_cls(body: str):
    """剥行首分类标签 → (cat, level_override, 去标签后的正文)。"""
    m = _CLS_TAG.match(body)
    if not m:
        return None, None, body
    tag, rest = m.group(1), m.group(2)
    if tag == "SYS":
        return "sys", "INFO", rest
    if tag == "ERR":
        return "dut", "ERROR", rest
    return "dut", None, rest


class DutLogFileSink:
    """[DUTx] 日志落盘（2026-09-29 按用户拍板重构）：
    - 目录结构：<logDir>/<轮次时间戳>/dut{n}.log + system.log
    - **同轮上电共目录**：任一会话活跃期间新开的会话沿用同一时间戳目录
      （多路并发一轮一处看全）；全部会话结束后再上电才开新轮；单路中途
      重启（他人仍活跃）沿用同目录，dutN.log 追加、行首时间戳区分轮次。
      目录名取轮次首个 begin_run 时刻（2026-09-20 版取首行写入时刻，已改）。
    - **system.log**：系统级行（板卡 0xC1 轨迹、通道 LOG BEGIN、无通道归属
      的 DUT 文本）经 write_system 落盘；轮次结束后仍顺延写最近一轮（不丢行）。
    - 会话外的 [DUTx] 行维持丢弃（2026-09-29 用户拍板"现状"）。

    落盘故障韧性（修 2026-09-29 实证的"自禁用"缺陷——一条 OSError 曾把
    整个 sink 静默关死且无任何日志）：任何异常只丢当条并经 warner 告警
    （首条 + 每 100 条限频），不再清 _dir 自禁用，后续行继续尝试重开文件。
    warner 由 LogChannel 注入 hub.syslog。
    """

    def __init__(self, warner=None):
        self._dir = ""
        self._fh = {}          # dut -> 打开的文件句柄
        self._ts = set()       # 活跃会话的通道号（名字沿用 _ts，历史测试引用）
        self._round_ts = None  # 当前/最近一轮时间戳（目录名）
        self._sys_fh = None    # system.log 句柄（随轮次切换重开）
        self._err_n = 0
        self.warner = warner

    def _warn(self, msg: str) -> None:
        self._err_n += 1
        if self._err_n == 1 or self._err_n % 100 == 0:
            cb = self.warner
            if cb:
                try:
                    cb(f"{msg}（累计 {self._err_n} 次）")
                except Exception:
                    pass

    def set_dir(self, d: str) -> None:
        d = (d or "").strip()
        if d == self._dir:
            return
        self._close()
        self._dir = d

    def _round_dir(self) -> str:
        if self._round_ts is None:
            self._round_ts = time.strftime("%Y%m%d_%H%M%S")
        return os.path.join(self._dir, self._round_ts)

    def begin_run(self, dut: int) -> None:
        """上电/进入运行态：幂等；会话全空时开新轮（见类注释）。"""
        if dut in self._ts:
            return                            # 已在记录中,不重启
        if not self._ts:
            self._round_ts = time.strftime("%Y%m%d_%H%M%S")
            if self._sys_fh is not None:      # system.log 切到新轮目录
                try:
                    self._sys_fh.close()
                except Exception:
                    pass
                self._sys_fh = None
        self._ts.add(dut)

    def end_run(self, dut: int) -> None:
        """DUT 结束（PASS/FAIL/超时/下电）：关闭文件。轮次目录保留至下一轮。"""
        fh = self._fh.pop(dut, None)
        if fh:
            try:
                fh.close()
            except Exception:
                pass
        self._ts.discard(dut)

    def _close(self) -> None:
        for fh in list(self._fh.values()) + [self._sys_fh]:
            if fh is None:
                continue
            try:
                fh.close()
            except Exception:
                pass
        self._fh.clear()
        self._sys_fh = None
        self._ts.clear()
        self._round_ts = None

    def write(self, line: str) -> None:
        """DUT 行（含 [DUTx] 前缀，63001 原始行 / boardlog 归因行同格式）。
        只有处于运行态的 DUT 行落盘；无前缀/未运行的行丢弃（系统级行走
        write_system；面板与 WS 不受影响）。"""
        if not self._dir:
            return
        m = _TAG.match(line)
        if not m:
            return                          # 系统级（总览）走 write_system
        dut = int(m.group(2))
        if dut not in self._ts:
            return                          # 未在运行态
        # 合规（2026-09-19）：HSG 为他司代号，落盘替换为 AC（与 hub.log 一致）
        line = line.replace("HSG", "AC").replace("hsg_", "ac_")
        try:
            fh = self._fh.get(dut)
            if fh is None:
                run_dir = self._round_dir()
                os.makedirs(run_dir, exist_ok=True)
                fh = open(os.path.join(run_dir, f"dut{dut}.log"),
                          "a", encoding="utf-8")
                self._fh[dut] = fh
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
            fh.flush()
        except Exception as e:  # noqa: BLE001 —— 只丢当条，绝不自禁用（09-29 教训）
            fh = self._fh.pop(dut, None)
            if fh:
                try:
                    fh.close()
                except Exception:
                    pass
            self._warn(f"DUT 日志落盘失败 dut{dut}: {e!r}——丢当条，继续")

    def write_system(self, line: str) -> None:
        """系统级行 → 本轮（或最近一轮）目录 system.log（2026-09-29 全部落盘）。"""
        if not self._dir:
            return
        line = line.replace("HSG", "AC").replace("hsg_", "ac_")
        try:
            if self._sys_fh is None:
                run_dir = self._round_dir()
                os.makedirs(run_dir, exist_ok=True)
                self._sys_fh = open(os.path.join(run_dir, "system.log"),
                                    "a", encoding="utf-8")
            self._sys_fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
            self._sys_fh.flush()
        except Exception as e:  # noqa: BLE001 —— 同上，绝不自禁用
            if self._sys_fh is not None:
                try:
                    self._sys_fh.close()
                except Exception:
                    pass
                self._sys_fh = None
            self._warn(f"系统日志落盘失败: {e!r}——丢当条，继续")


class LogChannel(asyncio.DatagramProtocol):
    def __init__(self, hub: Hub, conns: ConnectionManager, port: int = 63001):
        self.hub = hub
        self.conns = conns
        self.port = port
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.file_sink = DutLogFileSink(
            warner=lambda msg: hub.syslog("WARN", msg))

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: self, local_addr=("0.0.0.0", self.port))
        self.hub.syslog("INFO", f"DUT 日志通道已监听 UDP :{self.port}")

    async def close(self) -> None:
        if self.transport:
            self.transport.close()

    def datagram_received(self, data: bytes, addr) -> None:
        text = data.decode("utf-8", "replace")
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            self.file_sink.write(line)      # 落盘原始行（含 [DUTx] 前缀）
            m = _TAG.match(line)
            if not m:
                # 无前缀：板卡转发器把 [DUTx] 前缀留在上一包尾部时会出现；
                # 归系统级显示但不丢
                cat, _, body0 = _apply_cls(line)
                self.hub.log(None, None, "INFO", f"[63001] {body0}",
                             cat=cat or "dut")
                continue
            site, slot = int(m.group(1) or 1), int(m.group(2))
            body = m.group(3)
            # [2026-09-28 对齐旧上位机] 63001 前缀 x = 板卡 uartId（0-11，
            # 芯片1→0-3/芯片2→4-7），不再查 conns.sessions（那是上位机
            # 透传会话的 slot 空间，与板卡 uartId 无对应关系——此前把合法
            # 前缀行当"未知通道"丢弃，是多路分路失效的另一半原因）。
            # 手动 rig 直接按前缀分路；自动线 slot 与 uartId 同空间时同样成立。
            cat, lv, body = _apply_cls(body)
            low = body.lower()
            level = (lv or ("ERROR" if ("fail" in low or "error" in low)
                            else "WARN" if "warn" in low else "INFO"))
            self.hub.log(site, slot, level, f"CH{slot:02d} {body}",
                         cat=cat or "dut")
