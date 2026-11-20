"""机台配置持久化（2026-10-10「设置保存 json，下次开启加载」）单测。

POST /api/config → save_machine_config 写 machine_settings.json；
重启 → load_machine_config 恢复。profile 不落盘（产品档案在 products/）。

运行：cd backend && python -m unittest tests.test_machine_config -v
"""

import json
import ast
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, ".")

from app.models import MachineConfig                            # noqa: E402

# Execute the actual persistence functions without importing the hardware assembly
# root. A clean clone has no real config.yaml and tests must not read field data.
_tree = ast.parse((Path(__file__).parents[1] / 'app/main.py').read_text(encoding='utf-8-sig'))
_functions = [node for node in _tree.body if isinstance(node, ast.FunctionDef)
              and node.name in ('load_machine_config', 'save_machine_config')]
_scope = {'json': json, 'MachineConfig': MachineConfig}
exec(compile(ast.Module(body=_functions, type_ignores=[]), 'main.py', 'exec'), _scope)
load_machine_config = _scope['load_machine_config']
save_machine_config = _scope['save_machine_config']


class TestMachineConfigPersist(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "machine_settings.json")

    def test_roundtrip(self):
        cfg = MachineConfig(product="LPDDR4x-16Gb", workOrder="WO-1",
                            lotNo="LOT-A", operator="admin",
                            profile={"name": "P1"},
                            ioControl={"action": "power_key", "batch": 4,
                                       "startDelaySec": 0, "intervalSec": 5,
                                       "pulseMs": 200})
        save_machine_config(self.path, cfg)
        # profile 不落盘
        saved = json.load(open(self.path, encoding="utf-8"))
        self.assertNotIn("profile", saved)
        self.assertEqual(saved["workOrder"], "WO-1")
        # 重启加载恢复
        loaded = load_machine_config(self.path)
        self.assertEqual(loaded.product, "LPDDR4x-16Gb")
        self.assertEqual(loaded.workOrder, "WO-1")
        self.assertEqual(loaded.lotNo, "LOT-A")
        self.assertEqual(loaded.operator, "admin")
        self.assertNotIn("ioControl", saved)
        self.assertIsNone(loaded.ioControl)
        self.assertIsNone(loaded.profile)

    def test_missing_or_bad_file_falls_back(self):
        self.assertEqual(load_machine_config(self.path).product, "")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(load_machine_config(self.path).product, "")
        # 非法字段值（ioControl.action 超枚举）→ 整体回落空配置
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"product": "X", "ioControl": {"action": "bogus"}}, f)
        self.assertEqual(load_machine_config(self.path).product, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
