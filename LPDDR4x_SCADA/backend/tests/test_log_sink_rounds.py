"""DutLogFileSink 轮次目录 / system.log / 故障韧性（2026-09-29 用户拍板重构）。

拍板内容：①同轮上电共目录（多路并发一轮一处看全）；②全部落盘（系统行、
板卡轨迹 → system.log；会话外 [DUTx] 行维持丢弃）；③落盘故障不再自禁用
（旧缺陷：一条 OSError 清 _dir 把整个 sink 静默关死，且无任何日志）。

注意：Windows 下临时目录清理要求文件句柄先关——每个用例收尾 set_dir("")。
"""

import os
import tempfile
import unittest
from unittest import mock

from app.logchannel import DutLogFileSink


def _fake_strftime_factory():
    """轮次目录名给确定且互异的值（同秒两个轮次会撞名的测试问题）。"""
    state = {"n": 0}

    def fake(fmt):
        if fmt == "%Y%m%d_%H%M%S":
            state["n"] += 1
            return f"20260929_round{state['n']}"
        return "2026-09-29 10:00:00"
    return fake


class TestRoundDir(unittest.TestCase):
    def _sink(self, d, **kw):
        sink = DutLogFileSink(**kw)
        sink.set_dir(d)
        return sink

    def test_same_round_shares_dir(self):
        """同轮多路 → 一个时间戳目录：dutN.log 并列 + system.log 同处。"""
        with tempfile.TemporaryDirectory() as d:
            sink = self._sink(d)
            sink.begin_run(5)
            sink.write("[DUT5] hello")
            sink.begin_run(6)
            sink.write("[DUT6] world")
            sink.write_system("board trace line")
            self.assertEqual(os.listdir(d), [sink._round_ts])   # 一个轮次目录
            files = sorted(os.listdir(os.path.join(d, sink._round_ts)))
            self.assertEqual(files, ["dut5.log", "dut6.log", "system.log"])
            sink.set_dir("")

    def test_new_round_after_all_end(self):
        """全部会话结束后再上电 → 开新轮（两个目录；假时钟避免同秒撞名）。"""
        with tempfile.TemporaryDirectory() as d:
            sink = self._sink(d)
            with mock.patch("app.logchannel.time.strftime",
                            side_effect=_fake_strftime_factory()):
                sink.begin_run(5)
                sink.write("[DUT5] round1")
                sink.end_run(5)
                sink.begin_run(5)
                sink.write("[DUT5] round2")
            self.assertEqual(len(os.listdir(d)), 2)
            sink.set_dir("")

    def test_midround_reboot_appends_same_file(self):
        """单路中途重启（他人仍活跃）→ 沿用同目录，dutN.log 追加不换文件。"""
        with tempfile.TemporaryDirectory() as d:
            sink = self._sink(d)
            sink.begin_run(5)
            sink.write("[DUT5] boot1")
            sink.begin_run(6)                 # 他人活跃
            sink.write("[DUT6] other")
            sink.end_run(5)                   # 5 号"重启"
            sink.begin_run(5)
            sink.write("[DUT5] boot2")
            self.assertEqual(os.listdir(d), [sink._round_ts])
            with open(os.path.join(d, sink._round_ts, "dut5.log"),
                      encoding="utf-8") as f:
                content = f.read()
            self.assertIn("boot1", content)
            self.assertIn("boot2", content)   # 追加，行首时间戳区分
            sink.set_dir("")

    def test_system_after_round_end_appends_last(self):
        """轮次全部结束后系统行仍落最近一轮的 system.log（不丢行）。"""
        with tempfile.TemporaryDirectory() as d:
            sink = self._sink(d)
            sink.begin_run(5)
            sink.write("[DUT5] hello")
            sink.end_run(5)
            sink.write_system("late board trace")
            with open(os.path.join(d, sink._round_ts, "system.log"),
                      encoding="utf-8") as f:
                self.assertIn("late board trace", f.read())
            sink.set_dir("")

    def test_session_outside_lines_still_dropped(self):
        """会话外 [DUTx] 行与无前缀 write() 行维持丢弃（用户拍板现状）。"""
        with tempfile.TemporaryDirectory() as d:
            sink = self._sink(d)
            sink.write("[DUT5] before power")
            sink.write("no tag line")
            sink.begin_run(5)
            sink.write("[DUT6] other channel")
            # 三条都被丢弃：dut5.log 从未创建
            self.assertFalse(
                os.path.exists(os.path.join(d, sink._round_ts, "dut5.log")))
            sink.set_dir("")


class TestResilience(unittest.TestCase):
    def test_write_failure_recovers_and_warns(self):
        """落盘异常：丢当条 + warner 告警 + 不自禁用 + 后续行恢复写入。"""
        warns = []
        with tempfile.TemporaryDirectory() as d:
            sink = DutLogFileSink(warner=warns.append)
            sink.set_dir(d)
            sink.begin_run(5)
            with mock.patch("os.makedirs", side_effect=OSError("boom")):
                sink.write("[DUT5] lost line")     # 失败：丢当条不抛
            self.assertEqual(sink._dir, d)          # 不再清 _dir
            self.assertEqual(len(warns), 1)
            self.assertIn("boom", warns[0])
            sink.write("[DUT5] kept line")          # 恢复：无需人工干预
            with open(os.path.join(d, sink._round_ts, "dut5.log"),
                      encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("lost line", content)
            self.assertIn("kept line", content)
            sink.set_dir("")

    def test_warner_rate_limited(self):
        """持续失败 → 告警限频：首条 + 每 100 条（150 次失败只告警 2 次）。"""
        warns = []
        with tempfile.TemporaryDirectory() as d:
            sink = DutLogFileSink(warner=warns.append)
            sink.set_dir(d)
            sink.begin_run(5)
            with mock.patch("os.makedirs", side_effect=OSError("boom")):
                for i in range(150):
                    sink.write(f"[DUT5] line {i}")
            self.assertEqual(len(warns), 2)
            sink.set_dir("")

    def test_system_write_failure_also_survives(self):
        """system.log 写失败同样不自禁用，恢复后继续。"""
        warns = []
        with tempfile.TemporaryDirectory() as d:
            sink = DutLogFileSink(warner=warns.append)
            sink.set_dir(d)
            with mock.patch("os.makedirs", side_effect=OSError("boom")):
                sink.write_system("lost sys line")
            self.assertEqual(sink._dir, d)
            sink.write_system("kept sys line")
            with open(os.path.join(d, sink._round_ts, "system.log"),
                      encoding="utf-8") as f:
                self.assertIn("kept sys line", f.read())
            sink.set_dir("")


if __name__ == "__main__":
    unittest.main()
