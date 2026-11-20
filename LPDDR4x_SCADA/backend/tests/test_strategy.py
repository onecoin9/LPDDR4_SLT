"""测试方案（策略）加载器单测（2026-09-24 用户定案：方案 = 一份 .cfg 文本）。

运行：cd backend && python -m unittest tests.test_strategy -v
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, ".")

from app.manual import ManualDebug
from app.localdata import init_mock_data
from app.strategy import (StrategyError, list_strategies, load_strategy_text,
                          save_strategy, strategy_path)

CFG = {"cfg_defaults": {"Density": 16, "Freq": 3200},
       "manual_debug": {"enabled": True, "board_host": "192.168.50.100",
                        "mb_port": 501, "dut_count": 2, "dut_lines": [4, 5],
                        "local_ip": "192.168.50.10", "log_dir": "",
                        "cfg_file": "manual_debug.cfg",
                        "run_mode": "power_only", "ready_timeout_sec": 180}}

SCHEME_TEXT = "Density=16\nFreq=3200\nAgingTime=50\nMemTester=1\n"
CFG_FILE_TEXT = "Density=8\nFreq=1600\n"


class TestStrategyLoader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def test_save_list_load_roundtrip(self):
        self.assertEqual(list_strategies(self.dir), [])          # 无目录=空
        p = save_strategy(self.dir, "aging-50m", SCHEME_TEXT)
        self.assertTrue(os.path.isfile(p))
        self.assertEqual(list_strategies(self.dir), ["aging-50m"])
        self.assertEqual(load_strategy_text(self.dir, "aging-50m"), SCHEME_TEXT)
        self.assertEqual(load_strategy_text(self.dir, "nope"), None)

    def test_name_validation_blocks_traversal(self):
        for bad in ("../x", "a/b", "a\\b", "", "  ", "x.cfg/../y"):
            with self.assertRaises(StrategyError):
                strategy_path(self.dir, bad)

    def test_empty_file_treated_as_absent(self):
        save_strategy(self.dir, "blank", "   \n\n")
        self.assertIsNone(load_strategy_text(self.dir, "blank"))


class TestSchemePrecedence(unittest.TestCase):
    """加载优先级：scheme > cfg_file > cfg_defaults 基线（逐级降级不报错）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.md = ManualDebug(CFG, data_dir=self.dir)
        with open(self.md.cfg_file_abs(), "w", encoding="utf-8") as f:
            f.write(CFG_FILE_TEXT)

    def test_scheme_empty_keeps_cfg_file(self):
        """未配 scheme = 维持原行为（cfg_file 生效，零变化）"""
        self.assertEqual(self.md.scheme, "")
        self.assertEqual(self.md.get_cfg_text(), CFG_FILE_TEXT)
        st = self.md.active_scheme()
        self.assertEqual(st["scheme"], "")
        self.assertFalse(st["loaded"])

    def test_scheme_takes_precedence(self):
        save_strategy(self.dir, "aging-50m", SCHEME_TEXT)
        self.md.scheme = "aging-50m"
        self.assertEqual(self.md.get_cfg_text(), SCHEME_TEXT)
        st = self.md.active_scheme()
        self.assertTrue(st["loaded"])
        self.assertIn("aging-50m", st["available"])

    def test_scheme_missing_falls_back_to_cfg_file(self):
        self.md.scheme = "not-there"                     # 文件缺失 → 降级
        self.assertEqual(self.md.get_cfg_text(), CFG_FILE_TEXT)
        self.assertFalse(self.md.active_scheme()["loaded"])

    def test_scheme_and_cfg_file_missing_falls_back_baseline(self):
        self.md.scheme = "not-there"
        os.remove(self.md.cfg_file_abs())                # cfg_file 也没了
        text = self.md.get_cfg_text()
        self.assertIn("Density=16", text)                # 回 cfg_defaults 基线
        self.assertIn("Freq=3200", text)

    def test_switch_scheme_follows_config(self):
        """切方案 = 换 config.yaml 一行（此处模拟改字段）"""
        save_strategy(self.dir, "a", "Density=8\n")
        save_strategy(self.dir, "b", "Density=32\n")
        self.md.scheme = "a"
        self.assertEqual(self.md.get_cfg_text(), "Density=8\n")
        self.md.scheme = "b"
        self.assertEqual(self.md.get_cfg_text(), "Density=32\n")


class TestRepoStandardScheme(unittest.TestCase):
    def test_bundled_standard_matches_current_cfg(self):
        """干净检出无需现场 cfg；初始化的 mock 方案可以被实际加载器读取。"""
        with tempfile.TemporaryDirectory() as directory:
            root = init_mock_data(directory)
            cur = (root / "manual_debug.cfg").read_text(encoding="utf-8")
            self.assertEqual(load_strategy_text(str(root), "standard"), cur)
            self.assertEqual(ManualDebug(CFG, str(root)).get_cfg_text(), cur)


if __name__ == "__main__":
    unittest.main(verbosity=2)
