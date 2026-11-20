# -*- coding: utf-8 -*-
"""HSG-LOG E2E（2026-09-16）：LogLevel 档位 + 行标签全链验证。

自起 backend(uvicorn:8000) + mock_dut(site1 slots1-2)，两轮验证：
  A) profile 带 LogLevel=2（全量）→ 应看到 cat=sys（[SYS] 行）与 cat=dut（[TST] 行），
     且 msg 中不残留 [SYS]/[TST] 标签；
  B) profile 带 LogLevel=1（测试档）→ mock 源头拦截 SYS，WS 不应出现 cat=sys；
     [TST] 行正常到达。
结束后自动清理子进程。

运行：cd backend && python tests/e2e_log_tags.py
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request

import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
BASE = "http://127.0.0.1:8000"


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=10) as resp:
        return json.loads(resp.read().decode())


def load_profile(log_level: int):
    p = json.load(open(os.path.join(HERE, "e2e_profile.json"), encoding="utf-8"))
    p["params"] = [row for row in p.get("params", []) if row.get("name") != "LogLevel"]
    p["params"].append({"id": 99, "name": "LogLevel", "value": str(log_level),
                        "checked": True})
    return p


async def collect(round_name: str, log_level: int, seconds: float):
    profile = load_profile(log_level)
    body = {"product": profile["name"], "workOrder": "WO-LOGTAG", "lotNo": "L01",
            "operator": "qa", "profile": profile}
    req("POST", "/api/config", body)
    logs = []

    async def listen():
        async with websockets.connect("ws://127.0.0.1:8000/ws") as ws:
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                m = json.loads(raw)
                if m.get("type") == "log":
                    logs.append(m)

    task = asyncio.create_task(listen())
    await asyncio.sleep(0.5)                      # 等 WS 接上
    req("POST", "/api/test/start", {"site": 1})
    await task
    req("POST", "/api/test/stop", {"site": 1})
    cats = {}
    for m in logs:
        cats[m["cat"]] = cats.get(m["cat"], 0) + 1
    print(f"[{round_name}] LogLevel={log_level} 收到 {len(logs)} 条 log：{cats}")
    return logs


async def drive():
    # ---- Round A：全量档 → sys + dut 都应有，标签应被剥掉 ----
    logs = await collect("A 全量", 2, 14)
    sys_logs = [m for m in logs if m["cat"] == "sys"]
    dut_logs = [m for m in logs if m["cat"] == "dut"]
    assert sys_logs, "全量档应收到 [SYS] 行（cat=sys）"
    assert dut_logs, "全量档应收到 [TST] 行（cat=dut）"
    assert any("cfg 下发完成" in m["msg"] for m in sys_logs), \
        f"cfg 摘要应进 sys 类: {[m['msg'] for m in sys_logs][:3]}"
    for m in logs:
        assert "[SYS]" not in m["msg"] and "[TST]" not in m["msg"] \
               and "[ERR]" not in m["msg"], f"标签未剥净: {m['msg']}"
    print("  A 通过：sys/dut 分类正确，行标签已剥离")

    await asyncio.sleep(2)                        # 等通道回 IDLE

    # ---- Round B：测试档 → SYS 在 DUT 源头被拦截，WS 无 cat=sys ----
    logs = await collect("B 测试档", 1, 10)
    assert not [m for m in logs if m["cat"] == "sys"], \
        f"测试档不应有 sys 日志: {[m['msg'] for m in logs if m['cat']=='sys'][:3]}"
    assert [m for m in logs if m["cat"] == "dut"], "测试档应仍有 [TST] 测试日志"
    print("  B 通过：SYS 在源头被拦截，TST 正常")

    print("\nE2E 全部通过 ✔")


async def main():
    py = sys.executable
    procs = []
    try:
        logf = open(os.path.join(HERE, "_e2e_backend.log"), "w")
        procs.append(subprocess.Popen(
            [py, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
             "--port", "8000"], cwd=BACKEND,
            stdout=logf, stderr=logf))
        procs.append(subprocess.Popen(
            [py, "mock_dut.py", "--sites", "1", "--slots", "1-2"], cwd=BACKEND,
            stdout=logf, stderr=logf))
        for _ in range(60):                        # 等后端就绪
            try:
                req("GET", "/api/duts")
                break
            except Exception:
                await asyncio.sleep(0.5)
        else:
            raise RuntimeError("backend 启动超时")
        await asyncio.sleep(4)                     # 等 mock 心跳上线
        await drive()
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()


if __name__ == "__main__":
    asyncio.run(main())
