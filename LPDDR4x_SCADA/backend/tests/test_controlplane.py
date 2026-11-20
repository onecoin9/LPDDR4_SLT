"""P3 控制面接线层（app/controlplane.py）单元测试。

不依赖 fastapi：ControlPlane 纯 Python；通讯板/温控板用回环 mock 验证。
运行：backend/ 目录下 python -m unittest discover -s tests
"""

import socket
import struct
import threading
import time
import unittest

from app.commboard import (REG_CMD, REG_ACTION_STATE, CMD_IO_SECURITY_SET,
                           crc16_modbus)
from app.controlplane import ControlPlane, ControlPlaneError, ip_offset
from app.tempctrl import (CMD_QUERY_TEMP, CMD_QUERY_FAN_SPEED, CMD_SET_TEMP,
                          DUT_NUM, encode_package, decode_package, NeedMoreData)


def make_cfg(**over):
    """最小配置：2 个 SITE 的生成式站点 + 控制面两节。"""
    cfg = {
        "sites": {"count": 2,
                  "board_a_ip_base": "192.168.50.100",
                  "board_b_ip_base": "192.168.50.200"},
        "commboard": {"enabled": False},
        "tempctrl": {"enabled": False},
    }
    cfg.update(over)
    return cfg


class MockMbSlave(threading.Thread):
    """回环 Modbus RTU/UDP 从站：记录 FC16 写入，0xF001 返回固定动作状态。"""

    def __init__(self, state=1):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.state = state
        self.received = []          # (reg_addr, [regs])
        self.stop_flag = False

    def run(self):
        while not self.stop_flag:
            try:
                data, addr = self.sock.recvfrom(2048)
            except OSError:
                return
            if len(data) < 4 or crc16_modbus(data[:-2]) != struct.unpack("<H", data[-2:])[0]:
                continue
            slave, func = data[0], data[1]
            if func == 0x03:
                reg_addr, count = struct.unpack(">HH", data[2:6])
                vals = [self.state] if reg_addr == REG_ACTION_STATE else [0] * count
                body = bytes([count * 2]) + b"".join(struct.pack(">H", v) for v in vals[:count])
                resp = struct.pack("<BB", slave, func) + body
            elif func == 0x10:
                reg_addr, num = struct.unpack(">HH", data[2:6])
                byte_count = data[6]
                regs = [struct.unpack(">H", data[7 + 2 * i:9 + 2 * i])[0]
                        for i in range(byte_count // 2)]
                self.received.append((reg_addr, regs))
                resp = struct.pack("<BB", slave, func) + struct.pack(">HH", reg_addr, num)
            else:
                resp = struct.pack("<BB", slave, func | 0x80) + b"\x01"
            resp += struct.pack("<H", crc16_modbus(resp))
            self.sock.sendto(resp, addr)

    def close(self):
        self.stop_flag = True
        self.sock.close()


class MockTempBoard(threading.Thread):
    """回环温控板：温度固定 raw=1250（=85.0℃），风扇 4×1500rpm，记录设温值。"""

    def __init__(self, temp_raw=1250):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.temp_raw = temp_raw
        self.set_temp_param = None
        self.stop_flag = False

    def run(self):
        while not self.stop_flag:
            try:
                self.sock.settimeout(3)
                conn, _ = self.sock.accept()
            except (socket.timeout, OSError):
                continue
            with conn:
                conn.settimeout(3)
                buf = b""
                try:
                    while True:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        buf += chunk
                        try:
                            cmd, param, _ = decode_package(buf)
                        except NeedMoreData:
                            continue
                        if cmd == CMD_QUERY_TEMP:
                            resp_param = bytes([0x01]) + struct.pack("<h", self.temp_raw) * DUT_NUM
                        elif cmd == CMD_QUERY_FAN_SPEED:
                            resp_param = bytes([0x01]) + b"".join(
                                struct.pack(">H", 1500) for _ in range(4))
                        elif cmd == CMD_SET_TEMP:
                            self.set_temp_param = param
                            resp_param = bytes([0x01])
                        else:
                            resp_param = bytes([0x01])
                        conn.sendall(encode_package(cmd, resp_param))
                        break
                except (socket.timeout, OSError):
                    pass

    def close(self):
        self.stop_flag = True
        self.sock.close()


class TestBoardList(unittest.TestCase):
    """板清单推导：显式列表优先，缺省生成式（每 SITE 两块板）。"""

    def test_ip_offset(self):
        self.assertEqual(ip_offset("192.168.50.100", 3), "192.168.50.103")
        self.assertEqual(ip_offset("10.0.0.255", 1), "10.0.1.0")

    def test_generative_boards(self):
        cp = ControlPlane(make_cfg())
        boards = cp.boards()
        self.assertEqual(len(boards), 4)                     # 2 SITE × 2 板
        self.assertEqual(boards[0], {"site": 1, "board": "A",
                                     "host": "192.168.50.100", "port": 501})
        self.assertEqual(boards[3], {"site": 2, "board": "B",
                                     "host": "192.168.50.201", "port": 501})

    def test_explicit_boards_win(self):
        cp = ControlPlane(make_cfg(commboard={"enabled": True, "boards": [
            {"site": 1, "board": "a", "host": "127.0.0.1", "port": 9501},
        ]}))
        boards = cp.boards()
        self.assertEqual(len(boards), 1)                     # 显式列表取代生成式
        self.assertEqual(boards[0]["board"], "A")            # 板名统一大写
        self.assertEqual(boards[0]["port"], 9501)


class TestGuardRails(unittest.TestCase):
    """未启用/无此板 的错误语义（main.py 映射为 503/404）。"""

    def test_commboard_disabled_503(self):
        cp = ControlPlane(make_cfg())
        with self.assertRaises(ControlPlaneError) as ctx:
            cp.power_on(1, "A")
        self.assertEqual(ctx.exception.status, 503)

    def test_temp_disabled_503(self):
        cp = ControlPlane(make_cfg())
        with self.assertRaises(ControlPlaneError) as ctx:
            cp.temp_status()
        self.assertEqual(ctx.exception.status, 503)

    def test_unknown_board_404(self):
        cp = ControlPlane(make_cfg(commboard={"enabled": True}))
        with self.assertRaises(ControlPlaneError) as ctx:
            cp.power_on(99, "A")
        self.assertEqual(ctx.exception.status, 404)


class TestCommBoardViaControlPlane(unittest.TestCase):
    """通讯板命令经 ControlPlane 到达回环从站（0xF000 体系）。"""

    def setUp(self):
        self.slave = MockMbSlave(state=1)                    # 1=RUN
        self.slave.start()
        self.cp = ControlPlane(make_cfg(commboard={"enabled": True, "boards": [
            {"site": 1, "board": "A", "host": "127.0.0.1", "port": self.slave.port},
        ]}))

    def tearDown(self):
        self.slave.close()

    def test_power_on_frame(self):
        r = self.cp.power_on(1, "A", stagger_sec=2)
        self.assertEqual(r["lines"], list(range(1, 13)))     # 缺省整板 12 路
        time.sleep(0.1)
        addr, regs = self.slave.received[0]
        self.assertEqual(addr, REG_CMD)
        self.assertEqual(regs[0], CMD_IO_SECURITY_SET)       # cmd7 IO 安全分批
        # regs = [cmd, serial] + 12 路 × 4 寄存器（IoControl 8B）
        self.assertEqual(len(regs), 2 + 12 * 4)

    def test_power_off_lines(self):
        r = self.cp.power_off(1, "A", lines=[3, 5])
        self.assertEqual(r["lines"], [3, 5])
        time.sleep(0.1)
        _, regs = self.slave.received[0]
        self.assertEqual(len(regs), 2 + 2 * 4)

    def test_action_state(self):
        self.assertEqual(self.cp.action_state(1, "A")["state"], "RUN")


class TestTempViaControlPlane(unittest.TestCase):
    """温控板查询/设置经 ControlPlane 到达回环温控板。"""

    def _make_cp(self, board_port, **tc_over):
        tc = {"enabled": True, "host": "127.0.0.1", "port": board_port,
              "target_celsius": 85.0, "tolerance": 5.0}
        tc.update(tc_over)
        return ControlPlane(make_cfg(tempctrl=tc))

    def test_temp_status_ready(self):
        board = MockTempBoard(temp_raw=1250)                 # (1250-400)/10 = 85.0℃
        board.start()
        try:
            st = self._make_cp(board.port).temp_status()
        finally:
            board.close()
        self.assertEqual(st["celsius"], [85.0] * DUT_NUM)
        self.assertEqual(st["fans"], [1500] * 4)
        self.assertTrue(st["ready"])                         # 85±5 内 → 就绪

    def test_temp_status_not_ready(self):
        board = MockTempBoard(temp_raw=1000)                 # 60.0℃
        board.start()
        try:
            st = self._make_cp(board.port).temp_status()
        finally:
            board.close()
        self.assertFalse(st["ready"])

    def test_temp_status_no_target(self):
        board = MockTempBoard()
        board.start()
        try:
            st = self._make_cp(board.port, target_celsius=None).temp_status()
        finally:
            board.close()
        self.assertNotIn("ready", st)                        # 未配门槛 → 不判定

    def test_set_temp(self):
        board = MockTempBoard()
        board.start()
        try:
            self._make_cp(board.port).set_temp(85.5)
            time.sleep(0.1)
        finally:
            board.close()
        self.assertEqual(struct.unpack("<h", board.set_temp_param)[0], 855)  # ℃×10 LE

    def test_temp_unreachable_502(self):
        # 占一个随即释放的端口保证无人监听
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
        s.close()
        cp = self._make_cp(dead_port)
        cp.tc_timeout = 0.5
        with self.assertRaises(ControlPlaneError) as ctx:
            cp.temp_status()
        self.assertEqual(ctx.exception.status, 502)


if __name__ == "__main__":
    unittest.main()
