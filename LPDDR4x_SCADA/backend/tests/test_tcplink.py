"""TCP 直连会话端到端测试（sites.mode=tcp 核心链路，无需真实设备）。

用真 asyncio TCP 服务器扮演 DUT 固件（行为按 hsg_device_protocol.c）：
  ① 连上后发 0x10 READY（阻塞等 ACK，2s 重发，最多 3 轮）
  ② 收 0x15 cfg（读到 0xEF 尾，扫描校验）→ 回 ACK
  ③ 发文本横幅 + 0x11 容量 + 0x18 进度 + 0x17 PASS（混合流，7B 一块打散）
  ④ 客户端断开后重连，再走一遍 0x10 → 验证自动重连恢复

运行：cd backend && python -m unittest tests.test_tcplink -v
"""

import asyncio
import struct
import sys
import unittest

sys.path.insert(0, ".")

from app.connection import ConnectionManager         # noqa: E402
from app.protocol import (HsgCodec, Ready,           # noqa: E402
                          StartTest, TestDone, build_frame)
from app.tcplink import TcpDutSession                # noqa: E402
from app.ws import Hub                               # noqa: E402

READY = build_frame(0x01, 0x10, struct.pack("<HHHH", 0, 0, 0, 0)
                    + b"M80-" + b"6785")


async def _recv_frame(reader: asyncio.StreamReader, timeout=3.0) -> bytes:
    """固件式收包：读到 0xEF 尾即止，缓冲内扫 0xAF 帧"""
    buf = bytearray()
    while True:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout)
        if not chunk:
            raise ConnectionResetError
        buf += chunk
        t = buf.find(0xEF)
        if t < 0:
            continue
        part = bytes(buf[:t + 1])
        i = part.find(0xAF)
        while i >= 0:
            if i + 3 <= len(part):
                plen = part[i + 1] | (part[i + 2] << 8)
                if i + plen + 7 <= len(part):
                    cand = part[i:i + plen + 7]
                    if cand[-1] == 0xEF:
                        return cand
            i = part.find(0xAF, i + 1)
        buf = bytearray(buf[t + 1:])


class _FakeDut:
    """DUT 固件行为模拟器（TCP 服务端）"""

    def __init__(self, results: dict):
        self.results = results
        self.server: asyncio.AbstractServer | None = None
        self.port = 0
        self._writers: list = []

    async def start(self, host="127.0.0.1", port=0):
        self.server = await asyncio.start_server(self._serve, host, port)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def close(self):
        """先踹掉全部连接再关监听（wait_closed 会等存量连接结束）"""
        for w in list(self._writers):
            try:
                w.close()
            except Exception:
                pass
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    def kick(self):
        """模拟设备断电/网线拔出：服务端主动断开全部连接（监听保留）"""
        for w in list(self._writers):
            try:
                w.transport.abort()
            except Exception:
                pass

    async def _serve(self, reader, writer):
        cfg = None
        self._writers.append(writer)
        try:
            # ① 0x10 等 ACK（重试 3 轮）
            for attempt in range(3):
                writer.write(READY)
                await writer.drain()
                try:
                    f = await _recv_frame(reader, timeout=2.0)
                except asyncio.TimeoutError:
                    continue
                if f[3] == 0x00 and f[4] == 0x10 and len(f) == 9:
                    self.results["ack_after_tries"] = attempt + 1
                    break
            else:
                self.results["error"] = "DUT 未等到 0x10 ACK"
                return
            # ② 等 0x15
            while cfg is None:
                f = await _recv_frame(reader, timeout=5.0)
                if f[4] == 0x15:
                    cfg = f[5:-2]
            self.results["cfg_received"] = cfg.decode()
            writer.write(build_frame(0x01, 0x15, bytes([0, 0])))
            # ③ 混合流（7B 打散）
            stream = (b"\r\n[HSG] preloader ready\r\n"
                      + build_frame(0x01, 0x11, bytes([16, 8, 4, 8, 4]))
                      + b"[HSG] config received\r\n"
                      + build_frame(0x01, 0x18, bytes([1, 0])
                                    + b'{"step":"complex_test","stage":"PL",'
                                      b'"progress":50,"durationSec":10,'
                                      b'"countdownSec":10}')
                      + build_frame(0x01, 0x17, bytes([0, 0])))
            for i in range(0, len(stream), 7):
                writer.write(stream[i:i + 7])
                await writer.drain()
            self.results["done"] = True
            await writer.wait_closed()
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            try:
                self._writers.remove(writer)
            except ValueError:
                pass
            writer.close()


class TestTcpSession(unittest.TestCase):

    def test_full_session_and_reconnect(self):
        results: dict = {}
        hub = Hub()

        async def main():
            dut = await _FakeDut(results).start()
            sess = TcpDutSession(site=1, slot=1, host="127.0.0.1",
                                 port=dut.port, codec=HsgCodec(), hub=hub,
                                 cfg={"retry_sec": 0.3})
            await sess.start()
            q = sess.subscribe()
            # DUT 上线后下发 0x15
            cfg_sent = False
            for _ in range(100):                       # 最长 ~5s
                await asyncio.sleep(0.05)
                if not cfg_sent and sess.connected:
                    sess.send(StartTest(cfg="LOG_TO_UART1=1\nPatternTest=1\n"))
                    cfg_sent = True
                if any(type(m).__name__ == "TestDone" for m in _drain(q)):
                    break
            self.assertTrue(cfg_sent, "未触发 0x15 下发")
            self.assertTrue(results.get("done"), f"DUT 模拟未完成: {results}")
            self.assertEqual(results.get("cfg_received"),
                             "LOG_TO_UART1=1\nPatternTest=1\n")
            st = dict(hub.states[(1, 1)])
            # 断线重连：服务端踹掉连接 → 会话 OFFLINE → 监听仍在 → 自动重连 → 再次上线
            dut.kick()
            for _ in range(40):
                await asyncio.sleep(0.1)
                if hub.states[(1, 1)]["state"] == "OFFLINE":
                    break
            self.assertEqual(hub.states[(1, 1)]["state"], "OFFLINE")
            for _ in range(60):
                await asyncio.sleep(0.1)
                if hub.states[(1, 1)]["connected"]:
                    break
            self.assertTrue(hub.states[(1, 1)]["connected"], "重连后未重新上线")
            self.assertTrue(results.get("ack_after_tries", 0) >= 1)
            await sess.close()
            await dut.close()
            return st

        st = asyncio.run(main())
        self.assertTrue(st["connected"])
        self.assertEqual(st["state"], "IDLE")

    def test_manager_tcp_mode(self):
        cfg = {"sites": {"mode": "tcp"},
               "tcp_dut": {"channels": [
                   {"site": 1, "slot": 1, "host": "10.0.0.5", "port": 8001},
                   {"site": 1, "slot": 2, "host": "10.0.0.5", "port": 8002}]}}
        hub = Hub()
        cm = ConnectionManager(cfg, hub, HsgCodec())
        self.assertEqual(sorted(cm.sessions.keys()), [(1, 1), (1, 2)])
        self.assertIsInstance(cm.sessions[(1, 2)], TcpDutSession)
        self.assertEqual(hub.site_ids, [1])

    def test_manager_tcp_mode_empty_channels(self):
        cfg = {"sites": {"mode": "tcp"}, "tcp_dut": {"channels": []}}
        with self.assertRaises(ValueError):
            ConnectionManager(cfg, Hub(), HsgCodec())


def _drain(q: asyncio.Queue):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


if __name__ == "__main__":
    unittest.main(verbosity=2)
