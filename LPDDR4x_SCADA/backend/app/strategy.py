"""测试方案（策略）加载器（2026-09-24 用户定案：方案 = 一份 .cfg 文本）。

设计（用户指令原文「只是将目前的测试方案，整理成策略的方式，方便加载」）：
  - **一个方案 = strategies/ 目录下的一份 .cfg 文本**（沿用现有 cfg 格式，
    不新增格式、不新增前端/接口）；
  - `config.yaml` 的 `manual_debug.scheme: <名>` 指定当前用哪套；不填 = 维持
    原 cfg_file 行为（零变化兼容）；
  - 加载/列名/另存 均为纯代码 API（`list_strategies / load_strategy_text /
    save_strategy`），调用方流程不变。

方案名即文件名（不含 .cfg）：新增/切换方案 = 放一个文件 + 改 config.yaml 一行。
"""
from __future__ import annotations

import os
import re
from typing import List, Optional

_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class StrategyError(Exception):
    """方案名非法 / 文件缺失等（调用方决定降级或报错）。"""


def strategy_dir(data_dir: str) -> str:
    return os.path.join(data_dir, "strategies")


def strategy_path(data_dir: str, name: str) -> str:
    """方案名 → 文件绝对路径（限字符集，杜绝路径穿越）。"""
    n = str(name or "").strip()
    if not n or not _NAME_RE.match(n):
        raise StrategyError(f"方案名非法: {name!r}（仅字母数字与 _ . -）")
    return os.path.join(strategy_dir(data_dir), f"{n}.cfg")


def list_strategies(data_dir: str) -> List[str]:
    """可用方案名列表（目录内 *.cfg；目录不存在 = 空）。"""
    d = strategy_dir(data_dir)
    try:
        return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".cfg"))
    except OSError:
        return []


def load_strategy_text(data_dir: str, name: str) -> Optional[str]:
    """读取方案文本；文件不存在/为空返回 None（调用方降级到 cfg_file 基线）。"""
    p = strategy_path(data_dir, name)
    try:
        with open(p, encoding="utf-8") as f:
            text = f.read()
        return text if text.strip() else None
    except OSError:
        return None


def save_strategy(data_dir: str, name: str, text: str) -> str:
    """另存方案（代码调用；现场也可直接放文件）。返回写入路径。"""
    p = strategy_path(data_dir, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return p
