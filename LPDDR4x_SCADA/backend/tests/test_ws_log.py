"""Hub.log 的 cat 分类：缺省推导（system/dut）+ 显式 conn 透传。"""

import sys
import types
import unittest

# 本机 managed python 无 fastapi；app.ws 仅把 WebSocket 用作类型标注，打桩即可
try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    _stub = types.ModuleType("fastapi")
    _stub.WebSocket = object  # type: ignore[attr-defined]
    sys.modules["fastapi"] = _stub

from app.ws import Hub


class TestLogCat(unittest.TestCase):
    def _capture(self):
        hub = Hub()
        sent = []
        hub._broadcast = sent.append  # type: ignore[method-assign]
        return hub, sent

    def test_channel_log_defaults_dut(self):
        hub, sent = self._capture()
        hub.log(1, 7, "INFO", "CH07 命令确认 ACK 0x15 status=0")
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["type"], "log")
        self.assertEqual(sent[0]["cat"], "dut")
        self.assertEqual(sent[0]["site"], 1)
        self.assertEqual(sent[0]["slot"], 7)

    def test_syslog_defaults_system_and_site_null(self):
        hub, sent = self._capture()
        hub.syslog("WARN", "没有测试中的通道")
        self.assertEqual(sent[0]["cat"], "system")
        self.assertIsNone(sent[0]["site"])
        self.assertIsNone(sent[0]["slot"])

    def test_explicit_conn_cat(self):
        hub, sent = self._capture()
        hub.log(1, 3, "INFO", "CH03 上线 · 版本 K85V1", cat="conn")
        self.assertEqual(sent[0]["cat"], "conn")
        # conn 是通道级事件：site/slot 照常带上
        self.assertEqual(sent[0]["site"], 1)
        self.assertEqual(sent[0]["slot"], 3)


class TestManualState(unittest.TestCase):
    """manual_state 推送契约（2026-10-10 事件驱动）：Hub 只负责加 type 并
    立即广播，载荷由 main.py 组装（mdbg.info + runner.snapshot）。"""

    def _capture(self):
        hub = Hub()
        sent = []
        hub._broadcast = sent.append  # type: ignore[method-assign]
        return hub, sent

    def test_manual_state_broadcast(self):
        hub, sent = self._capture()
        hub.manual_state({"enabled": True,
                          "duts": [{"dut": 1, "line": 0, "channel": 5,
                                    "powerOn": True}],
                          "run": {"mode": "full_run", "duts": [
                              {"dut": 1, "channel": 5, "state": "running",
                               "detail": "", "sinceSec": 12,
                               "enteredAt": 1760123456.78}]}})
        self.assertEqual(len(sent), 1)
        m = sent[0]
        self.assertEqual(m["type"], "manual_state")
        self.assertTrue(m["enabled"])
        self.assertEqual(m["duts"][0]["powerOn"], True)
        self.assertEqual(m["run"]["duts"][0]["state"], "running")
        self.assertEqual(m["run"]["duts"][0]["enteredAt"], 1760123456.78)

    def test_manual_state_no_clients_no_crash(self):
        """无客户端 / 非事件循环上下文（REST to_thread 工作线程）也安全静默"""
        Hub().manual_state({"enabled": False, "duts": [],
                            "run": {"mode": "power_only", "duts": []}})


if __name__ == "__main__":
    unittest.main()
