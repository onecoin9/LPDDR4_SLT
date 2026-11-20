"""冒烟：POST /api/config 带按 Rank 分组的 MR 档案 → WS 抓 syslog 确认编译无告警。"""
import asyncio
import json
import urllib.request

import websockets


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request("http://127.0.0.1:8000" + path, data=data,
                               method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=10) as resp:
        return json.loads(resp.read().decode())


PROFILE = {
    "name": "MR-RANK-SMOKE", "rankEnabled": True, "pl1Enabled": True,
    "pl2Enabled": True, "rankCapacityGb": [1, 0.5],          # 两 Rank 都存在
    "channels": {"ch1": True, "ch2": True},
    "mr": {
        "rank1": {"enabled": True, "rows": [
            {"name": "MR5_1", "value": "0x1A", "checked": True},
            {"name": "MR8_1", "value": "60", "checked": True}]},
        "rank2": {"enabled": True, "rows": [
            {"name": "MR5_2", "value": "0x1B", "checked": True},
            {"name": "MR8_2", "value": "61", "checked": True}]},
    },
    "params": [], "pl2": {"testMode": "全映射读写测试", "ascEnabled": True,
                          "ascOrder": "升序", "patterns": {}},
}


async def main():
    logs = []
    async with websockets.connect("ws://127.0.0.1:8000/ws") as ws:
        await ws.recv()
        print("POST /api/config:", req("POST", "/api/config", {
            "product": PROFILE["name"], "workOrder": "WO-MR", "lotNo": "S1",
            "operator": "qa", "profile": PROFILE}))

        async def pump():
            async for raw in ws:
                m = json.loads(raw)
                if m.get("type") == "log" and m.get("slot") is None:
                    logs.append(m["msg"])
                    if "产品档案已编译" in m["msg"] or m.get("level") == "WARN":
                        print("SYS>", m["msg"])

        task = asyncio.create_task(pump())
        await asyncio.sleep(2)
        task.cancel()

    compiled = [l for l in logs if "产品档案已编译" in l]
    warns = [l for l in logs if "告警" in l or "MR" in l and "非法" in l]
    assert compiled, "未见编译日志"
    assert not warns, f"有意外的 MR 告警: {warns}"
    print("SMOKE PASS：按 Rank 的 MR 档案编译无告警")


asyncio.run(main())
