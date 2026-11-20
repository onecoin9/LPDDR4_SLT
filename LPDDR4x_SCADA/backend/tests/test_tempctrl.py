# -*- coding: utf-8 -*-
"""app/tempctrl.py 单测：帧编解码、各响应解析、TCP 回环（含拆包）。"""
import socket
import struct
import threading
import time
import unittest

from app.tempctrl import (
    TempCtrlClient, TempCtrlError, NeedMoreData,
    encode_package, decode_package, decode_temps, decode_fan_speeds,
    decode_faults, decode_voltages,
    CMD_QUERY_TEMP, CMD_SET_TEMP, DUT_NUM, FAN_NUM, TEMP_DEVIATION,
)


class TestFrame(unittest.TestCase):
    def test_encode_decode_roundtrip(self):
        param = struct.pack("<h", 850)
        pkg = encode_package(CMD_SET_TEMP, param)
        self.assertEqual(len(pkg), 11)
        self.assertEqual(pkg[:4], struct.pack("<I", 0x5A4B4457))
        cmd, got, consumed = decode_package(pkg)
        self.assertEqual(cmd, CMD_SET_TEMP)
        self.assertEqual(got, param)
        self.assertEqual(consumed, len(pkg))

    def test_checksum_error(self):
        pkg = bytearray(encode_package(CMD_SET_TEMP, struct.pack("<h", 100)))
        pkg[-1] ^= 0xFF
        with self.assertRaises(TempCtrlError):
            decode_package(bytes(pkg))

    def test_need_more_data(self):
        pkg = encode_package(CMD_QUERY_TEMP, b"")
        with self.assertRaises(NeedMoreData):
            decode_package(pkg[:6])

    def test_leading_garbage(self):
        pkg = encode_package(CMD_SET_TEMP, struct.pack("<h", -100))
        cmd, got, consumed = decode_package(b"\xDE\xAD" + pkg)
        self.assertEqual(cmd, CMD_SET_TEMP)
        self.assertEqual(consumed, 2 + len(pkg))


class TestDecoders(unittest.TestCase):
    def test_decode_temps(self):
        # raw=1250 → (1250-400)/10 = 85.0℃
        param = bytes([0x01]) + struct.pack("<h", 1250) * DUT_NUM
        temps = decode_temps(param)
        self.assertEqual(len(temps), DUT_NUM)
        self.assertAlmostEqual(temps[0], 85.0)

    def test_decode_temps_with_compensation(self):
        param = bytes([0x01]) + struct.pack("<h", 1250) * DUT_NUM
        temps = decode_temps(param, compensation=[1.5] * DUT_NUM)
        self.assertAlmostEqual(temps[0], 83.5)

    def test_decode_temps_bad_state(self):
        param = bytes([0x00]) + b"\x00" * (2 * DUT_NUM)
        with self.assertRaises(TempCtrlError):
            decode_temps(param)

    def test_decode_fan_speeds_big_endian(self):
        # 旧代码按大端解析：wire 0B B8 → 3000 RPM
        param = bytes([0x01]) + struct.pack(">H", 3000) * FAN_NUM
        speeds = decode_fan_speeds(param)
        self.assertEqual(speeds, [3000] * FAN_NUM)

    def test_decode_faults(self):
        body = bytes([0x01]) + b"\x00" * (2 * DUT_NUM)
        body += bytes([0b00000001, 0, 0])   # DUT1 温控故障位
        body += b"\x00"                     # 对齐
        body += b"\x00" * 4                 # 测试保留
        body += bytes([0, 0, 0, 0b00000100])  # 风扇故障位图
        faults = decode_faults(body)
        self.assertEqual(faults["temp_faults"][0], 0b00000001)
        self.assertEqual(faults["fan_faults"][3], 0b00000100)

    def test_decode_voltages(self):
        detect = [5000, 5001, 5002, 5003, 5004, 5005]
        shunt = [10, 11, 12, 13, 14, 15]
        param = bytes([0x01])
        param += b"".join(struct.pack("<H", v) for v in detect)
        param += b"".join(struct.pack("<H", v) for v in shunt)
        out = decode_voltages(param)
        self.assertEqual(out["detect"], detect)
        self.assertEqual(out["shunt"], shunt)


class MockTempBoard(threading.Thread):
    """回环温控板：按命令回一帧；split=True 时分两包发送（测拆包重组）。"""

    def __init__(self, split=False):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.split = split
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
                            resp_param = bytes([0x01]) + struct.pack("<h", 1250) * DUT_NUM
                        else:
                            resp_param = bytes([0x01])
                        resp = encode_package(cmd, resp_param)
                        if self.split and len(resp) > 10:
                            conn.sendall(resp[:7])
                            time.sleep(0.05)
                            conn.sendall(resp[7:])
                        else:
                            conn.sendall(resp)
                        break
                except (socket.timeout, TempCtrlError):
                    pass

    def close(self):
        self.stop_flag = True
        self.sock.close()


class TestTempCtrlLoopback(unittest.TestCase):
    def _run_query(self, split):
        board = MockTempBoard(split=split)
        board.start()
        try:
            client = TempCtrlClient("127.0.0.1", port=board.port, timeout=2.0)
            temps = client.query_temps()
            self.assertEqual(len(temps), DUT_NUM)
            self.assertAlmostEqual(temps[23], 85.0)
        finally:
            board.close()

    def test_query_temps(self):
        self._run_query(split=False)

    def test_query_temps_split_packets(self):
        self._run_query(split=True)

    def test_set_temp_frame(self):
        board = MockTempBoard()
        board.start()
        try:
            client = TempCtrlClient("127.0.0.1", port=board.port, timeout=2.0)
            resp = client.set_temp(85.0)   # 参数 850 → i16 LE
            self.assertEqual(resp[0], 0x01)
        finally:
            board.close()

    def test_timeout(self):
        client = TempCtrlClient("127.0.0.1", port=1, timeout=0.3)
        with self.assertRaises(Exception):
            client.query_temps()


if __name__ == "__main__":
    unittest.main()
