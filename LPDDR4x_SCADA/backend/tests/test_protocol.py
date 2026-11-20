"""HsgCodec 单元测试——黄金帧按两份权威源码手工推演：

- DutProtocol.EncodeCmdPackage / GenerateAckPackage / GenerateAginTimeAckPackage（C#）
- hsg_device_protocol.c send_command_with_ack / receive_config_with_ack（ACK 帧）

运行：cd backend && python -m unittest discover -s tests -v
"""

import json
import sys
import unittest

sys.path.insert(0, ".")
from app.protocol import (Ack, DutLog, DramInfo,  # noqa: E402
                          HsgCodec, Ready, StartTest, TestDone,
                          build_frame)

C = HsgCodec()


def slave(cmd: int, payload: bytes) -> bytes:
    """构造下位机→上位机帧（黄金帧用，独立于被测的 decode）"""
    n = len(payload)
    cs = 0x55
    for b in payload:
        cs ^= b
    return bytes([0xAF, n & 0xFF, (n >> 8) & 0xFF, 0x01, cmd]) + payload + bytes([cs, 0xEF])


class TestGoldenFrames(unittest.TestCase):
    """与源码逐字节对应的黄金帧"""

    def test_ack_from_pc(self):
        # DutProtocol.GenerateAckPackage(cmd=0x15, status=0)：
        # AF 02 00 00 15 00 00 (0x55^0x00) EF
        self.assertEqual(C.encode(Ack(cmd=0x15, status=0)),
                         bytes.fromhex("AF0200 00 15 0000 55 EF"))

    def test_aging_and_pwrkey_restored(self):
        # 0x12/0x13 时序控制已恢复（2026-09-19，对齐旧上位机 DutMaster）：
        # 0x12 decode → AgingTimeRequest；应答帧 = GenerateAginTimeAckPackage
        # 黄金样例（minutes=80 → 0x0050 BE）；0x13 decode → startSec/span(×0.1s)
        from app.protocol import AgingTimeAnswer, AgingTimeRequest, PwrKeySet
        self.assertIsInstance(C.decode(slave(0x12, b"\x00\x00")),
                              AgingTimeRequest)
        pk = C.decode(slave(0x13, bytes([10, 5])))
        self.assertEqual(pk, PwrKeySet(startSecond=10, span100ms=5))
        # AF 02 00 00 12 00 50 (0x55^0x00^0x50=0x05) EF
        self.assertEqual(AgingTimeAnswer(minutes=80).encode_frame(),
                         bytes.fromhex("AF0200 00 12 0050 05 EF"))

    def test_start_test_frame_layout(self):
        cfg = "AgingTime=5\n"                      # 12 字节
        frame = C.encode(StartTest(cfg=cfg))
        self.assertEqual(frame[0:5], bytes([0xAF, 12, 0, 0x00, 0x15]))
        self.assertEqual(frame[5:17], cfg.encode())
        cs = 0x55
        for b in cfg.encode():
            cs ^= b
        self.assertEqual(frame[17], cs)
        self.assertEqual(frame[18], 0xEF)
        self.assertEqual(len(frame), 12 + 7)

    def test_heartbeat_and_stop_have_no_wire_format(self):
        from app.protocol import Heartbeat, StopTest
        self.assertIsNone(C.encode(Heartbeat()))
        self.assertIsNone(C.encode(StopTest()))


class TestDecode(unittest.TestCase):

    def test_ready_16b(self):
        payload = (0x0001).to_bytes(2, "little") + (0x0002).to_bytes(2, "little") \
            + (0x0100).to_bytes(2, "little") + (0x0101).to_bytes(2, "little") \
            + b"M80-" + b"V1.1"
        msg = C.decode(slave(0x10, payload))
        self.assertIsInstance(msg, Ready)
        self.assertEqual(msg.apHWCode, 1)
        self.assertEqual(msg.apSWVer, 0x0101)
        self.assertEqual(msg.version, "M80-_V1.1")

    def test_dram_info_5b(self):
        msg = C.decode(slave(0x11, bytes([16, 8, 2, 8, 2])))
        self.assertIsInstance(msg, DramInfo)
        self.assertEqual((msg.totalGb, msg.rank0Gb, msg.rank0Die, msg.rank1Gb, msg.rank1Die),
                         (16, 8, 2, 8, 2))

    def test_start_test_ack_from_slave(self):
        # DUT 对 0x15 的 ACK（mock 与真实固件 receive_config_with_ack 均会回）
        from app.protocol import Ack
        m = C.decode(slave(0x15, b"\x00\x00"))
        self.assertIsInstance(m, Ack)
        self.assertEqual((m.cmd, m.status), (0x15, 0))

    def test_done_pass_and_fail(self):
        m = C.decode(slave(0x17, bytes([0x00, 0x00])))
        self.assertEqual((m.result, m.failItem), ("PASS", ""))
        # 0x16 容量校验失败 {0x03,0x00}（hsg_device_protocol.h HSG_TEST_DENSITY_CHECK_FAIL）
        m = C.decode(slave(0x16, bytes([0x03, 0x00])))
        self.assertEqual((m.result, m.failItem), ("FAIL", "density_check_fail"))
        # 0x16 MR 读回比对失败 {0x0A,0x00}（HSG_TEST_MR_CHECK_FAIL，2026-08-31 固件新增）
        m = C.decode(slave(0x16, bytes([0x0A, 0x00])))
        self.assertEqual((m.result, m.failItem), ("FAIL", "mr_check_fail"))
        # 0x17 非 0 → FAIL
        m = C.decode(slave(0x17, bytes([0x02, 0x00])))
        self.assertEqual(m.failItem, "signal_fail")

    def test_progress_via_record_instance1(self):
        obj = {"step": "lk_pattern", "stage": "LK", "progress": 42.0,
               "durationSec": 12.5, "countdownSec": 30.0}
        payload = bytes([1, 0x00]) + json.dumps(obj).encode()
        m = C.decode(slave(0x18, payload))
        self.assertEqual((m.step, m.stage, m.progress, m.countdownSec),
                         ("lk_pattern", "LK", 42.0, 30.0))

    def test_plain_record_is_log(self):
        m = C.decode(slave(0x18, bytes([0, 0x00]) + "pattern 0x78 ok".encode()))
        self.assertIsInstance(m, DutLog)
        self.assertEqual(m.msg, "pattern 0x78 ok")

    def test_binary_record_becomes_hex_log(self):
        m = C.decode(slave(0x18, bytes([0, 0x02]) + b"\x01\x02\x03\x04"))
        self.assertIsInstance(m, DutLog)
        self.assertIn("dt=0x02", m.msg)

    def test_rejects_bad_frames(self):
        good = slave(0x17, bytes([0, 0]))
        self.assertIsNone(C.decode(good[:-1]))                       # 截断
        bad = bytearray(good); bad[6] ^= 0xFF
        self.assertIsNone(C.decode(bytes(bad)))                      # 校验错
        wrong_role = bytes([0xAF, 2, 0, 0x00, 0x17, 0, 0, 0x55, 0xEF])
        self.assertIsNone(C.decode(wrong_role))                      # 非下位机帧
        self.assertIsNone(C.decode(b"\x01\x02"))                     # 垃圾
        self.assertIsNone(C.decode(good[:1] + bytes([99]) + good[2:]))  # 长度不符


class TestRoundtrip(unittest.TestCase):

    def test_build_frame_matches_encode(self):
        cfg = "VDD1=1950\n"
        self.assertEqual(C.encode(StartTest(cfg=cfg)),
                         build_frame(0x00, 0x15, cfg.encode()))


if __name__ == "__main__":
    unittest.main()
