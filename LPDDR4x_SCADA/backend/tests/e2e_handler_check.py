"""Handler E2E：模拟分选机与后端完成一次完整对接回合。

前置（backend/ 目录）：
  - config.yaml handler.enabled=true, tx_host=127.0.0.1（tx 上报打到本脚本）
  - python mock_dut.py --sites 1 --slots 1-2
  - python -m uvicorn app.main:app --port 8000
运行：python tests/e2e_handler_check.py
"""
import asyncio
import json

ACK_PORT = 64999        # 后端 tx 上报目标（config tx_port）——本脚本监听并回 ACK
BACKEND_RX = 64100      # 后端 rx 监听口（脚本作为 Handler 连它）
BASE = "http://127.0.0.1:8000"

acks: list[dict] = []


async def ack_server_handler(reader, writer):
    while True:
        buf = bytearray()
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                return
            buf.extend(chunk)
            if buf.decode("utf-8", "replace").rstrip().endswith("}"):
                break
        req = json.loads(buf.decode())
        acks.append(req)
        print(f"[TX-ACK 收到上报] {json.dumps(req, ensure_ascii=False)}")
        writer.write(json.dumps({"method": req["method"], "status": "success",
                                 "data": {}}).encode())
        await writer.drain()


async def call(method: str, data: dict) -> dict:
    r, w = await asyncio.open_connection("127.0.0.1", BACKEND_RX)
    w.write(json.dumps({"method": method, "data": data}).encode())
    await w.drain()
    buf = bytearray()
    while True:
        chunk = await r.read(4096)
        if not chunk:
            break
        buf.extend(chunk)
        if buf.decode("utf-8", "replace").rstrip().endswith("}"):
            break
    w.close()
    resp = json.loads(buf.decode())
    print(f"[{method}] → {json.dumps(resp, ensure_ascii=False)[:200]}")
    return resp


async def main():
    ack_srv = await asyncio.start_server(ack_server_handler, "0.0.0.0", ACK_PORT)
    print("1) 模拟 Handler ACK 服务端已监听 :64100（接收后端 testend 上报）")

    resp = await call("getversion", {})
    assert resp["status"] == "success" and resp["data"]["version"], resp

    resp = await call("lotstart", {"lotid": "LOT-HXY-01", "productid": "LPDDR4x-16Gb",
                                   "recipe": "R1", "operator": "handler", "selfcheck": True})
    assert resp["status"] == "success", resp
    en = resp["data"]["setenable"]
    print(f"2) setenable: bibid1={en[0]['enable']}（在线位串）")

    resp = await call("teststart", {"bibid": 1, "sites": [
        {"siteid": 1, "IsEnable": True}, {"siteid": 2, "IsEnable": True}]})
    assert resp["status"] == "success", resp
    print("3) teststart 已接受，等待测试完成 → testend 自动上报...")

    for _ in range(600):                                # 最长 120s
        if any(a["method"] == "testend" for a in acks):
            break
        await asyncio.sleep(0.2)
    ack_srv.close()
    testends = [a for a in acks if a["method"] == "testend"]
    assert testends, "超时未收到 testend 上报"
    payload = testends[0]
    assert payload["data"]["bibid"] == 1
    results = {s["siteid"]: s["result"] for s in payload["data"]["sites"]}
    print(f"4) testend: bibid=1 sites={results}")
    assert set(results) == {1, 2} and all(v in (1, 2) for v in results.values())
    print("E2E PASS：getversion/lotstart(selfcheck)/teststart → 全链测试 → testend 自动上报")


asyncio.run(main())
