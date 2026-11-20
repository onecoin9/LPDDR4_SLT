# -*- coding: utf-8 -*-
"""app/commboard.py 单测：Modbus RTU 帧、0xF000 命令打包、发现协议、回环服务器。"""
import socket
import struct
import threading
import time
import unittest

from app.commboard import (
    MbRtuUdpClient, CommBoard, IoControl, IoGroupControl, ModbusError,
    crc16_modbus, le_bytes_to_regs,
    build_assign_req, parse_assign_ack, discover, ip_to_u32,
    REG_CMD, REG_ACTION_STATE, CMD_REBOOT, CMD_IO_SECURITY_SET, CMD_TEST_RESET,
)


def crc16_table(data: bytes) -> int:
    """独立实现（移位查表展开）用于与 crc16_modbus 互验。"""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc


class TestCrc(unittest.TestCase):
    def test_known_vector(self):
        # Modbus 经典例子：01 03 00 00 00 0A → CRC 0xCDC5（线上 C5 CD）
        self.assertEqual(crc16_modbus(bytes.fromhex("01030000000A")), 0xCDC5)

    def test_cross_impl(self):
        for payload in (b"", b"\x01", bytes(range(64)),
                        bytes.fromhex("010F0000000A")):
            self.assertEqual(crc16_modbus(payload), crc16_table(payload))


class TestPacking(unittest.TestCase):
    def test_le_bytes_to_regs(self):
        self.assertEqual(le_bytes_to_regs(bytes.fromhex("01000201")), [0x0001, 0x0102])
        self.assertEqual(le_bytes_to_regs(b"\x05"), [0x0005])  # 奇数补零

    def test_io_control_pack(self):
        c = IoControl(group_id=1, line=2, start_status=1, start_sec=3,
                      duration_msec=0xFFFF)
        self.assertEqual(c.pack(), bytes.fromhex("010002010300ffff"))

    def test_ip_to_u32(self):
        # lwIP 小端：192.168.50.101 → 0x6532A8C0
        self.assertEqual(ip_to_u32("192.168.50.101"), 0x6532A8C0)


class MockMbSlave(threading.Thread):
    """回环 Modbus RTU/UDP 从站：记录 0xF000 写入，0xF001 返回固定状态。"""

    def __init__(self, state=3):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.state = state
        self.received = []          # (addr, [regs])
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
                self.assert_reg = reg_addr
                if reg_addr == REG_ACTION_STATE:
                    vals = [self.state]
                else:
                    vals = [0] * count
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


class TestCommBoardLoopback(unittest.TestCase):
    def setUp(self):
        self.slave = MockMbSlave(state=3)
        self.slave.start()
        self.board = CommBoard("127.0.0.1", mb_port=self.slave.port, timeout=1.0)

    def tearDown(self):
        self.slave.close()

    def test_reboot_command_frame(self):
        self.board.reboot()
        time.sleep(0.1)
        self.assertEqual(self.slave.received, [(REG_CMD, [CMD_REBOOT])])

    def test_action_state(self):
        self.assertEqual(self.board.action_state(), "SUCCESS")

    def test_test_reset_timestamp(self):
        self.board.test_reset(timestamp=0x01020304)
        time.sleep(0.1)
        addr, regs = self.slave.received[0]
        self.assertEqual(addr, REG_CMD)
        self.assertEqual(regs, [CMD_TEST_RESET, 0x0304, 0x0102])  # u32 低字在前

    def test_io_security_set_packing(self):
        # 序列号 0x0005 + 一路 IoControl(1,2,1,3,0xFFFF)
        self.board.io_security_set([IoControl(1, 2, 1, 3, 0xFFFF)], serial=5)
        time.sleep(0.1)
        addr, regs = self.slave.received[0]
        self.assertEqual(addr, REG_CMD)
        self.assertEqual(regs, [CMD_IO_SECURITY_SET, 0x0005,
                                0x0001, 0x0102, 0x0003, 0xFFFF])

    def test_serial_autoincrement(self):
        self.board.io_security_set([IoControl(0, 0, 1)])
        self.board.io_security_set([IoControl(0, 0, 1)])
        time.sleep(0.1)
        s1 = self.slave.received[0][1][1]
        s2 = self.slave.received[1][1][1]
        self.assertEqual((s1 + 1) & 0xFFFF, s2)

    def test_timeout(self):
        self.slave.close()
        with self.assertRaises(ModbusError):
            self.board.reboot()


class TestDiscovery(unittest.TestCase):
    def test_req_ack_roundtrip(self):
        req = build_assign_req(0, serial=0x11223344, ip=0)
        self.assertEqual(len(req), 24)
        head, tid, serial, ip, cksum, tail = struct.unpack("<6I", req)
        self.assertEqual((head, tid, ip, tail), (0xAF, 0, 0, 0xFE))
        self.assertEqual(cksum, (tid + serial + ip) & 0xFFFFFFFF)

    def test_ack_parse(self):
        # 固件 GenAck：checkSum = deviceId + serial
        ack = struct.pack("<6I", 0xAF, 0x1234, 0x9, (0x1234 + 0x9) & 0xFFFFFFFF,
                          0, 0xFE)
        parsed = parse_assign_ack(ack)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["device_id"], 0x1234)

    def test_ack_reject_bad_checksum(self):
        ack = struct.pack("<6I", 0xAF, 0x1234, 0x9, 0xDEAD, 0, 0xFE)
        self.assertIsNone(parse_assign_ack(ack))
        self.assertIsNone(parse_assign_ack(b"\x00" * 24))
        self.assertIsNone(parse_assign_ack(b"\xAF"))

    def test_ack_parse_20b_firmware_format(self):
        # 2026-09-17 真机实证：固件 AssignAck 实为 5×u32=20B
        # （GenAck: head/deviceId/serial/checkSum/tail），旧 24B 判据会把 ACK 全丢掉
        ack = struct.pack("<5I", 0xAF, 0x1A1, 0xAE584E2B,
                          (0x1A1 + 0xAE584E2B) & 0xFFFFFFFF, 0xFE)
        parsed = parse_assign_ack(ack)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["device_id"], 0x1A1)
        # 20B 坏校验和仍须拒绝
        bad = struct.pack("<5I", 0xAF, 0x1A1, 0x9, 0xDEAD, 0xFE)
        self.assertIsNone(parse_assign_ack(bad))

    def test_discover_loopback(self):
        """本机回环：起假板应答，discover 应发现它。"""
        srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 60000))

        def responder():
            srv.settimeout(5)
            try:
                data, addr = srv.recvfrom(1024)
                head, tid, serial, ip, cksum, tail = struct.unpack("<6I", data)
                ack = struct.pack("<6I", 0xAF, 0xABCD, serial,
                                  (0xABCD + serial) & 0xFFFFFFFF, 0, 0xFE)
                srv.sendto(ack, addr)
            except socket.timeout:
                pass
            srv.close()

        t = threading.Thread(target=responder, daemon=True)
        t.start()
        time.sleep(0.2)
        found = discover(timeout=2.0, broadcast_addrs=["127.0.0.1"])
        t.join(timeout=6)
        self.assertTrue(any(f["device_id"] == 0xABCD for f in found))


if __name__ == "__main__":
    unittest.main()
