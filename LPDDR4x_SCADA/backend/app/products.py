"""产品档案落盘：products/<产品名>.json。

SSOT §4.3 约定：后端按 <产品名>.json 文件读写产品档案，字段与前端
frontend/src/types/product.ts 的 ProductProfile 一一对应（原样存取，不重组）。
前端当前仍以 localStorage 为编辑态权威，「确定/启动本站」时随 /api/config
上传并在后端留档；后续前端改为从后端加载（GET /api/products）时数据源已就绪。
"""

import json
import os
import re
import tempfile
from typing import Dict, List, Optional

# 桌面版打包（desktop/desktop.py）用 SLT_DATA_DIR 把档案指到 exe 旁的 products/；
# 缺省 = backend/products/（main.py 的 DATA_DIR 约定一致）
_DATA_DIR = os.environ.get("SLT_DATA_DIR")
_DIR = (os.path.join(_DATA_DIR, "products") if _DATA_DIR else
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "products"))

# Windows 文件名非法字符 → 下划线（产品名本身可含中文）
_UNSAFE = re.compile(r'[\\/:*?"<>|]')


def _path(name: str) -> str:
    safe = _UNSAFE.sub("_", str(name)).strip() or "unnamed"
    return os.path.join(_DIR, f"{safe}.json")


def save(profile: dict, fallback_name: str = "") -> Optional[str]:
    """保存/覆盖一份产品档案，返回文件路径；异常（权限/非法 JSON 名）返回 None"""
    temp_path = None
    try:
        name = profile.get("name") or fallback_name or "unnamed"
        os.makedirs(_DIR, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=_DIR,
                                         prefix=".product-", suffix=".tmp", delete=False) as f:
            temp_path = f.name
            json.dump(profile, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, _path(name))
        return _path(name)
    except (OSError, ValueError, TypeError):
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass  # 写入失败已返回 None；临时文件清理失败不能伪装为保存成功。


def list_profiles() -> List[str]:
    """已存档产品名列表（按文件名去扩展名）"""
    if not os.path.isdir(_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(_DIR) if f.endswith(".json"))


def load(name: str) -> Optional[dict]:
    """按产品名读取档案；不存在/损坏返回 None"""
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def all_profiles() -> Dict[str, dict]:
    return {name: p for name in list_profiles()
            if (p := load(name)) is not None}
