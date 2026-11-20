"""WebSocket 推送与实时状态中心（Hub）。

消息契约（与 SSOT agent.md §5.2、前端 types/dut.ts 逐字段一致，
额外附加可选 "site" 字段以支撑多 site 拓扑，默认 50 SITE）：
  {"type":"dut_status","site":1,"slot":7,"connected":true,"state":"TESTING","step":"...",
   "progress":42,"durationSec":35.0,"countdownSec":55.0,"successCount":3,"totalCount":4,"testInfo":"..."}
  {"type":"dut_result","site":1,"slot":7,"result":"FAIL","failItem":"...","durationSec":83.5}
  {"type":"log","site":1,"slot":7,"level":"INFO","cat":"dut","msg":"..."}
  # slot=null 为系统级日志；缺省按 slot 推导；cat ∈ system/dut/sys/conn：
  #   system=上位机自身，dut=主控板测试日志，sys=主控板系统运行日志
  #   （[SYS] 行标签，2026-09-16 HSG-LOG），conn=连接事件
  {"type":"manual_state","enabled":true,
   "duts":[{"dut":1,"line":0,"channel":5,"powerOn":true}],
   "run":{"mode":"full_run","duts":[{"dut":1,"channel":5,"state":"running",
          "detail":"","sinceSec":12,"enteredAt":1760123456.78}]}}
  # manual_state = 手动调试页完整快照（电源 + 完整运行状态机），事件驱动：
  # 每次电源变化/状态转换后由 main.py 组装推送，新客户端连接即下发一份，
  # 前端不再轮询 /api/manual/info、/api/manual/run_state（2026-10-10）。

1200 路并发下的节流：dut_status 变更先入 pending 表，每 200ms 合并 flush 一次
（同一 DUT 的多次更新只发最后一帧）；dut_result 与 log 低频且实时性重要，立即发送。
"""

import asyncio
import json
from typing import Dict, List, Optional, Set, Tuple

from fastapi import WebSocket

Key = Tuple[int, int]   # (site, slot)

_WS_FIELDS = ("connected", "state", "step", "progress", "durationSec",
              "countdownSec", "successCount", "totalCount", "testInfo", "result", "failItem")

FLUSH_INTERVAL_SEC = 0.2


def _default_state() -> dict:
    return {"connected": False, "state": "OFFLINE", "step": "-", "progress": 0,
            "durationSec": 0.0, "countdownSec": 0.0, "successCount": 0,
            "totalCount": 0, "testInfo": "连接失败", "result": None, "failItem": None}


class Hub:
    """全局状态中心：所有状态变更经 Hub 合并并广播；并发持有 WS 客户端。"""

    def __init__(self) -> None:
        from .timing_reports import TimingReports
        self.timing_reports = TimingReports()
        self.clients: Set[WebSocket] = set()
        self.states: Dict[Key, dict] = {}
        self.site_ids: list = []          # 有序 site id 列表，startup 时由 connection 填充
        self._pending: Dict[Key, dict] = {}
        self._flush_task: Optional[asyncio.Task] = None
        self._outgoing: dict = {}
        self._senders: dict = {}

    async def start(self) -> None:
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def close(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            self._flush_task = None
        self._flush_pending()
        tasks = list(self._senders.values())
        for ws in list(self.clients):
            self.disconnect(ws)
        await asyncio.gather(*tasks, return_exceptions=True)

    # ---------------- 客户端管理 ----------------

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)
        self._outgoing.pop(ws, None)
        task = self._senders.pop(ws, None)
        if task and task is not asyncio.current_task():
            task.cancel()

    def _send_texts(self, texts: List[str]) -> None:
        """每个客户端一个有界队列、一个发送者，保证快照/终态/连接灯按序送达。"""
        for ws in list(self.clients):
            self._enqueue(ws, texts)

    def send_to(self, ws: WebSocket, objects: list[dict]) -> None:
        self._enqueue(ws, [json.dumps(obj, ensure_ascii=False) for obj in objects])

    def _enqueue(self, ws, texts) -> None:
        if ws not in self.clients or not texts:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        q = self._outgoing.get(ws)
        if q is None:
            q = asyncio.Queue(maxsize=256)
            self._outgoing[ws] = q
            self._senders[ws] = loop.create_task(self._send_client(ws, q))
        try:
            q.put_nowait(texts)
        except asyncio.QueueFull:
            # 慢客户端重连拿最新完整快照；不能悄悄丢掉 FAIL 或下电状态。
            self.disconnect(ws)
            async def close_slow():
                try:
                    await ws.close(code=1013)
                except Exception:
                    pass
            loop.create_task(close_slow())

    async def _send_client(self, ws, q) -> None:
        try:
            while True:
                for payload in await q.get():
                    await ws.send_text(payload)
        except (Exception, asyncio.CancelledError):
            pass
        finally:
            self.disconnect(ws)

    def _broadcast(self, obj: dict) -> None:
        self._send_texts([json.dumps(obj, ensure_ascii=False)])

    # ---------------- dut_status 批量合并 ----------------

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(FLUSH_INTERVAL_SEC)
            self._flush_pending()

    def _flush_pending(self) -> None:
        if not self._pending:
            return
        texts = []
        for (site, slot), st in self._pending.items():
            texts.append(json.dumps(
                {"type": "dut_status", "site": site, "slot": slot,
                 **{k: st[k] for k in _WS_FIELDS}}, ensure_ascii=False))
        self._pending.clear()
        self._send_texts(texts)

    # ---------------- 状态更新入口 ----------------

    def ensure(self, site: int, slot: int) -> dict:
        return self.states.setdefault((site, slot), _default_state())

    def update(self, site: int, slot: int, **kw) -> None:
        """状态变更：合并进 pending，下一轮 flush（≤200ms）广播"""
        st = self.ensure(site, slot)
        st.update(kw)
        self._pending[(site, slot)] = st

    def result(self, site: int, slot: int, result: str, fail_item: str, duration_sec: float) -> None:
        """测试完成：立即广播 dut_result；随后状态经 pending 通道刷新"""
        st = self.ensure(site, slot)
        passed = result == "PASS"
        st.update(state=result, result=result,
                  failItem="" if passed else fail_item,
                  progress=100 if passed else min(99, st["progress"]), countdownSec=0.0,
                  successCount=st["successCount"] + (1 if passed else 0),
                  totalCount=st["totalCount"] + 1,
                  durationSec=duration_sec,
                  testInfo="PASS" if passed else f"FAIL: {fail_item}")
        self._broadcast({"type": "dut_result", "site": site, "slot": slot,
                         "result": result, "failItem": "" if passed else fail_item,
                         "durationSec": duration_sec})
        self._pending[(site, slot)] = st

    def log(self, site: Optional[int], slot: Optional[int], level: str, msg: str,
            cat: Optional[str] = None) -> None:
        self.timing_reports.ingest(site,slot,msg)
        # cat 缺省推导：系统级→system，通道级→dut；连接事件由调用方显式传 "conn"
        if cat is None:
            cat = "system" if slot is None else "dut"
        # 合规（2026-09-19）：HSG 为他司代号，日志输出一律替换为 AC。
        # 固件侧已根治（mt6785 仓 112a5b316），此处兜底旧固件残留的 [HSG] 打印。
        msg = msg.replace("HSG", "AC").replace("hsg_", "ac_")
        self._broadcast({"type": "log", "site": site if slot is not None else None,
                         "slot": slot, "level": level, "cat": cat, "msg": msg})

    def syslog(self, level: str, msg: str) -> None:
        self.log(None, None, level, msg)

    def manual_state(self, payload: dict) -> None:
        """手动调试完整快照（电源 + 完整运行状态机）：低频且实时性重要
        （拨杆/状态转换后要立刻上屏），走立即广播通道（同 dut_result）。
        载荷由 main.py 组装（mdbg.info + runner.snapshot），Hub 不依赖
        manual 模块。"""
        self._broadcast({"type": "manual_state", **payload})

    # ---------------- 快照 ----------------

    def snapshot(self) -> dict:
        sites = []
        for sid in self.site_ids:
            duts = []
            for (s, slot), st in sorted(self.states.items()):
                if s != sid:
                    continue
                duts.append({"slot": slot, **{k: st[k] for k in _WS_FIELDS}})
            sites.append({"id": sid, "duts": duts})
        return {"siteCount": len(self.site_ids), "sites": sites}
