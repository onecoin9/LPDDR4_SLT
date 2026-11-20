"""HandlerService 单元测试：协议分发 + testend 聚合 + 真实 TCP 回环。

运行：cd backend && python -m unittest discover -s tests -v
协议基准：旧上位机 HCProtocol.Json.cs / BSController.stateMachine.cs
（bibid=测试组=SITE，siteid=组内 DUT=slot，结果 0/1/2）。
"""

import asyncio
import json
import sys
import unittest

sys.path.insert(0, ".")


class _Hub:
    """最小 Hub 替身：site_ids + syslog 收集"""

    def __init__(self, site_ids=(1, 2)):
        self.site_ids = list(site_ids)
        self.logs = []

    def syslog(self, level, msg):
        self.logs.append(f"{level}: {msg}")


def make_service(started_stub=None):
    from app.handler import HandlerService
    hub = _Hub()

    async def start_test(targets, batch):
        return started_stub if started_stub is not None else list(targets)

    return HandlerService(
        {"handler": {"enabled": True, "rx_port": 0, "tx_host": "", "tx_port": 0}},
        hub, start_test, lambda site: "1" * 24, lambda: "WO-T"), hub


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class TestStatusText(unittest.TestCase):
    def test_extended_codes(self):
        from app.protocol import _status_name
        self.assertEqual(_status_name(0x02), "signal_fail")
        self.assertEqual(_status_name(0x03), "density_check_fail")
        self.assertEqual(_status_name(0x01), "addr_scan_fail")
        self.assertEqual(_status_name(0x05), "temp_abnormal")
        self.assertEqual(_status_name(0x06), "timeout")
        self.assertEqual(_status_name(0xFC), "aging_log_fail")
        self.assertEqual(_status_name(0xFD), "dut_conn_timeout")
        self.assertEqual(_status_name(0xFE), "dut_reboot")
        self.assertEqual(_status_name(0x42), "status_0x0042")


class TestDispatch(unittest.TestCase):
    def _dispatch(self, svc, hub, obj):
        return json.loads(run(svc._dispatch(json.dumps(obj).encode())).decode())

    def test_getversion(self):
        svc, hub = make_service()
        r = self._dispatch(svc, hub, {"method": "getversion", "data": {}})
        self.assertEqual((r["method"], r["status"]), ("getversion", "success"))
        self.assertIn("version", r["data"])

    def test_lotstart_selfcheck_setenable_bitstring(self):
        svc, hub = make_service()
        r = self._dispatch(svc, hub, {"method": "lotstart", "data": {
            "lotid": "L9", "productid": "P", "recipe": "R", "selfcheck": True}})
        self.assertEqual(r["status"], "success")
        en = r["data"]["setenable"]
        self.assertEqual([e["bibid"] for e in en], [1, 2])
        self.assertEqual(en[0]["enable"], "1" * 24)     # 位串：每字符一个 DUT
        self.assertEqual(svc.lot_info["lotid"], "L9")

    def test_lotend_clears_lot(self):
        svc, hub = make_service()
        self._dispatch(svc, hub, {"method": "lotstart", "data": {"lotid": "L9"}})
        r = self._dispatch(svc, hub, {"method": "lotend", "data": {}})
        self.assertEqual(r["status"], "success")
        self.assertEqual(svc.lot_info, {})

    def test_teststart_maps_bibid_to_site(self):
        svc, hub = make_service()
        r = self._dispatch(svc, hub, {"method": "teststart", "data": {
            "bibid": 2, "sites": [{"siteid": 1, "IsEnable": True},
                                   {"siteid": 2, "IsEnable": False},
                                   {"siteid": 5, "IsEnable": True}]}})
        self.assertEqual(r["status"], "success")
        self.assertEqual(svc._pending[2], {1, 5})        # 只有使能通道进聚合

    def test_teststart_invalid_bibid(self):
        svc, hub = make_service()
        r = self._dispatch(svc, hub, {"method": "teststart", "data": {
            "bibid": 99, "sites": [{"siteid": 1, "IsEnable": True}]}})
        self.assertEqual(r["status"], "fail")

    def test_unsupported_method(self):
        svc, hub = make_service()
        r = self._dispatch(svc, hub, {"method": "frobnicate", "data": {}})
        self.assertEqual(r["status"], "fail")

    def test_bad_json(self):
        svc, hub = make_service()
        r = json.loads(run(svc._dispatch(b"not json")).decode())
        self.assertEqual(r["status"], "fail")


class TestAggregation(unittest.TestCase):
    def test_collect_all_then_testend(self):
        svc, hub = make_service()
        run(svc._dispatch(json.dumps({"method": "teststart", "data": {
            "bibid": 1, "sites": [{"siteid": s, "IsEnable": True} for s in (1, 2, 3)]}
        }).encode()))
        svc.notify_result(1, 2, "PASS")
        svc.notify_result(1, 3, "FAIL")
        self.assertEqual(svc._tx_queue.qsize(), 0)       # 未集齐不上报
        svc.notify_result(1, 1, "CANCEL")               # 手动停止 → 0
        self.assertEqual(svc._tx_queue.qsize(), 1)
        method, payload = svc._tx_queue.get_nowait()
        self.assertEqual(method, "testend")
        self.assertEqual(payload["bibid"], 1)
        self.assertEqual(payload["sites"], [
            {"siteid": 1, "result": 0}, {"siteid": 2, "result": 1},
            {"siteid": 3, "result": 2}])
        self.assertNotIn(1, svc._pending)               # 已清理

    def test_unrelated_result_ignored(self):
        svc, hub = make_service()
        run(svc._dispatch(json.dumps({"method": "teststart", "data": {
            "bibid": 1, "sites": [{"siteid": 1, "IsEnable": True}]}}).encode()))
        svc.notify_result(2, 1, "PASS")                 # 别的 site
        svc.notify_result(1, 7, "PASS")                 # 未使能通道
        self.assertEqual(svc._tx_queue.qsize(), 0)


class TestDefaultsAndSnapshot(unittest.TestCase):
    """2026-10-13 端口口径对齐老上位机：rx=DestPort(7000)、tx=HandlerReplyPort(64100)"""

    def _bare(self, cfg=None):
        from app.handler import HandlerService
        hub = _Hub()

        async def start_test(targets, batch):
            return list(targets)

        return HandlerService(cfg if cfg is not None else {}, hub,
                              start_test, lambda site: "1" * 24, lambda: "B"), hub

    def test_port_defaults_align_old_system(self):
        svc, _ = self._bare()
        self.assertEqual(svc.rx_port, 7000)     # 旧 Config.DestPort 默认
        self.assertEqual(svc.tx_port, 64100)    # 旧 Config.HandlerReplyPort 默认
        self.assertFalse(svc.enabled)

    def test_cfg_values_override_defaults(self):
        svc, _ = self._bare({"handler": {"rx_port": 8000, "tx_port": 9000}})
        self.assertEqual((svc.rx_port, svc.tx_port), (8000, 9000))

    def test_snapshot_fields(self):
        svc, _ = self._bare({"handler": {"enabled": True, "rx_port": 7000,
                                         "tx_host": "192.0.2.9", "tx_port": 64100}})
        snap = svc.snapshot()
        self.assertEqual(snap, {"enabled": True, "rx_port": 7000,
                                "tx_host": "192.0.2.9", "tx_port": 64100,
                                "running": False, "learned_host": ""})


class TestLearnedHost(unittest.TestCase):
    """tx_host 留空 → 上报目标自动学习入站连接源 IP（旧 OnHandlerConnected 语义）"""

    def test_auto_learn_then_testend(self):
        async def scenario():
            svc, hub = make_service()               # tx_host=""
            acks = []

            async def ack_server(reader, writer):
                while True:
                    buf = await HandlerService._read_frame(reader)
                    if not buf:
                        break
                    req = json.loads(buf.decode())
                    acks.append(req)
                    writer.write(json.dumps(
                        {"method": req["method"], "status": "success", "data": {}}
                    ).encode())
                    await writer.drain()

            tx = await asyncio.start_server(ack_server, "127.0.0.1", 0)
            svc.tx_port = tx.sockets[0].getsockname()[1]
            await svc.start()
            rx_port = svc._server.sockets[0].getsockname()[1]

            # 假 Handler 入站（getversion）→ 源 IP 127.0.0.1 被学习
            r, w = await asyncio.open_connection("127.0.0.1", rx_port)
            w.write(b'{"method": "getversion", "data": {}}')
            await w.drain()
            await HandlerService._read_frame(r)
            w.close()

            # 集齐结果 → TX 走学习到的目标（无显式 tx_host）
            svc._pending[1] = {1}
            svc._results[1] = {}
            svc.notify_result(1, 1, "PASS")
            for _ in range(100):
                if acks:
                    break
                await asyncio.sleep(0.05)
            learned = svc._learned_host
            await svc.close()
            tx.close()
            return acks, learned

        from app.handler import HandlerService
        acks, learned = run(scenario())
        self.assertEqual(learned, "127.0.0.1")
        self.assertEqual(len(acks), 1)
        self.assertEqual(acks[0]["method"], "testend")
        self.assertEqual(acks[0]["data"]["bibid"], 1)


class TestTcpLoopback(unittest.TestCase):
    """真实 TCP 回环：RX 服务端 + TX 上报（本地起 ACK 服务端）"""

    def test_roundtrip(self):
        async def scenario():
            svc, hub = make_service()
            acks = []

            async def ack_server(reader, writer):
                while True:
                    buf = await HandlerService._read_frame(reader)
                    if not buf:
                        break
                    req = json.loads(buf.decode())
                    acks.append(req)
                    writer.write(json.dumps(
                        {"method": req["method"], "status": "success", "data": {}}
                    ).encode())
                    await writer.drain()

            # TX 目标 = 本机回环 ACK 服务端
            tx = await asyncio.start_server(ack_server, "127.0.0.1", 0)
            tx_port = tx.sockets[0].getsockname()[1]
            svc.tx_host, svc.tx_port = "127.0.0.1", tx_port

            await svc.start()                            # rx_port=0 → 系统分配
            rx_port = svc._server.sockets[0].getsockname()[1]

            # 模拟 Handler：短连接发 teststart
            r, w = await asyncio.open_connection("127.0.0.1", rx_port)
            w.write(json.dumps({"method": "teststart", "data": {
                "bibid": 1, "sites": [{"siteid": 1, "IsEnable": True},
                                       {"siteid": 2, "IsEnable": True}]}}).encode())
            await w.drain()
            resp = json.loads((await HandlerService._read_frame(r)).decode())
            w.close()
            self.assertEqual(resp["status"], "success")

            # 通道结果集齐 → TX 自动上报 testend（带重试循环，等队列消费）
            svc.notify_result(1, 1, "PASS")
            svc.notify_result(1, 2, "FAIL")
            for _ in range(100):
                if acks:
                    break
                await asyncio.sleep(0.05)
            await svc.close()
            tx.close()
            return acks

        from app.handler import HandlerService
        acks = run(scenario())
        self.assertEqual(len(acks), 1)
        self.assertEqual(acks[0]["method"], "testend")
        self.assertEqual(acks[0]["data"]["bibid"], 1)
        self.assertEqual(acks[0]["data"]["sites"],
                         [{"siteid": 1, "result": 1}, {"siteid": 2, "result": 2}])


if __name__ == "__main__":
    unittest.main()
