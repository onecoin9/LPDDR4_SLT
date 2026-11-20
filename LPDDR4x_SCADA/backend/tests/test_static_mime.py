"""静态资源 MIME 防御回归（2026-10-29 现场黑屏根因）。

现场实机案例：注册表 HKCR 下 .js 的 Content Type 异常 → Python mimetypes
从注册表取到错误类型 → StaticFiles 伺服的 module 脚本被 WebView2 拒绝
执行 → 界面整页空白。main.py 在模块头显式 add_type 兜底；本测试保证该
兜底在导入 app.main 后始终成立——在注册表异常的机器上，若有人删掉兜底，
此测试会立即变红。
"""

import mimetypes
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class StaticMimeTests(unittest.TestCase):
    def test_frontend_asset_mime_overrides_registry(self):
        import app.main  # noqa: F401  模块头 add_type 生效于全局 MIME 表
        self.assertEqual(mimetypes.guess_type("app.js")[0], "text/javascript")
        self.assertEqual(mimetypes.guess_type("chunk.mjs")[0], "text/javascript")
        self.assertEqual(mimetypes.guess_type("style.css")[0], "text/css")

    def test_add_type_survives_hostile_registry_value(self):
        """模拟被污染的注册表条目：add_type 显式覆盖后 guess 必须正确。"""
        mimetypes.add_type("text/plain", ".js")
        self.assertEqual(mimetypes.guess_type("app.js")[0], "text/plain")
        mimetypes.add_type("text/javascript", ".js")
        self.assertEqual(mimetypes.guess_type("app.js")[0], "text/javascript")


if __name__ == "__main__":
    unittest.main()
