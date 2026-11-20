"""BoardLogClient 多通道归因（2026-09-29 抓包定案回写）。

抓包实证（diag/multi_ch_10080_20260929.pcapng）：10080 流帧
AF <type> <len16 LE> <payload> 的 type 即通道号——高 4 位=通道-1、
低 4 位=1 为文本流（CH5→0x41 / CH6→0x51 / CH7→0x61）。多 DUT 并发时
各通道文本分属不同流，按流归因即可精确分流，不再依赖单 DUT hint。
"""

import os
import sys
import tempfile
import types
import unittest

# 本机 managed python 无 fastapi；app.ws 仅把 WebSocket 用作类型标注，打桩即可
try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    _stub = types.ModuleType("fastapi")
    _stub.WebSocket = object  # type: ignore[attr-defined]
    sys.modules["fastapi"] = _stub

from app.boardlog import BoardLogClient
from app.ws import Hub


def frame(ftype: int, payload: bytes) -> bytes:
    ln = len(payload)
    return bytes((0xAF, ftype, ln & 0xFF, ln >> 8)) + payload


class _Rig:
    def __init__(self, hint=None):
        self.hub = Hub()
        self.sent = []
        self.hub._broadcast = self.sent.append  # type: ignore[method-assign]
        self.sink = []
        self.client = BoardLogClient(
            self.hub, "192.168.50.100",
            dut_hint=(lambda: hint) if hint is not None else (lambda: None),
            sink_write=self.sink.append)
        # 非文本帧样本落盘（诊断文件）在单测里不产生副作用
        self.client._dbg_frame = lambda ftype, payload: None

    def dut_logs(self):
        return [(m["slot"], m["msg"]) for m in self.sent
                if m["type"] == "log" and m.get("cat") == "dut"]


class TestFtypeAttribution(unittest.TestCase):
    def test_multichannel_streams_attributed_by_ftype(self):
        """三路 DUT 并发（0x41/0x51/0x61 交织到达）→ 各自归到 CH5/6/7，
        不依赖 dut_hint（恒 None——多 DUT 活动时 hint 本来就给不出）。"""
        rig = _Rig()
        rig.client._feed(
            frame(0x41, b"[TST] hello ch5\r\n")
            + frame(0x51, b"[TST] hello ch6\r\n")
            + frame(0x61, b"[TST] hello ch7\r\n")
            + frame(0x41, b"[TST] more ch5\r\n"))
        self.assertEqual(rig.dut_logs(),
                         [(5, "hello ch5"), (6, "hello ch6"),
                          (7, "hello ch7"), (5, "more ch5")])

    def test_dut_prefix_wins_over_ftype(self):
        """行首 [DUTx] 前缀优先于流类型归因（显式标记最可信）。"""
        rig = _Rig()
        rig.client._feed(frame(0x41, b"[DUT3] [TST] from prefix\r\n"))
        self.assertEqual(rig.dut_logs(), [(3, "from prefix")])

    def test_unknown_text_type_falls_back_to_hint(self):
        """低 4 位≠1 的文本帧（形态未证实）退回 dut_hint() 兜底。"""
        rig = _Rig(hint=9)
        rig.client._feed(frame(0x45, b"[TST] odd stream\r\n"))
        self.assertEqual(rig.dut_logs(), [(9, "odd stream")])

    def test_channel1_and_cap_at_12(self):
        """CH1=0x01 可映射；超出 12 路（0xF1→16）不认，走兜底。"""
        rig = _Rig(hint=None)
        rig.client._feed(frame(0x01, b"[TST] ch1\r\n") + frame(0xF1, b"[TST] x\r\n"))
        # 0xF1 认不出且 hint=None → 系统级，不产生 dut 行
        self.assertEqual(rig.dut_logs(), [(1, "ch1")])

    def test_heartbeat_and_board_trace_produce_no_lines(self):
        """0x03 空心跳与 0xC1 板卡轨迹不是文本流，不产生行。"""
        rig = _Rig()
        rig.client._feed(frame(0x03, b"") * 3
                         + frame(0xC1, b"[2026/09/29 09:17:20] RemoteIo\r\n"))
        self.assertEqual(rig.dut_logs(), [])
        self.assertEqual([m for m in rig.sent if m["type"] == "log"], [])


class TestAssemblyAndSink(unittest.TestCase):
    def test_halfline_split_across_chunks_and_feed_boundary(self):
        """半行跨帧/跨 _feed 分包仍拼成一行并按流归因（TCP 分段任意切）。"""
        rig = _Rig()
        rig.client._feed(frame(0x41, b"[TST] par")
                         + frame(0x51, b"[TST] other ch6\r\n"))
        rig.client._feed(frame(0x41, b"tial line\r\n"))
        self.assertEqual(rig.dut_logs(),
                         [(6, "other ch6"), (5, "partial line")])

    def test_tagged_and_banner_lines_reach_sink_with_dut_prefix(self):
        """[TST]/[SYS]/[ERR]/横幅行归因后经 sink 落盘（[DUTx] 前缀格式，
        与 63001 行同格式）；无标签杂行通道已知也落 dutN.log（全部落盘）。"""
        rig = _Rig()
        rig.client._feed(
            frame(0x41, b"============\r\n")
            + frame(0x41, b"[TST] i2c_set_vol ret=0\r\n")
            + frame(0x41, b"[SYS] Emi_setting done\r\n")
            + frame(0x41, b"[ERR] WDT DDR reserve mode FAIL!\r\n")
            + frame(0x41, b"random noise no tag\r\n"))
        self.assertEqual(rig.sink, [
            "[DUT5] ============",
            "[DUT5] [TST] i2c_set_vol ret=0",
            "[DUT5] [SYS] Emi_setting done",
            "[DUT5] [ERR] WDT DDR reserve mode FAIL!",
            "[DUT5] random noise no tag",
        ])
        sys_lines = [m for m in rig.sent if m["type"] == "log"
                     and m.get("slot") is None]
        self.assertEqual(len(sys_lines), 1)  # 无标签杂行面板仍走系统级


class TestSystemSinkRouting(unittest.TestCase):
    """系统行落盘路由（2026-09-29 用户拍板"全部落盘"）。"""

    def _rig(self):
        hub = Hub()
        sent = []
        hub._broadcast = sent.append  # type: ignore[method-assign]
        sys_lines = []
        dut_sink = []
        client = BoardLogClient(hub, "192.168.50.100",
                                sink_write=dut_sink.append,
                                sink_write_system=sys_lines.append)
        client._dbg_frame = lambda ftype, payload: None
        return hub, sent, sys_lines, dut_sink, client

    def test_untagged_line_on_channel_sinks_to_dut(self):
        """无标签杂行但通道已知（0x41=CH5 流）→ dut5.log，不进 system。"""
        hub, sent, sysl, dutsink, client = self._rig()
        client._feed(frame(0x41, b"random noise no tag\r\n"))
        self.assertEqual(dutsink, ["[DUT5] random noise no tag"])
        self.assertEqual(sysl, [])

    def test_tagged_line_without_slot_to_system(self):
        """[TST] 行但归因不出通道（未知形态+无 hint）→ system.log 兜底不丢。"""
        hub, sent, sysl, dutsink, client = self._rig()
        client._feed(frame(0x45, b"[TST] orphan text\r\n"))
        self.assertEqual(sysl, ["[TST] orphan text"])
        self.assertEqual(dutsink, [])

    def test_board_trace_frames_to_system_not_hub(self):
        """0xC1 板卡轨迹 → 只落 system.log，不上 WS（防刷屏）。"""
        hub, sent, sysl, dutsink, client = self._rig()
        client._feed(frame(0xC1, b"[2026/09/29 09:17:20] RemoteIo line\r\n"))
        self.assertEqual(sysl, ["[2026/09/29 09:17:20] RemoteIo line"])
        self.assertEqual([m for m in sent if m["type"] == "log"], [])

    def test_log_begin_marker_channel_prefixed(self):
        """0xN0 通道 LOG BEGIN 标记帧 → [CHn] 前缀进 system.log。"""
        hub, sent, sysl, dutsink, client = self._rig()
        client._feed(frame(0x40, b"-------- LOG BEGIN  [Date:2026/09/29] --------\r\n"))
        self.assertEqual(sysl, ["[CH5] -------- LOG BEGIN  [Date:2026/09/29] --------"])

    def test_heartbeat_and_empty_not_sunk(self):
        hub, sent, sysl, dutsink, client = self._rig()
        client._feed(frame(0x03, b"") * 3 + frame(0x50, b""))
        self.assertEqual(sysl, [])

    def test_auto_system_sink_from_sink_write_owner(self):
        """只传 sink_write（main.py 现状）时系统行自动接 write_system——
        集成验证 boardlog→DutLogFileSink 全链（不改 WIP 中的 main.py）。
        用 0xC1 板卡轨迹触发（系统腿不需要会话）。"""
        from app.logchannel import DutLogFileSink
        hub = Hub()
        hub._broadcast = lambda m: None  # type: ignore[method-assign]
        with tempfile.TemporaryDirectory() as d:
            sink = DutLogFileSink()
            sink.set_dir(d)
            client = BoardLogClient(hub, "192.168.50.100",
                                    sink_write=sink.write)
            client._dbg_frame = lambda ftype, payload: None
            self.assertIsNotNone(client.sink_write_system)
            client._feed(frame(0xC1, b"[2026/09/29 10:00:00] RemoteIo line\r\n"))
            with open(os.path.join(d, sink._round_ts, "system.log"),
                      encoding="utf-8") as f:
                self.assertIn("RemoteIo line", f.read())
            sink.set_dir("")              # 关句柄，Windows 才能清临时目录


if __name__ == "__main__":
    unittest.main()
