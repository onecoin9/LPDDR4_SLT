"""演示场景编排：一行 SITE（1-5）定格展示。

场景定义（总览第一行 5 个站点）：
  SITE 1 —— 全部 24 通道 PASS（--fail-rate 0 必过）
  SITE 2/3/4 —— 随机出现 FAIL（内置 ~11% 失败率）
  SITE 5 —— 通讯板 A（CH01-12）不启动 → 连接失败（板灯红）；板 B（CH13-24）正常测试

用法（backend/ 目录）：python demo_scene.py
前置：后端已运行（uvicorn :8000）；本脚本自带 mock 进程管理（结束不清理，方便定格展示）。
"""
import json
import subprocess
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8000"
PY = sys.executable


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=10) as resp:
        return json.loads(resp.read().decode())


def online(site):
    d = req("GET", "/api/duts")
    s = next(x for x in d["sites"] if x["id"] == site)
    return sum(1 for x in s["duts"] if x["connected"])


def main():
    print("1) 启动 mock 分组 ...")
    procs = [
        ("SITE1 必过", [PY, "mock_dut.py", "--sites", "1", "--fail-rate", "0"]),
        ("SITE2/3/4 随机", [PY, "mock_dut.py", "--sites", "2,3,4"]),
        ("SITE5 仅板B", [PY, "mock_dut.py", "--sites", "5", "--slots", "13-24"]),
    ]
    for name, cmd in procs:
        subprocess.Popen(cmd)
        print(f"   {name}: {' '.join(cmd[1:])}")

    print("2) 等待通道上线 ...")
    for _ in range(40):
        if online(1) == 24 and online(5) == 12 and online(2) == 24:
            break
        time.sleep(1)
    print(f"   SITE1={online(1)}/24  SITE2={online(2)}/24  SITE5={online(5)}/12(板B)")

    print("3) 下发配置并启动测试 ...")
    req("POST", "/api/config", {"product": "LPDDR4x-16Gb", "workOrder": "WO-DEMO",
                                "lotNo": "S01", "operator": "admin"})
    for site in (1, 2, 3, 4):
        r = req("POST", "/api/test/start", {"site": site})
        print(f"   SITE{site} started={len(r['started'])}")
    r = req("POST", "/api/test/start", {"site": 5, "slots": list(range(13, 25))})
    print(f"   SITE5(板B) started={len(r['started'])}")

    print("4) 等待测试完成（约 80s），场景定格 ...")
    deadline = time.time() + 150
    while time.time() < deadline:
        d = req("GET", "/api/duts")
        testing = sum(1 for s in d["sites"] if s["id"] <= 5
                      for x in s["duts"] if x["state"] == "TESTING")
        if testing == 0:
            break
        time.sleep(3)
    for sid in range(1, 6):
        d = req("GET", "/api/duts")
        s = next(x for x in d["sites"] if x["id"] == sid)
        p = sum(1 for x in s["duts"] if x["state"] == "PASS")
        f = sum(1 for x in s["duts"] if x["state"] == "FAIL")
        o = sum(1 for x in s["duts"] if x["state"] == "OFFLINE")
        print(f"   SITE{sid}: PASS={p} FAIL={f} OFFLINE={o}")
    print("场景就绪：总览第一行 = SITE1 全绿 / SITE2-4 随机红 / SITE5 板A红(连接失败) 板B完成")


if __name__ == "__main__":
    main()
