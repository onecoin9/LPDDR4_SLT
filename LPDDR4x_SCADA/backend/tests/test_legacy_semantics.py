"""旧 C# 上位机在线监测逻辑对齐测试（2026-09-07 用户指令）。

对齐项（来源：LPDDR4x_SLT_Standard DutMaster.StateMachine.cs /
DutsManager.StateMachine.cs 的权威语义）：
  ① 0x15 配置每 5s（cfg_resend_sec）重发，收到 DUT 的 0x15 ACK 才停
     （DoActionSendStartConfig: StartRetryTimer(5000, EVT_SND_CONFIG)）
  ② 测试中收到 0x10 READY = DUT 重启 → FAIL(dut_reboot 0xFE)
     （DoActionRecvDutRebootReady: FAIL2 + SCODE_DUT_REBOOT）
  ③ Ack 入订阅队列（sequencer 停止重发的依据）

运行：cd backend && python -m unittest tests.test_legacy_semantics -v
"""

import asyncio
import struct
import sys
import unittest

sys.path.insert(0, ".")

from app.connection import ConnectionManager, _DutReboot     # noqa: E402
from app.protocol import (Ack, HsgCodec, Ready,              # noqa: E402
                          StartTest, TestDone, build_frame)
from app.recorder import Recorder                            # noqa: E402
from app.sequencer import Sequencer                          # noqa: E402
from app.seriallink import BaseStreamSession                 # noqa: E402
from app.ws import Hub                                       # noqa: E402

READY = build_frame(0x01, 0x10, struct.pack("<HHHH", 0, 0, 0, 0)
                    + b"M80-" + b"6785")


class _FakeRecorder:
    """Recorder 替身：记录 _finish 写入的结果行"""

    def __init__(self):
        self.results = []

    def start_run(self, site, slot, batch):
        class _W:
            def __init__(s2): s2.lines = []
            def write_log(s2, level, msg): pass
            def close(s2, note=""): pass
        return _W()

    def append_result(self, batch, site, slot, result, fail_item, duration):
        self.results.append((result, fail_item))


class _FakeSession:
    """DutSession 替身：记录 send 调用，支持外部往订阅队列塞事件"""

    def __init__(self):
        self.site, self.slot = 1, 1
        self.sent = []
        self.connected = True

    def send(self, msg):
        self.sent.append(type(msg).__name__)

    def subscribe(self):
        return asyncio.Queue()

    def unsubscribe(self, q):
        pass


class TestCfgResend(unittest.TestCase):
    """① 0x15 重发直到 ACK"""

    def test_resend_loop_body(self):
        """重发循环本体：按间隔重发，ACK 置位后停止"""
        async def loop_test():
            fs = _FakeSession()
            acked = asyncio.Event()
            seq = Sequencer({"dut": {"cfg_resend_sec": 0.05}}, None, Hub(),
                            _FakeRecorder())
            t = asyncio.create_task(seq._resend_cfg_loop(fs, "A=1\n", acked))
            await asyncio.sleep(0.28)            # 0.05 间隔 → 至少 3 次重发（防抖留裕量）
            self.assertGreaterEqual(fs.sent.count("StartTest"), 3)
            acked.set()
            await asyncio.sleep(0.08)
            n = fs.sent.count("StartTest")
            await asyncio.sleep(0.08)
            self.assertEqual(fs.sent.count("StartTest"), n, "ACK 后仍在重发")
            t.cancel()

        asyncio.run(loop_test())

    def test_run_test_stops_resend_on_ack(self):
        """完整 _run_test：DUT 回 0x15 ACK → 重发停止 → 0x17 PASS 收尾"""
        async def main():
            hub = Hub()
            conns = ConnectionManager({"sites": {"mode": "mock", "count": 1},
                                       "dut": {}}, hub, HsgCodec())
            fs = _FakeSession()
            queues = []

            def subscribe():
                q = asyncio.Queue()
                queues.append(q)
                return q
            fs.subscribe = subscribe
            conns.sessions[(1, 1)] = fs
            rec = _FakeRecorder()
            seq = Sequencer({"dut": {"cfg_resend_sec": 0.05,
                                     "test_timeout_sec": 10, "log_drain_sec": 0}}, conns, hub, rec)
            task = asyncio.create_task(seq._run_test(1, 1, "B", seq.cfg_text, ["PL"]))
            # 等 subscribe 发生
            for _ in range(100):
                if queues:
                    break
                await asyncio.sleep(0.02)
            q = queues[0]
            await asyncio.sleep(0.03)            # 有 1 次首发 + 可能 1 次重发前
            q.put_nowait(Ack(cmd=0x15, status=0))     # DUT 确认
            await asyncio.sleep(0.15)            # 若未停早已再发 2+ 次
            q.put_nowait(TestDone(result="PASS"))
            await asyncio.sleep(0.3)
            self.assertFalse(task.done() and task.exception(),
                             f"任务异常: {task.exception() if task.done() else None}")
            # 首发 + 至多重发 1 次（0.05s 间隔，ACK 在 ~0.05s 到达）
            self.assertLessEqual(fs.sent.count("StartTest"), 2,
                                 f"ACK 后未停止重发: {fs.sent}")
            self.assertEqual(rec.results[-1][0], "PASS")
        asyncio.run(main())


class TestDutReboot(unittest.TestCase):
    """② 测试中 0x10 → FAIL(dut_reboot)（会话层推 _DutReboot，sequencer 收尾）"""

    def _session(self):
        class _S(BaseStreamSession):
            def _send_bytes(self, frame):
                pass
        return _S(1, 1, HsgCodec(), Hub(), {"auto_ack": False})

    def test_session_pushes_reboot_when_testing(self):
        s = self._session()
        s.hub.update(1, 1, connected=True, state="TESTING")
        q = s.subscribe()
        s._on_frame(READY)
        # 事件经 _schedule 直调入 loop——在无 loop 的测试里手动调度不了，
        # 直接调 _dispatch 验证（_on_frame 的解析/ACK 决策另有测试覆盖）
        from app.protocol import Ready as _R
        msg = s.codec.decode(READY)
        s._dispatch(msg)
        self.assertEqual(type(q.get_nowait()).__name__, "_DutReboot")

    def test_session_normal_online_when_idle(self):
        s = self._session()
        q = s.subscribe()
        s._dispatch(s.codec.decode(READY))
        self.assertTrue(s.connected)
        self.assertTrue(q.empty())               # 不产生重启事件

    def test_run_test_converts_reboot_to_fail(self):
        async def main():
            hub = Hub()
            conns = ConnectionManager({"sites": {"mode": "mock", "count": 1},
                                       "dut": {}}, hub, HsgCodec())
            fs = _FakeSession()
            queues = []
            fs.subscribe = lambda: (queues.append(asyncio.Queue())
                                    or queues[-1])
            conns.sessions[(1, 1)] = fs
            rec = _FakeRecorder()
            seq = Sequencer({"dut": {"test_timeout_sec": 10, "log_drain_sec": 0}}, conns, hub, rec)
            task = asyncio.create_task(seq._run_test(1, 1, "B", seq.cfg_text, ["PL"]))
            for _ in range(100):
                if queues:
                    break
                await asyncio.sleep(0.02)
            queues[0].put_nowait(_DutReboot())
            await asyncio.sleep(0.2)
            self.assertEqual(rec.results[-1], ("FAIL", "dut_reboot"))
            hub.update(1, 1, state="TESTING")    # _finish 已置 FAIL，此处只防误挂
            task.cancel() if not task.done() else None
        asyncio.run(main())


class TestAckQueued(unittest.TestCase):
    """③ Ack 入订阅队列"""

    def test_udp_session_queues_ack(self):
        from app.connection import DutSession
        hub = Hub()
        sess = DutSession(site=1, slot=1, board="A", remote_ip="127.0.0.1",
                          remote_port=40001, local_port=21001,
                          codec=HsgCodec(), hub=hub, cfg={})
        q = sess.subscribe()
        sess._on_data(build_frame(0x01, 0x15, bytes([0, 0])))
        evt = q.get_nowait()
        self.assertIsInstance(evt, Ack)
        self.assertEqual(evt.cmd, 0x15)


if __name__ == "__main__":
    unittest.main(verbosity=2)
