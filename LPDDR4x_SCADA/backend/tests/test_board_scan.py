"""常驻板卡扫描记账测试（旧 HsgBroadcast 语义 + 用户要求的静默/新板才 log 规则）。

旧码事实（HsgCBCProtocol.cs HsgBroadcast）：
  - Timer(3000, 5000)：每 5s 广播一轮；板 IP 进 _detectedAddrList 后粘性常驻，
    不自动判离线（ClearReadyState 手动清）
对应本实现（controlplane.scan_once）：返回本轮**新发现**的板（每板只返回一次），
已知板静默刷新 last_seen；掉线无事件。
"""

import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, ".")

from app import commboard                              # noqa: E402
from app.controlplane import ControlPlane              # noqa: E402

CFG = {"commboard": {"enabled": True,
                     "boards": [{"site": 1, "board": "A", "host": "192.168.50.100"}]}}


def _fake_discover(devs):
    def _d(timeout=3.0, **kw):
        return devs
    return _d


class TestScanBookkeeping(unittest.TestCase):

    def _cp(self):
        return ControlPlane(CFG)

    def test_new_board_returned_once(self):
        cp = self._cp()
        d1 = [{"device_id": 7, "serial": 1, "addr": "192.168.50.101"}]
        with mock.patch.object(commboard, "discover", _fake_discover(d1)):
            fresh1 = cp.scan_once()
            fresh2 = cp.scan_once()
        self.assertEqual(len(fresh1), 1)               # 新板：返回一次
        self.assertEqual(fresh1[0]["addr"], "192.168.50.101")
        self.assertEqual(fresh2, [])                   # 同板再扫：静默
        boards = cp.scanned_boards()
        self.assertEqual(len(boards), 1)
        self.assertGreaterEqual(boards[0]["last_seen"], boards[0]["first_seen"])

    def test_late_board_and_mixed(self):
        cp = self._cp()
        first = [{"device_id": 1, "serial": 1, "addr": "10.0.0.1"},
                 {"device_id": 2, "serial": 1, "addr": "10.0.0.2"}]
        later = first + [{"device_id": 3, "serial": 1, "addr": "10.0.0.3"}]
        with mock.patch.object(commboard, "discover", _fake_discover(first)):
            fresh = cp.scan_once()
        self.assertEqual({b["addr"] for b in fresh}, {"10.0.0.1", "10.0.0.2"})
        with mock.patch.object(commboard, "discover", _fake_discover(later)):
            fresh = cp.scan_once()
        self.assertEqual([b["addr"] for b in fresh], ["10.0.0.3"])   # 只有新板
        self.assertEqual(len(cp.scanned_boards()), 3)

    def test_board_offline_is_sticky(self):
        """旧逻辑：板不再应答也留在在线表（粘性），无事件"""
        cp = self._cp()
        with mock.patch.object(commboard, "discover",
                               _fake_discover([{"device_id": 1, "serial": 1,
                                                "addr": "10.0.0.1"}])):
            cp.scan_once()
        with mock.patch.object(commboard, "discover", _fake_discover([])):
            fresh = cp.scan_once()
        self.assertEqual(fresh, [])
        self.assertEqual(len(cp.scanned_boards()), 1)  # 仍在表

    def test_network_error_silent(self):
        cp = self._cp()

        def boom(timeout=3.0):
            raise OSError("network unreachable")
        with mock.patch.object(commboard, "discover", boom):
            self.assertEqual(cp.scan_once(), [])        # 静默不抛

    def test_disabled_raises(self):
        cp = ControlPlane({"commboard": {"enabled": False}})
        from app.controlplane import ControlPlaneError
        with self.assertRaises(ControlPlaneError):
            cp.scan_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
