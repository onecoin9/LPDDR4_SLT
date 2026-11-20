"""P3 控制面接线层：通讯板（Modbus 0xF000 体系）+ 温控板（TCP）的服务封装。

本模块不 import fastapi——本地单测可直接跑（本机无 fastapi 环境）；
main.py 只做薄路由包装，且所有客户端调用都是阻塞 socket，须用 asyncio.to_thread 调用。

错误约定：raise ControlPlaneError(status, msg)，main.py 映射为 HTTPException(status, msg)。
  503 = 功能未启用（config.yaml）；404 = 无此通讯板；502 = 对端设备通讯失败。
"""

import ipaddress
import time
from typing import Dict, List, Optional

from . import commboard, tempctrl


class ControlPlaneError(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


def ip_offset(base: str, off: int) -> str:
    """'192.168.50.100' + 3 → '192.168.50.103'（生成式站点规划的板 IP 推导）。"""
    return str(ipaddress.ip_address(base) + off)


class ControlPlane:
    """通讯板/温控板控制面。配置见 config.yaml 的 commboard:/tempctrl: 两节。

    板清单来源：commboard.boards 显式列表优先；缺省时按 sites 生成式推导
    （每 SITE 两块板：A=board_a_ip_base+(site-1)，B=board_b_ip_base+(site-1)，端口 501）。
    """

    def __init__(self, cfg: dict):
        cb = cfg.get("commboard") or {}
        tc = cfg.get("tempctrl") or {}
        sites = cfg.get("sites") or {}

        self.cb_enabled = bool(cb.get("enabled"))
        self.tc_enabled = bool(tc.get("enabled"))
        self.tc_host = tc.get("host", "192.168.50.2")
        self.tc_port = int(tc.get("port", 64200))
        self.tc_timeout = float(tc.get("timeout_sec", 2.0))
        # 高温老化温度就绪门槛（P3 真机联调时接 sequencer；现在 /api/temp 先返回 ready 判定）
        self.target_celsius: Optional[float] = tc.get("target_celsius")
        self.tolerance: float = float(tc.get("tolerance", 5.0))

        self._boards: List[dict] = []
        self._scanned: Dict[str, dict] = {}   # 常驻扫描在线表（addr → 板信息，粘性）
        explicit = cb.get("boards")
        if explicit:
            for b in explicit:
                self._boards.append({
                    "site": int(b["site"]),
                    "board": str(b["board"]).upper(),
                    "host": str(b["host"]),
                    "port": int(b.get("port", 501)),
                })
        else:
            count = int(sites.get("count", 1))
            a_base = sites.get("board_a_ip_base", "192.168.50.100")
            b_base = sites.get("board_b_ip_base", "192.168.50.200")
            for s in range(1, count + 1):
                self._boards.append({"site": s, "board": "A",
                                     "host": ip_offset(a_base, s - 1), "port": 501})
                self._boards.append({"site": s, "board": "B",
                                     "host": ip_offset(b_base, s - 1), "port": 501})

    # ---------------------------------------------------------------- 通讯板

    def boards(self) -> List[dict]:
        return [dict(b) for b in self._boards]

    def _require_cb(self) -> None:
        if not self.cb_enabled:
            raise ControlPlaneError(503, "通讯板控制面未启用（config.yaml commboard.enabled）")

    def resolve_board(self, site: int, board: str) -> dict:
        self._require_cb()
        b = str(board).upper()
        for it in self._boards:
            if it["site"] == site and it["board"] == b:
                return it
        raise ControlPlaneError(404, f"无此通讯板：SITE {site} 板 {b}")

    @staticmethod
    def _client(b: dict) -> commboard.CommBoard:
        return commboard.CommBoard(b["host"], mb_port=b.get("port", 501))

    def power_on(self, site: int, board: str, lines: Optional[List[int]] = None,
                 stagger_sec: int = 0) -> dict:
        """分批错峰上电（0xF000 cmd7 IO 安全分批）。lines 缺省 = 整板 12 路。"""
        b = self.resolve_board(site, board)
        lines = lines or list(range(1, 13))
        self._client(b).power_on_duts(lines, stagger_sec=stagger_sec)
        return {"ok": True, "site": site, "board": b["board"], "lines": lines,
                "stagger_sec": stagger_sec}

    def power_off(self, site: int, board: str, lines: Optional[List[int]] = None) -> dict:
        b = self.resolve_board(site, board)
        lines = lines or list(range(1, 13))
        self._client(b).power_off_duts(lines)
        return {"ok": True, "site": site, "board": b["board"], "lines": lines}

    def reboot(self, site: int, board: str) -> dict:
        """通讯板重启（0xF000 cmd3）——真机首联第一个验证命令（验字节序）。"""
        b = self.resolve_board(site, board)
        self._client(b).reboot()
        return {"ok": True, "site": site, "board": b["board"]}

    def boot_key(self, site: int, board: str, batch: int = 4, start_sec: int = 0,
                 interval_sec: int = 5, pulse_ms: int = 200, group_id: int = None) -> dict:
        """「测试板开机」分批按键（0xF000 cmd7 安全分批，旧上位机
        GenerateIoSecuritySetPackage 语义；group 缺省 MCU_PWR，下载模式传
        MCU_KPCOL）。给 sequencer 上电前置钩子用。"""
        if group_id is None:
            group_id = commboard.IO_GROUP_MCU_PWR
        b = self.resolve_board(site, board)
        self._client(b).boot_key_batch(batch, start_sec, interval_sec,
                                       pulse_ms, group_id)
        return {"ok": True, "site": site, "board": b["board"], "batch": batch}

    def action_state(self, site: int, board: str) -> dict:
        """轮询 0xF001 动作状态：NONE/RUN/FAIL/SUCCESS/ERROR。"""
        b = self.resolve_board(site, board)
        return {"site": site, "board": b["board"], "state": self._client(b).action_state()}

    def discover(self, timeout: float = 3.0) -> dict:
        """UDP 60000 广播发现通讯板。"""
        self._require_cb()
        return {"devices": commboard.discover(timeout)}

    # ---------------------------------------------------------------- 常驻扫描
    # 旧上位机 HsgBroadcast 语义：每 5s 广播一轮，板 IP 进在线表后**粘性常驻**
    # （不自动判离线；只有重置状态 ClearReadyState 才清）。扫描过程静默，
    # 只在发现新板时由调用方记 log（用户要求，2026-09-07）。

    def scan_once(self, timeout: float = 0.5) -> List[dict]:
        """广播扫描一轮（静默）。返回**本轮新发现**的板；已知板只刷新 last_seen。
        在线表 scanned_boards() 随时可查；板掉线不产生事件/日志（旧逻辑粘性）。"""
        self._require_cb()
        try:
            devs = commboard.discover(timeout)
        except OSError:
            return []                       # 网络栈异常（如无网卡广播）静默跳过
        fresh: List[dict] = []
        for d in devs:
            addr = d.get("addr", "")
            rec = self._scanned.get(addr)
            if rec is None:
                rec = {"addr": addr, "device_id": d.get("device_id"),
                       "serial": d.get("serial"),
                       "first_seen": time.time(), "last_seen": time.time()}
                self._scanned[addr] = rec
                fresh.append(rec)
            else:
                rec["last_seen"] = time.time()
                if d.get("device_id") is not None:
                    rec["device_id"] = d.get("device_id")
        return fresh

    def scanned_boards(self) -> List[dict]:
        """常驻扫描累计发现的通讯板（粘性在线表，含 first/last_seen）"""
        return list(self._scanned.values())

    # ---------------------------------------------------------------- 温控板

    def _tc(self) -> tempctrl.TempCtrlClient:
        if not self.tc_enabled:
            raise ControlPlaneError(503, "温控未启用（config.yaml tempctrl.enabled）")
        return tempctrl.TempCtrlClient(self.tc_host, self.tc_port, self.tc_timeout)

    def temp_status(self) -> dict:
        """24 路温度 + 风扇转速；配了 target_celsius 时附带 ready 判定（全路在 ±tolerance 内）。"""
        c = self._tc()
        try:
            temps = c.query_temps()
        except tempctrl.TempCtrlError as e:
            raise ControlPlaneError(502, f"温控板通讯失败：{e}")
        out: dict = {"ok": True, "celsius": temps}
        try:
            out["fans"] = c.query_fan_speeds()
        except tempctrl.TempCtrlError:
            out["fans"] = None        # 风扇查询失败不影响温度主信息
        if self.target_celsius is not None:
            lo, hi = float(self.target_celsius) - self.tolerance, float(self.target_celsius) + self.tolerance
            out["target"] = self.target_celsius
            out["tolerance"] = self.tolerance
            out["ready"] = bool(temps) and all(lo <= t <= hi for t in temps)
        return out

    def set_temp(self, celsius: float) -> dict:
        self._tc().set_temp(celsius)
        return {"ok": True, "target_celsius": celsius}

    def set_temp_on(self, on: bool) -> dict:
        self._tc().set_on_off(on)
        return {"ok": True, "on": on}
