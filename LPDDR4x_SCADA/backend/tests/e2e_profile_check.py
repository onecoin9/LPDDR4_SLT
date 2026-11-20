"""P4 E2E：上传产品档案 → 编译 cfg → 启动测试 → 经 WS 抓 DUT 日志验证编译值到达 DUT。

运行（backend/ 目录，mock_dut + uvicorn 已起）：
  python tests/e2e_profile_check.py
"""
import asyncio
import json
import os
import time
import urllib.request

import websockets

BASE = "http://127.0.0.1:8000"
HERE = os.path.dirname(os.path.abspath(__file__))
SLOT = 3


def req(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=10) as resp:
        return json.loads(resp.read().decode())


async def drive():
    profile = json.load(open(os.path.join(HERE, "e2e_profile.json"), encoding="utf-8"))
    body = {"product": profile["name"], "workOrder": "WO-E2E2", "lotNo": "L01",
            "operator": "qa", "profile": profile}
    print("1) POST /api/config（带 profile）:", req("POST", "/api/config", body))

    saved = req("GET", "/api/products")
    assert profile["name"] in saved, f"产品未留档: {saved}"
    print(f"2) GET /api/products: 已留档 {sorted(saved)}")

    logs = []
    done = asyncio.Event()

    async with websockets.connect("ws://127.0.0.1:8000/ws") as ws:
        await ws.recv()                                   # 首包快照
        started = req("POST", "/api/test/start", {"site": 1, "slots": [SLOT]})
        print(f"3) POST /api/test/start: {started}")
        assert started["started"] == [[1, SLOT]]

        async def pump():
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("type") == "log" and msg.get("slot") == SLOT:
                    logs.append(msg["msg"])
                    if "cfg 下发完成" in msg["msg"] or msg.get("level") == "ERROR":
                        print(f"   [DUT log] {msg['msg']}")
                elif msg.get("type") == "dut_result" and msg.get("slot") == SLOT:
                    print(f"4) dut_result: {msg}")
                    done.set()

        pump_task = asyncio.create_task(pump())
        try:
            await asyncio.wait_for(done.wait(), timeout=150)
        finally:
            pump_task.cancel()

    echo = [l for l in logs if "cfg 下发完成" in l]
    assert echo, f"未捕获 mock cfg 回显（DUT 日志 {len(logs)} 条）"
    assert "VDD1=1900mV" in echo[0], f"编译值未到达 DUT: {echo[0]}"
    assert "Density=16Gb" in echo[0]           # 基线键（档案无 Density 来源）
    print(f"5) mock 回显: {echo[0]}")

    today = time.strftime("%Y-%m-%d")
    q = req("GET", f"/api/records?date={today}&batch=WO-E2E2-L01")
    rows = [r for r in q.get("rows", []) if int(r["slot"]) == SLOT]
    assert rows and rows[0]["result"] in ("PASS", "FAIL"), f"CSV 无 slot{SLOT}: {rows}"
    print(f"6) CSV: {rows[0]}")
    print("E2E PASS：产品档案 → 留档 → cfg 编译 → 下发 → DUT 收到编译值 → CSV 落盘 全链验证通过")


if __name__ == "__main__":
    asyncio.run(drive())
