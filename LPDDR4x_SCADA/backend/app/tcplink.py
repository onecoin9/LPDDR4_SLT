"""TCP 直连 DUT 会话（sites.mode=tcp，2026-09-07 按现场硬件形态新增）。

现场形态：每颗 DUT（或其测试盒/串口服务器）对外提供一个 TCP 服务
（IP:端口），PC 作为 TCP 客户端逐颗连接；线上跑的还是同一套 hsg 字节流
（文本日志 + 0xAF 帧混流）——解析/路由/自动 ACK 全部复用
BaseStreamSession（seriallink.py），本文件只实现 asyncio TCP 传输：
  - 连接：asyncio.open_connection（connect_timeout_sec 控制握手超时）
  - 保活：SO_KEEPALIVE（系统默认参数）；DUT 未配置时会周期重发 0x10，
    链路活性由协议流量天然保证
  - 断线：读 EOF/异常 → _on_link_dead（OFFLINE + 测试中通道 FAIL(连接断开)），
    retry_sec 后自动重连（DUT 侧 send_command_with_ack 会持续重发 0x10，
    重连成功即恢复）
通道定义：config.yaml 的 tcp_dut.channels 显式列表
[{site, slot, host, port}, ...]——一颗设备一行，site/slot 决定它落在
前端哪个 SITE 哪个通道灯上。
"""

import asyncio
import socket
from typing import Optional

from .seriallink import BaseStreamSession


class TcpDutSession(BaseStreamSession):
    """单颗 DUT 的 TCP 直连会话（接口与 UDP DutSession / SerialDutSession 同构）。

    cfg 取 tcp_dut 节：{connect_timeout_sec: 5, retry_sec: 2, auto_ack: true}
    """

    def __init__(self, site: int, slot: int, host: str, port: int,
                 codec, hub, cfg: Optional[dict] = None):
        super().__init__(site, slot, codec, hub, cfg)
        self.host = str(host)
        self.port = int(port)
        self.connect_timeout = float((cfg or {}).get("connect_timeout_sec", 5))
        self.retry_sec = float((cfg or {}).get("retry_sec", 2))
        self.transport = None                       # 仅为 duck-type 兼容
        self._writer: Optional[asyncio.StreamWriter] = None
        self._task: Optional[asyncio.Task] = None
        self._closing = False

    # ---------------- 生命周期 ----------------

    async def start(self) -> None:
        self.hub.ensure(self.site, self.slot)
        self._closing = False
        self._task = asyncio.create_task(
            self._run(), name=f"tcp-{self.site}-{self.slot}-{self.host}:{self.port}")

    async def close(self) -> None:
        self._closing = True
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        if self.connected:
            self.connected = False
            self.hub.update(self.site, self.slot, connected=False,
                            state="OFFLINE", testInfo="后端关闭连接")

    # ---------------- 传输主循环 ----------------

    async def _run(self) -> None:
        while not self._closing:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=self.connect_timeout)
            except (OSError, asyncio.TimeoutError) as e:
                self._on_link_dead(f"TCP 连接失败 {self.host}:{self.port}: {e}")
                await asyncio.sleep(self.retry_sec)
                continue
            try:
                sock = writer.get_extra_info("socket")
                if sock is not None:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except OSError:
                pass
            self._writer = writer
            self.hub.log(self.site, self.slot, "INFO",
                         f"CH{self.slot:02d} TCP 已连接 {self.host}:{self.port}",
                         cat="conn")
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        raise ConnectionResetError("对端关闭连接")
                    self.rx_bytes += len(data)
                    self._feed(data)                # 解析 + 自动 ACK + 路由（本就在 loop 线程）
            except (OSError, ConnectionResetError) as e:
                self._writer = None
                try:
                    writer.close()
                except Exception:
                    pass
                if self._closing:
                    return
                self._on_link_dead(f"TCP 断开: {e}")
                await asyncio.sleep(self.retry_sec)

    # ---------------- BaseStreamSession 契约 ----------------

    def _send_bytes(self, frame: bytes) -> None:
        w = self._writer
        if w is None:
            raise RuntimeError("TCP 未连接")
        w.write(frame)          # 小帧（≤512B）写缓冲即可，无需 drain
        self.tx_bytes += len(frame)

    def _schedule(self, fn, *args) -> None:
        fn(*args)               # 读循环本就在 asyncio 线程

    def send(self, msg) -> None:
        payload = self.codec.encode(msg)
        if not payload:
            return              # 协议不承载（心跳/停止）
        try:
            self._send_bytes(payload)
        except Exception as e:
            self._on_link_dead(f"TCP 写入失败: {e}")
