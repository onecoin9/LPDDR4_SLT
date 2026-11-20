# -*- coding: utf-8 -*-
"""通讯板（TXP03 / GD32F407）控制面客户端 —— P3

两条通道（协议来源：CommBoardFW 现仓源码，见 memory.md §3.4/§4.2）：

1. Modbus RTU over UDP（默认端口 501，从站地址 1）
   - 0xF000 命令寄存器（FC16 写入，Word0=命令字，其后为参数区）
   - 0xF001 状态寄存器（FC03 读取，ACTION_STATE: 0=NONE 1=RUN 2=FAIL 3=SUCCESS 4=ERROR）
   - 命令字（MbService.h ACTION_CMD 枚举序）：
       1=OTA(params: u32 目标版本)  2=多组IO定时  3=重启  4=保存配置
       5=单路IO毫秒定时  6=对时+复位(params: u32 秒时间戳)  7=IO安全分批(带防重放序列号)
   - 字节序：freemodbus 按标准 Modbus 大端解析寄存器 → MCU 内存 u16 值，
     结构体 memcpy 按小端排布（Cortex-M4）。因此参数打包规则 =
     "结构体小端字节流 → 每 2 字节为一个寄存器值 → 线上大端发送"。
     （COMM_PROTOCOL.md 的"16bit 小端"表述与 freemodbus 标准行为不一致，
     此处按代码实证实现，真机首联时需用一条 reboot 命令验证字节序。）

2. 设备发现 / IP 分配（UDP 60000 广播，AddrAssignService.c）
   - AssignReq:  6×u32 LE = [0xAF, targetId, serial, ipAddr, checkSum, 0xFE]
                 checkSum = targetId+serial+ipAddr（u32 回绕加法）
                 targetId=0 且 ipAddr=0 → 查询在线设备
   - AssignAck:  6×u32 LE = [0xAF, deviceId, serial, checkSum, 0xFE]
                 checkSum = deviceId+serial
"""
from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass
from typing import List, Optional

# ---------------------------------------------------------------- Modbus RTU

FC_READ_HOLDING = 0x03
FC_WRITE_SINGLE = 0x06
FC_WRITE_MULTIPLE = 0x10

REG_CMD = 0xF000
REG_ACTION_STATE = 0xF001

CMD_OTA = 1
CMD_MULT_IO_SET = 2
CMD_REBOOT = 3
CMD_SAVE_CONFIG = 4
CMD_IO_SET = 5
CMD_TEST_RESET = 6
CMD_IO_SECURITY_SET = 7

ACTION_STATE = {0: "NONE", 1: "RUN", 2: "FAIL", 3: "SUCCESS", 4: "ERROR"}

MB_EXC = {1: "ILLEGAL_FUNCTION", 2: "ILLEGAL_DATA_ADDRESS",
          3: "ILLEGAL_DATA_VALUE", 4: "SLAVE_DEVICE_FAILURE"}


class ModbusError(Exception):
    pass


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def le_bytes_to_regs(buf: bytes) -> List[int]:
    """MCU 内存小端字节流 → u16 寄存器值列表（奇数长度补 0）。"""
    if len(buf) % 2:
        buf += b"\x00"
    return [buf[i] | (buf[i + 1] << 8) for i in range(0, len(buf), 2)]


class MbRtuUdpClient:
    """Modbus RTU over UDP 客户端（freemodbus mbrtu_udp 对端）。"""

    def __init__(self, host: str, port: int = 501, slave: int = 1,
                 timeout: float = 1.0):
        self.host = host
        self.port = port
        self.slave = slave
        self.timeout = timeout

    def _transact(self, pdu: bytes) -> bytes:
        frame = struct.pack("<B", self.slave) + pdu
        frame += struct.pack("<H", crc16_modbus(frame))
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(self.timeout)
            sock.sendto(frame, (self.host, self.port))
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    resp, _ = sock.recvfrom(1024)
                    break
                except ConnectionResetError:
                    # Windows：对端端口不可达时 ICMP 使 recvfrom 抛 10054，
                    # 视同无应答，继续等到超时
                    if time.monotonic() >= deadline:
                        raise ModbusError(f"timeout waiting {self.host}:{self.port}")
                    sock.settimeout(max(0.05, deadline - time.monotonic()))
        except socket.timeout:
            raise ModbusError(f"timeout waiting {self.host}:{self.port}")
        finally:
            sock.close()
        if len(resp) < 4:
            raise ModbusError(f"short response ({len(resp)}B)")
        if resp[0] != self.slave:
            raise ModbusError(f"slave mismatch: {resp[0]}")
        if crc16_modbus(resp[:-2]) != struct.unpack("<H", resp[-2:])[0]:
            raise ModbusError("CRC16 mismatch")
        func = resp[1]
        if func & 0x80:
            code = resp[2]
            raise ModbusError(f"exception {code} ({MB_EXC.get(code, '?')}) "
                              f"on func {func & 0x7F:#x}")
        return resp[2:-2]

    def read_holding(self, addr: int, count: int) -> List[int]:
        """FC03：读保持寄存器，返回 u16 列表。"""
        pdu = struct.pack(">BHH", FC_READ_HOLDING, addr, count)
        data = self._transact(pdu)
        if len(data) < 1 or data[0] != count * 2 or len(data) != 1 + count * 2:
            raise ModbusError(f"bad FC03 payload: {data.hex()}")
        return [struct.unpack(">H", data[1 + 2 * i:3 + 2 * i])[0]
                for i in range(count)]

    def write_single(self, addr: int, value: int) -> None:
        """FC06：写单个寄存器（回显校验）。"""
        pdu = struct.pack(">BHH", FC_WRITE_SINGLE, addr, value & 0xFFFF)
        data = self._transact(pdu)
        if data != pdu[1:]:
            raise ModbusError(f"FC06 echo mismatch: {data.hex()}")

    def write_multiple(self, addr: int, values: List[int]) -> None:
        """FC16(0x10)：写多个寄存器（回显地址+数量校验）。"""
        body = b"".join(struct.pack(">H", v & 0xFFFF) for v in values)
        pdu = struct.pack(">BHHB", FC_WRITE_MULTIPLE, addr, len(values),
                          len(body)) + body
        data = self._transact(pdu)
        if data != struct.pack(">HH", addr, len(values)):
            raise ModbusError(f"FC16 echo mismatch: {data.hex()}")


# ---------------------------------------------------------------- 0xF000 命令面

# 开关组 ID（旧上位机 CBCProtocol.cs EIOGroup 枚举序，设置页「IO 控制」下拉的选中值）
IO_GROUP_PWR_EN = 0      # 电源使能（上电）
IO_GROUP_MCU_PWR = 1     # 主控开机键（「测试板开机」）
IO_GROUP_MCU_KPCOL = 2   # 开机键+KPCOL 组合（「测试板进入下载模式」，调试用）
IO_GROUP_NUM = 3
IO_GROUP_INVALID = 0xFF

TOTAL_GPIO_LINE = 12     # 每块通讯板 12 路 DUT（旧码 TOTAL_GPIO_LINE）


def _batch_lines(batch: int, index: int) -> List[int]:
    """旧码 GetoutGroupData：12 路按 batch 数均分（余数给前面的批），
    第 index 批（1 起）返回板上线号 0..11 的子列表。"""
    if batch < 1 or index < 1 or index > batch:
        return []
    per, extra = divmod(TOTAL_GPIO_LINE, batch)
    if index <= extra:
        start = (index - 1) * (per + 1)
        count = per + 1
    else:
        start = extra * (per + 1) + (index - extra - 1) * per
        count = per
    end = TOTAL_GPIO_LINE if index == batch else start + count
    return list(range(start, end))


def build_key_batch_controls(group_id: int, batch: int, start_sec: int,
                             interval_sec: int, pulse_ms: int) -> List["IoControl"]:
    """旧码 GenerateIoSecuritySetPackage 移植：「测试板开机」分批按键包。

    语义（CBCProtocol.cs 实证）：
      - 12 路按 batch 分批，第 n 批比第 n-1 批晚 interval_sec 秒（错峰防浪涌）
      - 每路一条 IoControl：start_sec 后把线置 start_status，保持 pulse_ms 毫秒
        后自动恢复 —— 开机键组 startStatus=0（低有效按下），
        PWR_EN 电源组 startStatus=1（高有效上电）
      - 线序映射 group*4+numInGroup+1-1：旧治具 3 组×4 路的物理接线序
        （新测试盒接线若不同，改 _batch_lines 的映射即可）
    返回体经 CommBoard.io_security_set(cmd7，带防重放序列号) 下发。
    """
    controls: List[IoControl] = []
    sec = start_sec
    for i in range(1, batch + 1):
        for line in _batch_lines(batch, i):
            mapped = (line % 3) * 4 + line // 3     # 旧治具线序
            controls.append(IoControl(
                group_id=group_id, line=mapped,
                start_status=0 if group_id in (IO_GROUP_MCU_PWR,
                                               IO_GROUP_MCU_KPCOL) else 1,
                start_sec=sec, duration_msec=pulse_ms))
        sec += interval_sec
    return controls


@dataclass
class IoControl:
    """单路 IO 控制（8B = 4 寄存器）：毫秒级定时。"""
    group_id: int        # 开关组 ID（PWR_EN / MCU_PWR / MCU_KPCOL 等）
    line: int            # 线号 0..11（DUT 通道）
    start_status: int    # 0/1：动作目标状态
    start_sec: int = 0   # 延时启动（秒）
    duration_msec: int = 0xFFFF  # 持续时间（毫秒），0xFFFF=不自动恢复

    def pack(self) -> bytes:
        return struct.pack("<HBBHH", self.group_id, self.line,
                           self.start_status, self.start_sec,
                           self.duration_msec)


@dataclass
class IoGroupControl:
    """多组 IO 统一控制（8B = 4 寄存器）：秒级定时。"""
    group_id: int
    start_status: int
    end_status: int
    start_sec: int = 0
    duration_sec: int = 0xFFFF

    def pack(self) -> bytes:
        return struct.pack("<HBBHH", self.group_id, self.start_status,
                           self.end_status, self.start_sec, self.duration_sec)


class CommBoard:
    """一块通讯板的控制面。host = 板 IP（如 192.168.50.101）。"""

    def __init__(self, host: str, mb_port: int = 501, mb_slave: int = 1,
                 timeout: float = 1.0):
        self.mb = MbRtuUdpClient(host, mb_port, mb_slave, timeout)
        self._io_serial = 0

    def _command(self, cmd: int, param_regs: Optional[List[int]] = None) -> None:
        regs = [cmd] + list(param_regs or [])
        self.mb.write_multiple(REG_CMD, regs)

    def action_state(self) -> str:
        """读 0xF001 命令执行状态。"""
        return ACTION_STATE.get(self.mb.read_holding(REG_ACTION_STATE, 1)[0],
                                "UNKNOWN")

    # ---- 命令 ----

    def reboot(self) -> None:
        self._command(CMD_REBOOT)

    def save_config(self) -> None:
        self._command(CMD_SAVE_CONFIG)

    def ota(self, target_version: int) -> None:
        """OTA 升级请求；版本与板端相同会被拒（ACTION_ST_ERROR）。"""
        self._command(CMD_OTA, le_bytes_to_regs(struct.pack("<I", target_version)))

    def test_reset(self, timestamp: Optional[int] = None) -> None:
        """对时 + 复位测试（清 IO 队列、GPIO 恢复默认）。默认取当前时间。"""
        ts = int(time.time()) if timestamp is None else int(timestamp)
        self._command(CMD_TEST_RESET, le_bytes_to_regs(struct.pack("<I", ts)))

    def io_set(self, controls: List[IoControl]) -> None:
        """单路 IO 毫秒级控制（cmd5）。"""
        regs = le_bytes_to_regs(b"".join(c.pack() for c in controls))
        self._command(CMD_IO_SET, regs)

    def io_security_set(self, controls: List[IoControl],
                        serial: Optional[int] = None) -> None:
        """IO 安全分批控制（cmd7）：带防重放序列号，电源上下电用这个。

        序列号默认自增；与板端上次相同会被整包忽略。
        """
        if serial is None:
            self._io_serial = (self._io_serial + 1) & 0xFFFF
            serial = self._io_serial
        body = struct.pack("<H", serial) + b"".join(c.pack() for c in controls)
        self._command(CMD_IO_SECURITY_SET, le_bytes_to_regs(body))

    def multi_io_set(self, groups: List[IoGroupControl]) -> None:
        """多组 IO 秒级统一控制（cmd2）。"""
        regs = le_bytes_to_regs(b"".join(g.pack() for g in groups))
        self._command(CMD_MULT_IO_SET, regs)

    # ---- 便捷封装 ----

    def power_on_duts(self, lines: List[int], stagger_sec: int = 0,
                      group_id: int = IO_GROUP_PWR_EN) -> None:
        """分批上电：指定通道 PWR_EN 置 1，间隔 stagger_sec 秒错峰。"""
        ctrls = [IoControl(group_id=group_id, line=ln, start_status=1,
                           start_sec=i * stagger_sec)
                 for i, ln in enumerate(lines)]
        self.io_security_set(ctrls)

    def power_off_duts(self, lines: List[int],
                       group_id: int = IO_GROUP_PWR_EN) -> None:
        self.io_security_set([IoControl(group_id=group_id, line=ln,
                                        start_status=0) for ln in lines])

    def boot_key_batch(self, batch: int = 4, start_sec: int = 0,
                       interval_sec: int = 5, pulse_ms: int = 200,
                       group_id: int = IO_GROUP_MCU_PWR) -> None:
        """「测试板开机」：全板 12 路分批错峰按开机键（旧上位机
        GenerateIoSecuritySetPackage 语义，见 build_key_batch_controls）"""
        self.io_security_set(build_key_batch_controls(
            group_id, batch, start_sec, interval_sec, pulse_ms))

    def press_key(self, line: int, start_sec: int = 0, span_ms: int = 200,
                  group_id: int = IO_GROUP_MCU_PWR) -> None:
        """单路按键（旧码 DUT_EVT_SET_PWR_KEY 路径：老化后单颗补开机）"""
        self.io_security_set([IoControl(group_id=group_id, line=line,
                                        start_status=0, start_sec=start_sec,
                                        duration_msec=span_ms)])

    # ---- 电源直控（FC06 写保持寄存器，立即生效并锁存；推荐路径） ----

    def set_power_line(self, line: int, on: bool) -> None:
        """单路电源直控：写 PWR_EN 单路寄存器（0x83/0x87/…，1=上电 0=下电）。
        无序列号/定时器/回翻，硬件锁存。"""
        if line not in PWR_LINE_REG:
            raise ModbusError(f"无效线号: {line}（0..11）")
        self.mb.write_single(PWR_LINE_REG[line], 1 if on else 0)
        if on:
            # 2026-09-18 实证（TBSM02 抓包复刻）：只写寄存器不上电！
            # 上电必须在寄存器置 1 后再发 0xF000 执行命令（cmd5 IO_SET，
            # 参数 {groupId=3, line, startSec=1, durationMsec=8000}），
            # 硬件电源通路才真正闭合（LED 亮 ≠ DUT 上电）。断电只需寄存器清 0。
            self.mb.write_multiple(REG_CMD, [5, 3, line, 1, 8000])

    def set_power_group(self, mask: int) -> None:
        """整组电源直控：写 0xA2 位掩码（bit i = 线 i）。0x0FFF=整板 12 路上电。"""
        self.mb.write_single(REG_PWR_GROUP, mask & 0xFFFF)


# ---------------------------------------------------------------- 电源直控寄存器
# （DriverSwitch.c sSwitchReg，2026-09-17 真机验证）：FC06 写立即驱动 GPIO 并
# 锁存——无防重放序列号、无定时器、无 65s 回翻（cmd7 的三连坑全绕开）。
# 手动版调试的电源开关一律走这里；cmd7 保留给错峰按键等定时场景。
# 注意：读回路径（FC03）走的是固件缓存的状态结构体，vSwitchSetGpioStatus 从不
# 更新缓存（源码里那行被注释掉了）→ 读回不可信，电源状态由上位机记忆。

REG_PWR_GROUP = 0xA2          # PWR_EN 整组位掩码（bit i = 线 i，1=上电）
REG_MCU_PWR_GROUP = 0xA4      # MCU_PWR 整组（开机键）
REG_MCU_KPCOL_GROUP = 0xA6    # MCU_KPCOL 整组（下载模式）

# 线号 → 单路 PWR_EN 寄存器（线 0-7 步进 4；线 8-11 = 0x70-0x73）
PWR_LINE_REG = {0: 0x83, 1: 0x87, 2: 0x8B, 3: 0x8F,
                4: 0x93, 5: 0x97, 6: 0x9B, 7: 0x9F,
                8: 0x70, 9: 0x71, 10: 0x72, 11: 0x73}


# ---------------------------------------------------------------- 设备发现 / IP 分配

ASSIGN_PORT = 60000
ASSIGN_HEAD = 0xAF
ASSIGN_TAIL = 0xFE


def build_assign_req(target_id: int = 0, serial: Optional[int] = None,
                     ip: int = 0) -> bytes:
    """target_id=0 + ip=0 → 广播查询在线设备；target_id=<SN> + ip=<新IP> → 定向分配。"""
    if serial is None:
        serial = int(time.time() * 1000) & 0xFFFFFFFF
    cksum = (target_id + serial + ip) & 0xFFFFFFFF
    return struct.pack("<6I", ASSIGN_HEAD, target_id, serial, ip, cksum,
                       ASSIGN_TAIL)


def parse_assign_ack(data: bytes) -> Optional[dict]:
    """解析板端 ACK。固件 AssignAck 实为 5×u32=20B（head/deviceId/serial/checkSum/
    tail，AddrAssignService.c GenAck）；历史上位机按 24B 解析导致 ACK 全部丢弃，
    2026-09-17 真机实证修正为接受 20B（容忍 24B 旧格式）。"""
    if len(data) == 20:
        head, dev_id, serial, cksum, tail = struct.unpack("<5I", data)
    elif len(data) == 24:
        head, dev_id, serial, cksum, _, tail = struct.unpack("<6I", data)
    else:
        return None
    if head != ASSIGN_HEAD or tail != ASSIGN_TAIL:
        return None
    if (dev_id + serial) & 0xFFFFFFFF != cksum:
        return None
    return {"device_id": dev_id, "serial": serial}


def ip_to_u32(ip_str: str) -> int:
    """'192.168.50.101' → lwIP 小端序 u32（与固件 ip_addr_t.addr 一致）。"""
    return struct.unpack("<I", socket.inet_aton(ip_str))[0]


def discover(timeout: float = 3.0,
             broadcast_addrs: Optional[List[str]] = None,
             bind_ip: Optional[str] = None) -> List[dict]:
    """UDP 60000 广播发现通讯板，返回 [{'device_id','serial','addr'}]。

    broadcast_addrs 缺省 = ['255.255.255.255']；跨网段时可补 '192.168.50.255'。
    bind_ip：多网卡机器上绑定本机出口 IP 再发广播（2026-09-17 现场实证坑：
    直接发 255.255.255.255 时 Windows 会从主网卡发出，50 网段的板子收不到；
    且板子的 server_ip 学自"最后收到的广播包源 IP"——绑定 192.168.50.10 发
    定向广播既能让板子收到，又能把 server_ip 同步为该地址）。
    """
    if broadcast_addrs is None:
        broadcast_addrs = ["255.255.255.255"]
    serial = int(time.time() * 1000) & 0xFFFFFFFF
    req = build_assign_req(0, serial, 0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    found = {}
    try:
        if bind_ip:
            sock.bind((bind_ip, 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.5)
        for addr in broadcast_addrs:
            try:
                sock.sendto(req, (addr, ASSIGN_PORT))
            except OSError:
                pass
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, src = sock.recvfrom(2048)
            except socket.timeout:
                continue
            ack = parse_assign_ack(data)
            if ack:
                ack["addr"] = src[0]
                found[src[0]] = ack
    finally:
        sock.close()
    return list(found.values())


def assign_ip(device_sn: int, new_ip: str, timeout: float = 2.0,
              broadcast_addrs: Optional[List[str]] = None) -> bool:
    """给指定 SN 的板子分配 IP（发现之后第二步）。成功收到定向 ACK 返回 True。"""
    if broadcast_addrs is None:
        broadcast_addrs = ["255.255.255.255"]
    serial = int(time.time() * 1000) & 0xFFFFFFFF
    req = build_assign_req(device_sn, serial, ip_to_u32(new_ip))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.5)
        for addr in broadcast_addrs:
            try:
                sock.sendto(req, (addr, ASSIGN_PORT))
            except OSError:
                pass
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, _ = sock.recvfrom(2048)
            except socket.timeout:
                continue
            ack = parse_assign_ack(data)
            # 定向分配时板端回复 deviceId=0（一对一对话）
            if ack and ack["serial"] == serial:
                return True
    finally:
        sock.close()
    return False
