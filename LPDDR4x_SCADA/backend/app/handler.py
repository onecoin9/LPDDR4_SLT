"""Handler 分选机对接（TCP JSON，P4）。

协议按旧上位机 HCProtocol.Json.cs + BSController.stateMachine.cs 逐字段还原
（权威文档 SLT-RD-SOL-0001 与之同源）：

- 传输 = **TCP 短连接、裸 JSON、无长度前缀**（读到 '}' 即整包，TcpShortConn.cs）；
- RX（Handler → 上位机）：本服务监听 rx_port（旧默认 DestPort=7000），一连接一请求一响应；
- TX（上位机 → Handler）：主动上报 testend/alarm，短连接连 tx_host:tx_port
  （旧默认 HandlerReplyPort=64100），发 {method, data} 请求、读 {method, status} ACK
  （旧码 SendToHandlerByClient）；tx_host 留空时用最近入站连接的源 IP（旧码
  OnHandlerConnected 覆盖 _handlerIp 的"IP 自动学习"语义，内存态不落盘）；
- method：getversion / lotstart / lotend / teststart / testend / alarm / switch /
  setmachineaction / getmachineaction；
- **编号映射：bibid = 测试组号 = 我们的 SITE(1..N)，siteid = 组内 DUT = slot(1..24)**
  （旧码 HandleJsonTestStart：bibid 选 team、sites 数组给 DUT 使能位）；
- testend 结果：0=未测/禁用、1=良品、2=不良（ReportTestResult 的协议约定）；
- lotstart(selfcheck=true) 响应带 setenable：[{bibid, enable:"110.."}]（位串每字符一个 DUT）。

v1 未纳入：分 BIN（恒 1/2 映射）、switch/machineaction 的实际动作（空实现回 success）。
"""

import asyncio
import json
from typing import Awaitable, Callable, Dict, List, Optional, Set, Tuple

RESULT_INT = {"PASS": 1, "FAIL": 2}     # 其余（取消/未完成）→ 0
_TX_RETRIES = 3                          # 上报失败重试次数（旧码 3s 间隔重试）
_TX_RETRY_INTERVAL = 3.0

Key = Tuple[int, int]                    # (site, slot)


def _resp(method: str, ok: bool, data: Optional[dict] = None) -> bytes:
    return json.dumps({"method": method, "status": "success" if ok else "fail",
                       "data": data or {}}, ensure_ascii=False).encode()


class HandlerService:
    """RX 短连接服务端 + TX 上报客户端 + teststart 结果聚合。

    依赖注入（main 装配）：
    - start_test(targets, batch) -> started 列表：接 teststart 后启动测试；
    - get_site_flags(site) -> "1101.."：lotstart selfcheck 的 DUT 使能位串；
    - get_batch() -> str：teststart 启动时的批次标识。
    """

    def __init__(self, cfg: dict, hub,
                 start_test: Callable[[List[Key], str], Awaitable[List[Key]]],
                 get_site_flags: Callable[[int], str],
                 get_batch: Callable[[], str]):
        self.hub = hub
        self.start_test = start_test
        self.get_site_flags = get_site_flags
        self.get_batch = get_batch
        self.enabled = bool(cfg.get("handler", {}).get("enabled", False))
        h = cfg.get("handler", {})
        self.rx_host = str(h.get("rx_host", "0.0.0.0"))
        self.rx_port = int(h.get("rx_port", 7000))     # 旧 DestPort 默认 7000
        self.tx_host = str(h.get("tx_host", ""))
        self.tx_port = int(h.get("tx_port", 64100))    # 旧 HandlerReplyPort 默认 64100
        self._learned_host = ""                        # 入站连接源 IP（tx_host 空时的上报目标）
        self.lot_info: Dict[str, str] = {}          # lotstart 记录的批次信息
        # (site) → {slots 待收结果}；(site) → {slot: result_int}
        self._pending: Dict[int, Set[int]] = {}
        self._results: Dict[int, Dict[int, int]] = {}
        self._server: Optional[asyncio.AbstractServer] = None
        self._tx_queue: "asyncio.Queue[Tuple[str, dict]]" = asyncio.Queue()
        self._tx_active = False
        self._tx_task: Optional[asyncio.Task] = None

    @property
    def has_pending_work(self):
        return bool(self._pending or self._tx_active or not self._tx_queue.empty())

    # ---------------- 生命周期 ----------------

    async def start(self) -> None:
        if not self.enabled:
            return
        self._server = await asyncio.start_server(self._on_conn, self.rx_host, self.rx_port)
        self._tx_task = asyncio.create_task(self._tx_loop())
        target = self.tx_host or f"自动学习（当前 {self._learned_host or '未知'}）"
        self.hub.syslog("INFO", f"Handler 服务已启动：监听 :{self.rx_port}，"
                                f"上报目标 {target}:{self.tx_port}（TCP JSON 短连接）")

    async def close(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._tx_task:
            self._tx_task.cancel()
            await asyncio.gather(self._tx_task, return_exceptions=True)
            self._tx_task = None

    def snapshot(self) -> dict:
        """当前配置与运行状态（GET /api/handler/settings 载荷）"""
        return {"enabled": self.enabled, "rx_port": self.rx_port,
                "tx_host": self.tx_host, "tx_port": self.tx_port,
                "running": self._server is not None,
                "learned_host": self._learned_host}

    # ---------------- RX：短连接服务端 ----------------

    async def _on_conn(self, reader: asyncio.StreamReader,
                       writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        if peer and peer[0] and peer[0] != self._learned_host:
            # 旧码 OnHandlerConnected：入站源 IP 覆盖上报目标（tx_host 未配置时生效）
            self._learned_host = peer[0]
        try:
            raw = await asyncio.wait_for(self._read_frame(reader), timeout=5.0)
            if not raw:
                return
            self.hub.syslog("INFO", f"Handler ← {peer[0]}: {raw.decode('utf-8', 'replace')}")
            resp = await self._dispatch(raw)
            self.hub.syslog("INFO", f"Handler → {peer[0]}: {resp.decode('utf-8', 'replace')}")
            writer.write(resp)
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError, OSError):
            pass
        except Exception as e:                       # 防御：单连接异常不拖垮服务
            self.hub.syslog("ERROR", f"Handler 连接处理异常: {e!r}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    @staticmethod
    async def _read_frame(reader: asyncio.StreamReader) -> bytes:
        """旧码组包规则：读到以 '}' 结尾即整包"""
        buf = bytearray()
        while len(buf) < 65536:
            chunk = await reader.read(4096)
            if not chunk:
                break
            buf.extend(chunk)
            if buf.decode("utf-8", "replace").rstrip().endswith("}"):
                break
        return bytes(buf)

    async def _dispatch(self, raw: bytes) -> bytes:
        try:
            req = json.loads(raw.decode("utf-8", "replace").strip().strip("\x00\r\n "))
            method = str(req.get("method", "")).lower()
            data = req.get("data") or {}
        except (ValueError, AttributeError):
            return _resp("", False, {"reason": "bad request"})
        if not isinstance(data, dict):
            data = {}
        try:
            if method == "getversion":
                return _resp("getversion", True, {"version": "LPDDR4x-SCADA 0.1.0"})
            if method == "lotstart":
                return self._on_lot_start(data)
            if method == "lotend":
                self.lot_info.clear()
                self.hub.syslog("INFO", "Handler 批次结束（lotend）")
                return _resp("lotend", True)
            if method == "teststart":
                return await self._on_test_start(data)
            if method in ("switch", "setmachineaction"):
                return _resp(method, True)           # v1 无对应动作，按旧码回 success
            if method == "getmachineaction":
                bibid = int(data.get("bibid", 0))
                return _resp(method, True, {"bibid": bibid, "actionstatus": True})
            return _resp(method, False, {"reason": "unsupported method"})
        except Exception as e:
            return _resp(method, False, {"reason": str(e)})

    def _on_lot_start(self, data: dict) -> bytes:
        self.lot_info = {k: str(data.get(k, "") or "")
                         for k in ("lotid", "productid", "recipe", "operator")}
        if any(self.lot_info.values()):
            self.hub.syslog("INFO", f"Handler 批次开始: {self.lot_info}")
        if data.get("selfcheck"):
            sites = []
            for sid in self.hub.site_ids:
                sites.append({"bibid": sid, "enable": self.get_site_flags(sid)})
            return _resp("lotstart", True, {"setenable": sites})
        return _resp("lotstart", True)

    async def _on_test_start(self, data: dict) -> bytes:
        bibid = int(data.get("bibid", 0))
        slots_wanted: Dict[int, bool] = {}
        for s in data.get("sites") or []:
            if isinstance(s, dict):
                slots_wanted[int(s.get("siteid", 0))] = bool(s.get("IsEnable", False))
        if bibid not in self.hub.site_ids:
            return _resp("teststart", False, {"reason": f"invalid bibid: {bibid}"})
        slots = [s for s, en in slots_wanted.items() if en and 1 <= s <= 24]
        if not slots:
            return _resp("teststart", False, {"reason": "no enabled site"})
        started = await self.start_test([(bibid, s) for s in slots], self.get_batch())
        if not started:
            return _resp("teststart", False, {"reason": "no channel started"
                                              "（需在线且空闲）"})
        self._pending[bibid] = {slot for _, slot in started}
        self._results[bibid] = {}
        self.hub.syslog("INFO", f"Handler teststart：SITE {bibid:02d} 启动 "
                                f"{len(started)} 通道，完成后上报 testend")
        return _resp("teststart", True)

    # ---------------- 结果聚合 → testend ----------------

    def notify_result(self, site: int, slot: int, result: str) -> None:
        """sequencer 每通道终态回调；该 bibid 集齐后排队 testend 上报"""
        pend = self._pending.get(site)
        if pend is None or slot not in pend:
            return                                   # 非 Handler 发起的测试
        self._results.setdefault(site, {})[slot] = RESULT_INT.get(result, 0)
        pend.discard(slot)
        if not pend:
            results = self._results.pop(site, {})
            self._pending.pop(site, None)
            self._tx_queue.put_nowait((
                "testend",
                {"bibid": site,
                 "sites": [{"siteid": s, "result": results.get(s, 0)}
                           for s in sorted(results)]}))

    # ---------------- TX：短连接上报 ----------------

    async def send_alarm(self, message: str) -> None:
        self._tx_queue.put_nowait(("alarm", {"message": message}))

    async def _tx_loop(self) -> None:
        while True:
            method, payload = await self._tx_queue.get()
            self._tx_active = True
            try:
                ok = False
                for attempt in range(1, _TX_RETRIES + 1):
                    ok = await self._tx_once(method, payload)
                    if ok:
                        break
                    await asyncio.sleep(_TX_RETRY_INTERVAL)
                if not ok:
                    self.hub.syslog("ERROR", f"Handler 上报 {method} 失败"
                                             f"（已重试 {_TX_RETRIES} 次），丢弃")
            finally:
                self._tx_active = False
                self._tx_queue.task_done()

    async def _tx_once(self, method: str, payload: dict) -> bool:
        host = self.tx_host or self._learned_host
        if not host:
            self.hub.syslog("WARN", "Handler 上报目标未配置（handler.tx_host 为空且"
                                     "尚无入站连接可学习源 IP）")
            return False
        req = json.dumps({"method": method, "data": payload}, ensure_ascii=False)
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, self.tx_port), timeout=3.0)
            try:
                writer.write(req.encode())
                await writer.drain()
                ack_raw = await asyncio.wait_for(self._read_frame(reader), timeout=5.0)
                ack = json.loads(ack_raw.decode("utf-8", "replace"))
                ok = str(ack.get("status", "")).lower() == "success"
                self.hub.syslog("INFO", f"Handler → {host}:{self.tx_port} "
                                        f"{req}｜ACK {ack_raw.decode('utf-8', 'replace')}")
                return ok
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass
        except (OSError, ValueError, asyncio.TimeoutError) as e:
            self.hub.syslog("WARN", f"Handler 上报 {method} 异常: {e!r}")
            return False
