"""串口直连会话单元测试（统一界面版 sites.mode=serial 的核心链路）。

覆盖：
- SerialDutSession：0x10 上线（hub 状态 IDLE + 自动 ACK 回写）、文本日志行拼装
  （cat=dut 入 hub.log + 订阅队列给 sequencer 落盘）、0x17 PASS、
  串口异常 → OFFLINE + _Offline 事件、send(StartTest) 线程安全写
- ConnectionManager serial 模式：SITE 1 仅 1 通道、类型为 SerialDutSession

运行：cd backend && python -m unittest tests.test_seriallink -v
（无需真实串口：monkeypatch serial.Serial 为 FakeSerial 双向管道）
"""

import asyncio
import struct
import sys
import threading
import time
import unittest

sys.path.insert(0, ".")
import serial as serial_mod                     # noqa: E402

from app.connection import ConnectionManager    # noqa: E402
from app.protocol import (HsgCodec, Ready,      # noqa: E402
                          StartTest, TestDone, build_frame)
from app.seriallink import SerialDutSession     # noqa: E402
from app.ws import Hub                          # noqa: E402


class _Chan:
    def __init__(self):
        self.buf = bytearray()
        self.cv = threading.Condition()

    def write(self, data):
        with self.cv:
            self.buf += data
            self.cv.notify_all()

    def read(self, n, timeout):
        with self.cv:
            if not self.buf:
                self.cv.wait(timeout)
            out = bytes(self.buf[:n])
            del self.buf[:n]
            return out


class FakeSerial:
    def __init__(self, to_dut, to_pc, **kw):
        self.to_dut, self.to_pc = to_dut, to_pc
        self.is_open = True
        for k, v in kw.items():
            setattr(self, k, v)

    def read(self, n):
        return self.to_pc.read(n, timeout=0.02)

    def write(self, data):
        self.to_dut.write(bytes(data))

    def close(self):
        self.is_open = False


def dut_frame(cmd, payload):
    return build_frame(0x01, cmd, payload)


READY = dut_frame(0x10, struct.pack("<HHHH", 0, 0, 0, 0) + b"M80-" + b"6785")


class TestSerialDutSession(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    def test_session_flow(self):
        to_dut, to_pc = _Chan(), _Chan()
        hub = Hub()
        orig = serial_mod.Serial
        serial_mod.Serial = lambda **kw: FakeSerial(to_dut, to_pc, **kw)

        async def main():
            sess = SerialDutSession(site=1, slot=1, port="FAKE",
                                    codec=HsgCodec(), hub=hub,
                                    cfg={"auto_ack": True})
            await sess.start()
            q = sess.subscribe()
            # ① DUT 上电发 0x10（分 8 字节一块到达，压力测流解析）
            for i in range(0, len(READY), 8):
                to_pc.write(READY[i:i + 8])
            await asyncio.sleep(0.3)
            # ② 文本日志两行半 → 行拼装
            to_pc.write(b"[HSG] preloader ready\r\n[MR CHK] ch0 ok\r\nhalf line")
            await asyncio.sleep(0.3)
            # ③ 0x17 PASS
            to_pc.write(dut_frame(0x17, bytes([0, 0])))
            await asyncio.sleep(0.3)
            # close() 会置 OFFLINE（后端停机的正确语义），先捕获断言数据
            st = dict(hub.states[(1, 1)])
            msgs = []
            while not q.empty():
                msgs.append(q.get_nowait())
            ack = bytes(to_dut.buf[:9])
            return sess, st, msgs, ack

        try:
            sess, st, msgs, ack = self._run(main())
        finally:
            serial_mod.Serial = orig
            asyncio.run(sess.close())

        # 上线：hub 状态 + 自动 ACK 已回写 DUT 侧
        self.assertTrue(st["connected"])
        self.assertEqual(st["state"], "IDLE")
        self.assertEqual(sess.version, "M80-_6785")
        self.assertEqual(ack, bytes.fromhex("AF020000 1000 0055EF".replace(" ", "")))
        # 文本行 + 半行冲刷 + PASS 均入订阅队列（sequencer 落盘数据源）
        kinds = [type(m).__name__ for m in msgs]
        self.assertIn("DutLog", kinds)
        self.assertIn("TestDone", kinds)
        done = [m for m in msgs if isinstance(m, TestDone)][0]
        self.assertEqual(done.result, "PASS")
        logs = [m.msg for m in msgs if type(m).__name__ == "DutLog"]
        self.assertTrue(any("[HSG] preloader ready" in x for x in logs))
        self.assertTrue(any("half line" in x for x in logs))  # 帧边界冲刷半行

    def test_link_dead_marks_offline_and_signals_test(self):
        to_dut, to_pc = _Chan(), _Chan()
        hub = Hub()

        class ExplodingSerial(FakeSerial):
            def read(self, n):
                raise serial_mod.SerialException("device unplugged")

        orig = serial_mod.Serial
        serial_mod.Serial = lambda **kw: ExplodingSerial(to_dut, to_pc, **kw)

        async def main():
            sess = SerialDutSession(1, 1, "FAKE", HsgCodec(), hub, {})
            await sess.start()
            # 人为置为 TESTING（模拟 sequencer 已启动）
            hub.update(1, 1, connected=True, state="TESTING")
            sess.connected = True
            q = sess.subscribe()
            await asyncio.sleep(0.3)     # reader 线程立刻撞异常 → _on_link_dead
            return sess, q

        try:
            sess, q = self._run(main())
        finally:
            serial_mod.Serial = orig
            asyncio.run(sess.close())

        st = hub.states[(1, 1)]
        self.assertFalse(st["connected"])
        self.assertEqual(st["state"], "OFFLINE")
        from app.seriallink import _Offline
        self.assertEqual(type(q.get_nowait()).__name__, "_Offline")

    def test_send_starttest_writes_wire_frame(self):
        to_dut, to_pc = _Chan(), _Chan()
        hub = Hub()
        orig = serial_mod.Serial
        serial_mod.Serial = lambda **kw: FakeSerial(to_dut, to_pc, **kw)

        async def main():
            sess = SerialDutSession(1, 1, "FAKE", HsgCodec(), hub, {})
            await sess.start()
            sess.send(StartTest(cfg="LOG_TO_UART1=1\n"))
            await asyncio.sleep(0.05)
            return sess

        try:
            sess = self._run(main())
        finally:
            serial_mod.Serial = orig
            asyncio.run(sess.close())

        wire = bytes(to_dut.buf[:7 + 15])
        self.assertEqual(wire[:5], bytes([0xAF, 15, 0, 0x00, 0x15]))
        self.assertEqual(wire[-1], 0xEF)


class TestSerialModeManager(unittest.TestCase):

    def test_serial_mode_single_channel(self):
        cfg = {"sites": {"mode": "serial"}, "serial_dut": {"port": "auto"},
               "dut": {}}
        hub = Hub()
        cm = ConnectionManager(cfg, hub, HsgCodec())
        self.assertEqual(list(cm.sessions.keys()), [(1, 1)])
        self.assertIsInstance(cm.sessions[(1, 1)], SerialDutSession)
        self.assertEqual(hub.site_ids, [1])

    def test_mock_mode_untouched(self):
        cfg = {"sites": {"count": 1, "mode": "mock", "mock_port_base": 40000},
               "dut": {}}
        hub = Hub()
        cm = ConnectionManager(cfg, hub, HsgCodec())
        self.assertEqual(len(cm.sessions), 24)     # 1 SITE × 24 通道（UDP 不变）
        self.assertNotIsInstance(cm.sessions[(1, 1)], SerialDutSession)


if __name__ == "__main__":
    unittest.main(verbosity=2)
