"""手动版调试（app/manual.py）单测：1 原版通讯板 × N DUT 电源开关。

协议面 = 直控寄存器（DriverSwitch.c sSwitchReg，2026-09-17 真机验证）：
单路 FC06 写 0x83/0x87/…（commboard.PWR_LINE_REG），整组 FC06 写 0xA2 位掩码。
写立即生效并硬件锁存——无 cmd7 的序列号/65s 回翻坑。
这里用 monkeypatch 替换 CommBoard 客户端验证调用参数与状态跟踪，不碰真实 socket。

运行：cd backend && python -m unittest tests.test_manual_debug -v
"""

import os
import sys
import json
import tempfile
import unittest

import yaml

sys.path.insert(0, ".")

from app import commboard                      # noqa: E402
from app.manual import ManualDebug, ManualDebugError   # noqa: E402

CFG = {"manual_debug": {"enabled": True, "board_host": "192.168.50.100",
                        "mb_port": 501, "dut_count": 4}}


class FakeBoard:
    """记录直控调用的假通讯板"""

    def __init__(self):
        self.calls = []

    def set_power_line(self, line, on):
        self.calls.append(("line", line, on))

    def set_power_group(self, mask):
        self.calls.append(("group", mask))

    def action_state(self):
        return "NONE"


class TestManualDebug(unittest.TestCase):
    def setUp(self):
        self.fake = FakeBoard()
        self.orig = commboard.CommBoard
        commboard.CommBoard = lambda *a, **k: self.fake   # 替换客户端
        self.addCleanup(setattr, commboard, "CommBoard", self.orig)
        # 隔离 data_dir：默认 "." 会读到 backend/ 下真实的 session_settings.json
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def test_disabled_503(self):
        md = ManualDebug({"manual_debug": {"enabled": False}},
                         data_dir=self.dir)
        self.assertFalse(md.info()["enabled"])
        with self.assertRaises(ManualDebugError) as ctx:
            md.set_power(1, True)
        self.assertEqual(ctx.exception.status, 503)

    def test_default_lines_and_info(self):
        md = ManualDebug(CFG, data_dir=self.dir)
        info = md.info()
        self.assertTrue(info["enabled"])
        self.assertEqual(info["boardHost"], "192.168.50.100")
        self.assertEqual([d["line"] for d in info["duts"]], [0, 1, 2, 3])
        self.assertTrue(all(not d["powerOn"] for d in info["duts"]))

    def test_power_on_off_lines(self):
        md = ManualDebug(CFG, data_dir=self.dir)
        r = md.set_power(2, True)
        self.assertEqual(r["line"], 1)               # DUT2 → 线号 1
        self.assertEqual(self.fake.calls, [("line", 1, True)])
        md.set_power(2, False)
        self.assertEqual(self.fake.calls[-1], ("line", 1, False))
        self.assertFalse(md.info()["duts"][1]["powerOn"])

    def test_power_all_mask(self):
        """整组：掩码 = dut_lines 位或；下电 = 0"""
        md = ManualDebug(CFG, data_dir=self.dir)
        r = md.set_power_all(True)
        self.assertEqual(r["mask"], 0b1111)          # 线 0-3
        self.assertEqual(self.fake.calls[-1], ("group", 0b1111))
        self.assertTrue(all(d["powerOn"] for d in md.info()["duts"]))
        md.set_power_all(False)
        self.assertEqual(self.fake.calls[-1], ("group", 0))
        self.assertTrue(all(not d["powerOn"] for d in md.info()["duts"]))

    def test_explicit_line_mapping(self):
        md = ManualDebug({"manual_debug": {"enabled": True,
                                           "dut_lines": [4, 5, 6, 7]}},
                         data_dir=self.dir)
        r = md.set_power(4, True)
        self.assertEqual(r["line"], 7)               # DUT4 → lines[3] = 7
        self.assertEqual(self.fake.calls, [("line", 7, True)])
        md.set_power_all(True)
        self.assertEqual(self.fake.calls[-1], ("group", 0b11110000))

    def test_invalid_dut_404(self):
        md = ManualDebug(CFG, data_dir=self.dir)
        for bad in (0, 5, -1):
            with self.assertRaises(ManualDebugError) as ctx:
                md.set_power(bad, True)
            self.assertEqual(ctx.exception.status, 404)
        self.assertEqual(self.fake.calls, [])        # 无效 DUT 不下发

    def test_board_timeout_502(self):
        class DeadBoard(FakeBoard):
            def set_power_line(self, line, on):
                raise commboard.ModbusError("timeout")
        self.fake = DeadBoard()
        commboard.CommBoard = lambda *a, **k: self.fake
        md = ManualDebug(CFG, data_dir=self.dir)
        with self.assertRaises(ManualDebugError) as ctx:
            md.set_power(1, True)
        self.assertEqual(ctx.exception.status, 502)
        self.assertFalse(md.info()["duts"][0]["powerOn"])  # 失败不记状态

    def test_board_state_heartbeat(self):
        md = ManualDebug(CFG, data_dir=self.dir)
        self.assertEqual(md.board_state(), {"ok": True, "state": "NONE"})

        class DeadBoard(FakeBoard):
            def action_state(self):
                raise commboard.ModbusError("timeout")
        self.fake = DeadBoard()
        commboard.CommBoard = lambda *a, **k: self.fake
        with self.assertRaises(ManualDebugError) as ctx:
            md.board_state()
        self.assertEqual(ctx.exception.status, 502)


ADD_YAML = """manual_debug:
  enabled: true
  board_host: 192.168.50.100   # 通讯板 IP（原版固件）
  dut_count: 4                 # 接 4 块测试主板
  dut_lines: [4, 5, 6, 7]      # 线号
  dut_channels: [5, 6, 7, 8]   # 通道

tempctrl:
  enabled: false
"""


class TestAddDut(unittest.TestCase):
    """add_dut（界面「+」卡片）：默认 4 路、最多 8 路，线号/通道取最小未占用值。

    持久化 = update_manual_debug_yaml 文本级更新（_yaml_scalar 已扩展支持
    list，写成 [4, 5, 6, 7, 0] 形态并保留行尾注释）。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "config.yaml")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(ADD_YAML)

    def _mk(self, lines=None, chans=None):
        md_cfg = {"enabled": True,
                  "dut_lines": [4, 5, 6, 7] if lines is None else lines,
                  "dut_channels": [5, 6, 7, 8] if chans is None else chans}
        return ManualDebug({"manual_debug": md_cfg}, data_dir=self.tmp.name)

    def _read(self):
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def test_add_fifth_min_unoccupied(self):
        """[4,5,6,7]/[5,6,7,8] → 第 5 路：线号 0、通道 1（最小未占用）"""
        md = self._mk()
        info = md.add_dut(self.path)
        self.assertEqual(len(info["duts"]), 5)
        # dut 序号是身份（新增恒为最大序号）；info 已按通道号排序，
        # 新 DUT（通道 1）显示在最前，不在末尾
        new = next(d for d in info["duts"] if d["dut"] == 5)
        self.assertEqual(info["duts"][0]["dut"], 5)
        self.assertEqual(new["line"], 0)
        self.assertEqual(new["channel"], 1)
        self.assertEqual(new["port"], 2001)        # 2000 + 通道 1
        self.assertFalse(new["powerOn"])
        self.assertEqual([d["channel"] for d in info["duts"]],
                         [1, 5, 6, 7, 8])          # 显示按通道升序
        self.assertFalse(md._power[5])             # _power 补 False

    def test_add_to_eight_then_reject_ninth(self):
        md = self._mk()
        for _ in range(4):
            md.add_dut(self.path)
        self.assertEqual(len(md.dut_lines), 8)
        self.assertEqual(sorted(md.dut_lines), list(range(8)))
        self.assertEqual(sorted(md.dut_channels), list(range(1, 9)))
        with self.assertRaises(ManualDebugError) as ctx:
            md.add_dut(self.path)
        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(len(md.dut_lines), 8)     # 拒绝后不残留

    def test_min_unoccupied_with_gaps(self):
        """有洞时取最小未占用：lines [0,2]→1；chans [1,3]→2"""
        md = self._mk(lines=[0, 2], chans=[1, 3])
        info = md.add_dut(self.path)
        new = next(d for d in info["duts"] if d["dut"] == 3)
        self.assertEqual(new["line"], 1)
        self.assertEqual(new["channel"], 2)
        self.assertEqual([d["channel"] for d in info["duts"]], [1, 2, 3])

    def test_info_sorted_by_channel_with_scrambled_order(self):
        """乱序通道表：info 输出按通道升序，dut 序号仍指列表位置"""
        md = self._mk(lines=[4, 5, 6, 7], chans=[8, 5, 7, 6])
        info = md.info()
        self.assertEqual([d["channel"] for d in info["duts"]], [5, 6, 7, 8])
        self.assertEqual([d["dut"] for d in info["duts"]], [2, 4, 3, 1])
        # 身份不变：dut 2 仍是线号 5 / 端口 2005
        d2 = next(d for d in info["duts"] if d["dut"] == 2)
        self.assertEqual((d2["line"], d2["channel"], d2["port"]), (5, 5, 2005))

    def test_disabled_503(self):
        md = ManualDebug({"manual_debug": {"enabled": False}})
        with self.assertRaises(ManualDebugError) as ctx:
            md.add_dut(self.path)
        self.assertEqual(ctx.exception.status, 503)

    def test_yaml_persisted_and_reloadable(self):
        md = self._mk()
        md.add_dut(self.path)
        text = self._read()
        self.assertIn("dut_count: 5", text)
        self.assertIn("dut_lines: [4, 5, 6, 7, 0]", text)
        self.assertIn("dut_channels: [5, 6, 7, 8, 1]", text)
        self.assertIn("# 线号", text)                    # 行尾注释保留
        self.assertIn("tempctrl:\n  enabled: false", text)  # 其它节不动
        # 写回的 yaml 可被下次启动正常加载（重启后新 DUT 仍在）
        # 用全新空目录做 data_dir，隔离 session 覆盖层——这里只验 yaml
        with open(self.path, encoding="utf-8") as f:
            reloaded = ManualDebug(yaml.safe_load(f),
                                   data_dir=tempfile.mkdtemp())
        self.assertEqual(reloaded.dut_lines, [4, 5, 6, 7, 0])
        self.assertEqual(reloaded.dut_channels, [5, 6, 7, 8, 1])


class TestRemoveDut(unittest.TestCase):
    """remove_dut（卡片「−」）：安全约束 + 成对剔除 + yaml 写回。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "config.yaml")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(ADD_YAML)
        self.fake = FakeBoard()
        self.orig = commboard.CommBoard
        commboard.CommBoard = lambda *a, **k: self.fake
        self.addCleanup(setattr, commboard, "CommBoard", self.orig)

    def _mk(self):
        return ManualDebug({"manual_debug": {
            "enabled": True, "dut_lines": [4, 5, 6, 7],
            "dut_channels": [5, 6, 7, 8]}}, data_dir=self.tmp.name)

    def _read(self):
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def test_remove_middle_keeps_pairing(self):
        """移除中间一路（dut 2）：其余 DUT 线号↔通道↔端口配对完全不变"""
        md = self._mk()
        info = md.remove_dut(2, self.path)
        self.assertEqual(md.dut_lines, [4, 6, 7])
        self.assertEqual(md.dut_channels, [5, 7, 8])
        self.assertEqual(sorted(md._power), [1, 2, 3])
        self.assertEqual(md.ch(2), 7)              # 原 dut3 通道平移到序号 2
        self.assertEqual(md.dut_port(2), 2007)
        self.assertEqual(md.dut_port(3), 2008)
        self.assertEqual([d["channel"] for d in info["duts"]], [5, 7, 8])
        self.assertEqual(len(info["duts"]), 3)

    def test_remove_powered_on_rejected(self):
        md = self._mk()
        md.set_power(2, True)
        with self.assertRaises(ManualDebugError) as ctx:
            md.remove_dut(2, self.path)
        self.assertEqual(ctx.exception.status, 400)
        self.assertIn("下电", str(ctx.exception))
        self.assertEqual(md.dut_lines, [4, 5, 6, 7])   # 拒绝后不动

    def test_remove_active_run_rejected(self):
        """is_active（完整运行活动态，由 main.py 注入 runner 查询）为真 → 400"""
        md = self._mk()
        with self.assertRaises(ManualDebugError) as ctx:
            md.remove_dut(3, self.path, is_active=lambda d: d == 3)
        self.assertEqual(ctx.exception.status, 400)
        self.assertIn("进行中", str(ctx.exception))
        self.assertEqual(md.dut_channels, [5, 6, 7, 8])

    def test_remove_nonexistent_400(self):
        md = self._mk()
        for bad in (0, 5, -1):
            with self.assertRaises(ManualDebugError) as ctx:
                md.remove_dut(bad, self.path)
            self.assertEqual(ctx.exception.status, 400)

    def test_remove_yaml_persisted_and_reloadable(self):
        md = self._mk()
        md.remove_dut(2, self.path)
        text = self._read()
        self.assertIn("dut_count: 3", text)
        self.assertIn("dut_lines: [4, 6, 7]", text)
        self.assertIn("dut_channels: [5, 7, 8]", text)
        self.assertIn("# 线号", text)
        with open(self.path, encoding="utf-8") as f:
            reloaded = ManualDebug(yaml.safe_load(f),
                                   data_dir=tempfile.mkdtemp())  # 隔离 session 覆盖层
        self.assertEqual(reloaded.dut_lines, [4, 6, 7])
        self.assertEqual(reloaded.dut_channels, [5, 7, 8])

    def test_remove_then_readd(self):
        """移除 dut 2 后再 add：最小未占用 → 线号 0、通道 1（补在最小洞，
        不是刚移除的 5/6）；移除-添加循环后配对与排序仍正确"""
        md = self._mk()
        md.remove_dut(2, self.path)
        info = md.add_dut(self.path)
        new = next(d for d in info["duts"] if d["dut"] == 4)
        self.assertEqual(new["channel"], 1)
        self.assertEqual(new["line"], 0)
        self.assertEqual([d["channel"] for d in info["duts"]], [1, 5, 7, 8])
        self.assertEqual(md.dut_lines, [4, 6, 7, 0])
        self.assertEqual(md.dut_channels, [5, 7, 8, 1])


class TestSessionLoad(unittest.TestCase):
    """启动加载 session_settings.json 覆盖（2026-10-10「配置存 json，下次
    打开可改变」）：config.yaml 是基础源，session json 是运行期覆盖层。"""

    BASE = {"enabled": True, "board_host": "192.168.50.100",
            "dut_lines": [4, 5, 6, 7], "dut_channels": [5, 6, 7, 8],
            "local_ip": "192.168.50.10", "run_mode": "power_only",
            "ready_timeout_sec": 180, "test_timeout_sec": 0}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _write_session(self, obj):
        with open(os.path.join(self.tmp.name, "session_settings.json"),
                  "w", encoding="utf-8") as f:
            json.dump(obj, f)

    def _mk(self):
        return ManualDebug({"manual_debug": dict(self.BASE)},
                           data_dir=self.tmp.name)

    def test_no_session_file_keeps_config(self):
        md = self._mk()
        self.assertEqual(md.dut_lines, [4, 5, 6, 7])
        self.assertEqual(md.run_mode, "power_only")

    def test_load_scalars_and_dut_tables(self):
        self._write_session({
            "board_host": "192.168.50.200", "local_ip": "192.168.50.30",
            "log_dir": "logs", "run_mode": "full_run",
            "ready_timeout_sec": 120, "test_timeout_sec": 600,
            "dut_count": 99,                     # 忽略，以 dut_lines 长度为准
            "dut_lines": [0, 2], "dut_channels": [1, 3]})
        md = self._mk()
        self.assertEqual(md.board_host, "192.168.50.200")
        self.assertEqual(md.run_mode, "full_run")
        self.assertEqual(md.ready_timeout_sec, 120)
        self.assertEqual(md.dut_lines, [0, 2])
        self.assertEqual(md.dut_channels, [1, 3])
        self.assertEqual(sorted(md._power), [1, 2])     # 按新表重建

    def test_bad_json_and_non_dict_ignored(self):
        path = os.path.join(self.tmp.name, "session_settings.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(self._mk().dut_lines, [4, 5, 6, 7])
        self._write_session([1, 2, 3])                  # 非 dict
        self.assertEqual(self._mk().dut_lines, [4, 5, 6, 7])

    def test_invalid_keys_skipped_individually(self):
        self._write_session({"run_mode": "xxx", "ready_timeout_sec": 1,
                             "board_host": "not-an-ip",
                             "local_ip": "192.168.50.31"})
        md = self._mk()
        self.assertEqual(md.run_mode, "power_only")     # 非法跳过
        self.assertEqual(md.ready_timeout_sec, 180)
        self.assertEqual(md.board_host, "192.168.50.100")
        self.assertEqual(md.local_ip, "192.168.50.31")  # 合法键生效

    def test_invalid_dut_tables_discarded_as_pair(self):
        # 长度不一致 → 整组弃用
        self._write_session({"dut_lines": [0, 2], "dut_channels": [1, 3, 4]})
        self.assertEqual(self._mk().dut_lines, [4, 5, 6, 7])
        # 线号越界 → 整组弃用
        self._write_session({"dut_lines": [0, 9], "dut_channels": [1, 3]})
        self.assertEqual(self._mk().dut_channels, [5, 6, 7, 8])
        # 通道重复 → 整组弃用
        self._write_session({"dut_lines": [0, 2], "dut_channels": [3, 3]})
        self.assertEqual(self._mk().dut_lines, [4, 5, 6, 7])

    def test_add_remove_double_write_session(self):
        """add/remove 双写：config.yaml 与 session json 都更新（重启仍生效）"""
        cfg_path = os.path.join(self.tmp.name, "config.yaml")
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(ADD_YAML)
        md = self._mk()
        md.add_dut(cfg_path)
        saved = json.load(open(os.path.join(self.tmp.name,
                                            "session_settings.json"),
                               encoding="utf-8"))
        self.assertEqual(saved["dut_lines"], [4, 5, 6, 7, 0])
        self.assertEqual(saved["dut_channels"], [5, 6, 7, 8, 1])
        self.assertEqual(saved["dut_count"], 5)
        md.remove_dut(5, cfg_path)
        saved = json.load(open(os.path.join(self.tmp.name,
                                            "session_settings.json"),
                               encoding="utf-8"))
        self.assertEqual(saved["dut_lines"], [4, 5, 6, 7])
        # 新实例（模拟重启）从 session json 恢复
        md2 = self._mk()
        self.assertEqual(md2.dut_lines, [4, 5, 6, 7])


class TestPowerLineRegMap(unittest.TestCase):
    """线号 → 寄存器映射与固件 sSwitchReg 一致性（DriverSwitch.c）"""

    def test_map(self):
        self.assertEqual(commboard.PWR_LINE_REG[0], 0x83)   # PW1
        self.assertEqual(commboard.PWR_LINE_REG[3], 0x8F)   # PW4
        self.assertEqual(commboard.PWR_LINE_REG[7], 0x9F)   # PW8
        self.assertEqual(commboard.PWR_LINE_REG[8], 0x70)   # PW9
        self.assertEqual(commboard.PWR_LINE_REG[11], 0x73)  # PW12
        self.assertEqual(commboard.REG_PWR_GROUP, 0xA2)

    def test_invalid_line_rejected(self):
        b = commboard.CommBoard("192.0.2.1")         # 不会真正发包
        with self.assertRaises(commboard.ModbusError):
            b.set_power_line(12, True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
