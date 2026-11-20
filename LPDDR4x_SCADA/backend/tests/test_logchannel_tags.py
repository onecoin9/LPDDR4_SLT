# -*- coding: utf-8 -*-
"""logchannel 行首分类标签 [SYS]/[TST]/[ERR] 解析（HSG-LOG 2026-09-16）。

契约：DUT 文本行行首标签由固件输出层（PL print.c / LK debug.c /
memtest.sh mlog / memtester mt_printf）打上，通讯板纯透传；
上位机按标签分 cat：SYS→sys（主控板系统运行日志，与上位机自身 system 分开），
TST/ERR→dut（ERR 强制 level=ERROR）；无标签行保持旧行为。
"""

import sys
import types
import unittest

try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    _stub = types.ModuleType("fastapi")
    _stub.WebSocket = object  # type: ignore[attr-defined]
    sys.modules["fastapi"] = _stub

# app.logchannel → app.connection → app.seriallink 依赖 pyserial；
# managed python 无此包，打桩即可（本测试不触串口功能）
try:
    import serial  # noqa: F401
except ModuleNotFoundError:
    _serial = types.ModuleType("serial")
    _serial.Serial = object  # type: ignore[attr-defined]
    _serial.SerialException = Exception  # type: ignore[attr-defined]
    _tools = types.ModuleType("serial.tools")
    _lp = types.ModuleType("serial.tools.list_ports")
    _lp.comports = lambda: []  # type: ignore[attr-defined]
    _tools.list_ports = _lp  # type: ignore[attr-defined]
    _serial.tools = _tools  # type: ignore[attr-defined]
    sys.modules["serial"] = _serial
    sys.modules["serial.tools"] = _tools
    sys.modules["serial.tools.list_ports"] = _lp

from app.logchannel import LogChannel


class _Hub:
    def __init__(self):
        self.logs = []

    def log(self, site, slot, level, msg, cat=None):
        self.logs.append(dict(site=site, slot=slot, level=level,
                              cat=cat, msg=msg))

    def syslog(self, level, msg):
        self.logs.append(dict(site=None, slot=None, level=level,
                              cat="system", msg=msg))


class _Conns:
    sessions = {(1, 1): object(), (2, 12): object()}


def _feed(lc, text):
    lc.datagram_received(text.encode("utf-8"), ("127.0.0.1", 40000))


class TestClsTags(unittest.TestCase):
    def setUp(self):
        self.hub = _Hub()
        self.lc = LogChannel(self.hub, _Conns())

    def test_sys_tag_routes_to_sys_cat(self):
        _feed(self.lc, "[DUT1] [SYS] EMI setting done\n")
        self.assertEqual(len(self.hub.logs), 1)
        e = self.hub.logs[0]
        self.assertEqual(e["cat"], "sys")
        self.assertEqual(e["level"], "INFO")
        self.assertEqual(e["site"], 1)
        self.assertEqual(e["slot"], 1)
        self.assertEqual(e["msg"], "CH01 EMI setting done")

    def test_err_tag_forces_error_level(self):
        _feed(self.lc, "[S2DUT12] [ERR] [MEMTEST] *** FAIL DETECTED ***\n")
        e = self.hub.logs[0]
        self.assertEqual(e["cat"], "dut")
        self.assertEqual(e["level"], "ERROR")
        self.assertEqual(e["site"], 2)
        self.assertEqual(e["slot"], 12)
        self.assertNotIn("[ERR]", e["msg"])

    def test_tst_tag_stays_dut_info(self):
        _feed(self.lc, "[DUT1] [TST] Test time 60 s\n")
        e = self.hub.logs[0]
        self.assertEqual(e["cat"], "dut")
        self.assertEqual(e["level"], "INFO")
        self.assertEqual(e["msg"], "CH01 Test time 60 s")

    def test_tst_with_fail_keyword_still_error(self):
        # 标签只定分类，级别关键词推导不丢（双保险）
        _feed(self.lc, "[DUT1] [TST] loop 3 result: FAIL item 2\n")
        e = self.hub.logs[0]
        self.assertEqual(e["cat"], "dut")
        self.assertEqual(e["level"], "ERROR")

    def test_untagged_legacy_line_unchanged(self):
        _feed(self.lc, "[DUT1] hello world\n")
        e = self.hub.logs[0]
        self.assertEqual(e["cat"], "dut")
        self.assertEqual(e["level"], "INFO")
        self.assertEqual(e["msg"], "CH01 hello world")

    def test_unroutable_sys_tag(self):
        # 无 [DUTn] 前缀但带 [SYS]：仍按 sys 分类
        _feed(self.lc, "[SYS] board-wide notice\n")
        e = self.hub.logs[0]
        self.assertEqual(e["cat"], "sys")
        self.assertIsNone(e["site"])
        self.assertIn("board-wide notice", e["msg"])


if __name__ == "__main__":
    unittest.main()
