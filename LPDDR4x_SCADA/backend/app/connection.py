"""24 路 DUT 会话管理（UDP 透传，D1 决策）。

拓扑：每颗 DUT 经通讯板映射为「通讯板 IP + 板侧透传端口」。
后端为每个 DUT 绑定一个本地 UDP 端口（21000+(site-1)*100+slot），
发往配置的对端地址；回包按会话各自接收，会话间完全独立
（断线重连、心跳、超时互不影响 —— 验收标准 4）。

P2 换真实协议时：只需把 codec 换成 HsgCodec，本文件不动。
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .protocol import (Ack, BaseCodec,  # noqa: F401
                       DramInfo, DutLog, Heartbeat, Progress, Ready,
                       TestDone)
from .seriallink import _DutReboot, _Offline, SerialDutSession  # noqa: F401（_Offline/_DutReboot 权威定义于此，sequencer 仍从本模块导入）
from .tcplink import TcpDutSession
from .ws import Hub


class _UdpProto(asyncio.DatagramProtocol):
    def __init__(self, session: "DutSession"):
        self.session = session

    def datagram_received(self, data: bytes, addr) -> None:
        self.session._on_data(data)


class DutSession:
    """单颗 DUT 的 UDP 会话：心跳、离线判定、事件订阅。"""

    def __init__(self, site: int, slot: int, board: str, remote_ip: str, remote_port: int,
                 local_port: int, codec: BaseCodec, hub: Hub, cfg: dict):
        self.site, self.slot = site, slot
        self.board, self.remote = board, (remote_ip, remote_port)
        self.local_port = local_port
        self.codec = codec
        self.hub = hub
        self.hb_interval = float(cfg.get("heartbeat_interval_sec", 2.0))
        self.hb_timeout = float(cfg.get("heartbeat_timeout_sec", 6.0))
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.last_seen = 0.0
        self.connected = False
        self.version = ""
        self.ready_generation = 0
        self._awaiting_ready = False
        self._ignore_frames = False
        self.dram_info = ""
        self._testing_since = 0.0    # 进入 TESTING 的时刻（dut_reboot 宽限判定）
        self._queues: Set[asyncio.Queue] = set()
        self._hb_task: Optional[asyncio.Task] = None

    # ---------------- 生命周期 ----------------

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: _UdpProto(self), local_addr=("0.0.0.0", self.local_port))
        self._hb_task = asyncio.create_task(self._heartbeat_loop())
        self.hub.ensure(self.site, self.slot)

    async def close(self) -> None:
        if self._hb_task:
            self._hb_task.cancel()
        if self.transport:
            self.transport.close()

    # ---------------- 收发 ----------------

    def send(self, msg: Any) -> None:
        if not self.transport:
            return
        payload = self.codec.encode(msg)
        if payload:
            self.transport.sendto(payload, self.remote)

    def _on_data(self, data: bytes) -> None:
        if self._ignore_frames:
            return
        msg = self.codec.decode(data)
        if msg is None:
            self.hub.log(self.site, self.slot, "WARN",
                         f"CH{self.slot:02d} 收到无法解析的报文({len(data)}B)，已丢弃")
            return
        self.last_seen = time.monotonic()

        if isinstance(msg, Ready):
            self.ready_generation += 1
            # 测试中收到 0x10 = DUT 重启（旧上位机判 FAIL dut_reboot 0xFE）；
            # 非测试态才是正常上线。
            # [宽限 2026-09-28] 置 TESTING 后 ≤2s 内到达的 READY 是启动握手的
            # 尾巴（mock 保活相位/真板 UART 缓冲迟到），不算重启——吸收之。
            if (self.hub.ensure(self.site, self.slot)["state"] == "TESTING" and not self._awaiting_ready
                    and time.monotonic() - self._testing_since > 2.0):
                self.hub.log(self.site, self.slot, "ERROR",
                             f"CH{self.slot:02d} 测试中收到 0x10 —— DUT 已重启",
                             cat="conn")
                for q in list(self._queues):
                    q.put_nowait(_DutReboot())
                return
            self.version = msg.version
            if not self.connected:
                self.connected = True
                state = self.hub.ensure(self.site, self.slot)
                # 离线恢复 → IDLE；测试中收到 0x10 不改变测试状态
                if state["state"] == "OFFLINE":
                    self.hub.update(self.site, self.slot, connected=True, state="IDLE",
                                    step="-", progress=0, countdownSec=0.0, testInfo="")
                else:
                    self.hub.update(self.site, self.slot, connected=True)
                self.hub.log(self.site, self.slot, "INFO",
                             f"CH{self.slot:02d} 上线 · 版本 {msg.version}", cat="conn")
            return
        if isinstance(msg, DramInfo):
            self.dram_info = str(msg)
            self.hub.log(self.site, self.slot, "INFO", f"CH{self.slot:02d} {msg}")
            return
        # 0x12/0x13（老化时间应答/唤醒按键）死路径已移除：DUT 固件不发送这两帧
        # （完整工程侧 2026-09-02 实证），若未来到达会以"无法解析的报文"告警呈现
        if isinstance(msg, Ack):
            # DUT 对下发命令的确认（如 0x15 cfg 已收到）——计活 + 记录 +
            # 入订阅队列（sequencer 以 0x15 ACK 停止配置重发，旧上位机语义）
            self.hub.log(self.site, self.slot, "INFO",
                         f"CH{self.slot:02d} 命令确认 ACK 0x{msg.cmd:02X} status={msg.status}")
            for q in list(self._queues):
                q.put_nowait(msg)
            return
        # Progress / DutLog / TestDone：DUT 主动上报 → 日志显示 + 推给订阅中的测试任务
        if isinstance(msg, DutLog):
            self.hub.log(self.site, self.slot, msg.level, f"CH{self.slot:02d} {msg.msg}")
        if isinstance(msg, (Progress, DutLog, TestDone)):
            for q in list(self._queues):
                q.put_nowait(msg)

    # ---------------- 心跳与离线判定 ----------------

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self.hb_interval)
            self.send(Heartbeat())
            if self.connected and (time.monotonic() - self.last_seen) > self.hb_timeout:
                self._mark_offline()

    def _mark_offline(self) -> None:
        self.connected = False
        state = self.hub.ensure(self.site, self.slot)
        was_testing = state["state"] == "TESTING"
        self.hub.update(self.site, self.slot, connected=False, state=state["state"] if state["state"] in ("PASS", "FAIL") else "OFFLINE",
                        testInfo=state["testInfo"] if state["state"] in ("PASS", "FAIL") else "连接断开")
        self.hub.log(self.site, self.slot, "ERROR",
                     f"CH{self.slot:02d} 心跳超时，判定离线", cat="conn")
        if was_testing:
            for q in list(self._queues):
                q.put_nowait(_Offline())

    # ---------------- 事件订阅（sequencer 用） ----------------

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)


def _ip_plus(base_ip: str, delta: int) -> str:
    """'192.168.50.100' + 3 → '192.168.50.103'"""
    prefix, last = base_ip.rsplit(".", 1)
    return f"{prefix}.{int(last) + delta}"


def expand_sites(cfg: dict) -> list:
    """把 config.yaml 的 sites 配置展开为 [{id, name, slots:[{slot,board,ip,port}...]}] 列表。

    支持两种形式：
    - 列表（显式）：逐条写出 slot→ip/port，真机部署最终核准后可用它覆盖生成式默认值；
    - 字典（生成式，默认）：count 个 site，mode=mock 全指向本机，mode=legacy 按旧上位机
      IP 规划（A 板 192.168.50.100+(site-1)、B 板 .200+(site-1)，透传端口 2001-2012/板）。
    """
    raw = cfg.get("sites", [])
    if isinstance(raw, list):
        return raw
    count = int(raw.get("count", 1))
    mode = str(raw.get("mode", "mock"))
    mock_port_base = int(raw.get("mock_port_base", 24000))
    a_base = str(raw.get("board_a_ip_base", "192.168.50.100"))
    b_base = str(raw.get("board_b_ip_base", "192.168.50.200"))
    a_port = int(raw.get("board_a_port_base", 2001))
    b_port = int(raw.get("board_b_port_base", 2001))
    out = []
    for i in range(count):
        slots = []
        for slot in range(1, 25):
            board = "A" if slot <= 12 else "B"
            if mode == "mock":
                ip, port = "127.0.0.1", mock_port_base + i * 100 + slot
            elif board == "A":
                ip, port = _ip_plus(a_base, i), a_port + (slot - 1)
            else:
                ip, port = _ip_plus(b_base, i), b_port + (slot - 13)
            slots.append({"slot": slot, "board": board, "ip": ip, "port": port})
        out.append({"id": i + 1, "name": f"SITE {i + 1:02d}", "slots": slots})
    return out


class ConnectionManager:
    """按 config.yaml 的 sites 配置建全部会话。

    - mode=mock/legacy：UDP 透传，默认 50 SITE × 24 DUT = 1200 路（D1 决策）
    - mode=serial：串口直连单 DUT（SITE 1 仅 1 个通道 slot 1，SerialDutSession）
    - mode=tcp：TCP 直连（2026-09-07 现场硬件形态：每颗 DUT 一个 TCP 服务，
      tcp_dut.channels 显式列表 [{site,slot,host,port},...]，一颗一行）
    """

    def __init__(self, cfg: dict, hub: Hub, codec: BaseCodec):
        self.hub = hub
        self.sessions: Dict[Tuple[int, int], DutSession] = {}
        self._site_names: Dict[int, str] = {}
        sites_cfg = cfg.get("sites", {})
        mode = sites_cfg.get("mode", "mock") if isinstance(sites_cfg, dict) else "mock"
        if mode == "serial":
            scfg = cfg.get("serial_dut", {})
            self.sessions[(1, 1)] = SerialDutSession(
                site=1, slot=1, port=str(scfg.get("port", "auto")),
                codec=codec, hub=hub, cfg=scfg)
            self._site_names[1] = "SITE 01"
        elif mode == "tcp":
            tcfg = cfg.get("tcp_dut", {}) or {}
            for ch in tcfg.get("channels", []) or []:
                sid, slot = int(ch.get("site", 1)), int(ch.get("slot", 1))
                self.sessions[(sid, slot)] = TcpDutSession(
                    site=sid, slot=slot,
                    host=str(ch.get("host", "127.0.0.1")),
                    port=int(ch.get("port", 9001)),
                    codec=codec, hub=hub, cfg=tcfg)
                self._site_names.setdefault(
                    sid, f"SITE {sid:02d}")
            if not self.sessions:
                raise ValueError("sites.mode=tcp 但 tcp_dut.channels 为空——"
                                 "每颗设备一行 {site, slot, host, port}")
        else:
            for site in expand_sites(cfg):
                sid = int(site["id"])
                self._site_names[sid] = site.get("name", f"SITE {sid:02d}")
                for s in site.get("slots", []):
                    slot = int(s["slot"])
                    local_port = 21000 + (sid - 1) * 100 + slot
                    self.sessions[(sid, slot)] = DutSession(
                        site=sid, slot=slot, board=s.get("board", "?"),
                        remote_ip=s["ip"], remote_port=int(s["port"]),
                        local_port=local_port, codec=codec, hub=hub,
                        cfg=cfg.get("dut", {}))
        self.hub.site_ids = sorted(self._site_names)

    async def start(self) -> None:
        failed = 0
        for sess in self.sessions.values():
            try:
                await sess.start()
            except OSError:
                # 单路绑定失败（如端口被占）不拖垮整个后端，该通道保持离线
                failed += 1
        if failed:
            self.hub.syslog("ERROR", f"{failed} 路 DUT 会话本地端口绑定失败（端口被占用？），这些通道将保持离线")

    async def close(self) -> None:
        for sess in self.sessions.values():
            await sess.close()

    def get(self, site: int, slot: int) -> Optional[DutSession]:
        return self.sessions.get((site, slot))

    def online_idle_slots(self, site: int) -> List[int]:
        """该 site 可启动测试的通道：在线且当前不在测试中（IDLE/PASS/FAIL 终态均可复测）"""
        out = []
        for (s, slot), sess in self.sessions.items():
            if s != site or not sess.connected:
                continue
            if self.hub.ensure(s, slot)["state"] != "TESTING":
                out.append(slot)
        return sorted(out)

    def testing_slots(self, site: int) -> List[int]:
        return sorted(slot for (s, slot) in self.sessions
                      if s == site and self.hub.ensure(s, slot)["state"] == "TESTING")
