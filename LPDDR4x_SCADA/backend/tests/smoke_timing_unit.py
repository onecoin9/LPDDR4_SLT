# -*- coding: utf-8 -*-
"""端到端冒烟：timingUnit=2 的 ProductProfile → 实际 .cfg 文本（0x15 载荷形态）。"""
import sys
sys.path.insert(0, ".")
from app.cfg import base_cfg, cfg_from_profile, cfg_text  # noqa: E402

profile = {
    "name": "MCK-DEMO",
    "rankEnabled": True, "pl1Enabled": True, "pl2Enabled": True,
    "rankCapacityGb": [1, 1],
    "channels": {"ch1": True, "ch2": True},
    "mr": {"ch1": [], "ch2": []},
    "timingUnit": 2,
    "params": [
        {"id": 1, "name": "TWR时序", "value": "40", "checked": True},    # reg20 无05T
        {"id": 2, "name": "TRC", "value": "39", "checked": True},        # reg20 带05T
        {"id": 3, "name": "TRCD", "value": "31", "checked": True},       # 越界(>30) 应拒
        {"id": 4, "name": "TR2MRW", "value": "5", "checked": True},      # unsupported 应拒
        {"id": 5, "name": "TRFC", "value": "180", "checked": True},      # 恒绝对 ns
    ],
    "pl2": {"testMode": "Block测试", "ascEnabled": True, "ascOrder": "升序", "patterns": {}},
}

d, warns = cfg_from_profile(profile, base_cfg({}))
print("=== 编译告警 ===")
for w in warns:
    print(" ", w)
print("=== .cfg 时序相关行 ===")
for line in cfg_text(d).splitlines():
    k = line.split("=")[0]
    if k in ("TIMING_UNIT", "TWR", "TRC", "TRCD", "TR2MRW", "TRFC"):
        print(" ", line)
