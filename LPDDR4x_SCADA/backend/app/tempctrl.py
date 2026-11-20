# -*- coding: utf-8 -*-
"""温控板 TCP 客户端 —— P3（协议来源：旧上位机 BLL/TempCtr/TempProtocol.cs）

帧格式（全小端）：
    CmdFlag  u32 = 0x5A4B4457 | CmdID u16 | CmdDataSize u16 | CmdData[N] | CRC8 u8
    CRC8 = 从第 0 字节到校验前一字节的累加和（mod 256），帧总长 = 9 + N

命令（TempProtocol.cs:19-27）：
    0x01 查询温度      响应: stateCode(=0x01 OK) + 24×i16 LE，温度 = (raw-400)/10 - 补偿
    0x02 查询风扇      响应: stateCode + 4×u16 **大端**（旧代码 fanBytes 交换字节序）
    0x03 设定温度      参数: i16 LE = 温度×10（所有 DUT 相同）
    0x04 设定风扇转速  参数: i16 LE
    0x05 温控开关      参数: u8（0x01 开 / 0x00 关）
    0x07 查询故障      响应: stateCode + 24×i16 + 3B 温控故障 + 1B 对齐 + 4B + 4B 风扇故障
    0x08 查询电压      响应: stateCode + 6×u16 LE 检测电压 + 6×u16 LE 分流电压
    0x09 设置 5V       参数: u8（1 开 / 0 关）
    0x0B 按 DUT 设温度（未实现，第一版不需要）

部署约定（memory.md §4.3）：IP 192.168.50.2+i，端口 64200~64204，每 Team 一块。
"""
from __future__ import annotations

import socket
import struct
from typing import List, Optional, Tuple

HEAD_WORD = 0x5A4B4457
STATE_OK = 0x01

CMD_QUERY_TEMP = 0x01
CMD_QUERY_FAN_SPEED = 0x02
CMD_SET_TEMP = 0x03
CMD_SET_FAN_SPEED = 0x04
CMD_ON_OFF = 0x05
CMD_QUERY_FAULT = 0x07
CMD_QUERY_VOLTAGE = 0x08
CMD_SET_VOLTAGE = 0x09

TEMP_DEVIATION = 400        # 温度偏差：raw-400 后 /10 = 摄氏度（最低 -40℃）
DUT_NUM = 24                # 每块温控板 24 路温控模块
FAN_NUM = 4                 # 4 个风扇
DETECT_VOL_CH = 3           # 3 路电压检测
POGO_PIN_NUM = 2            # 2 个 pogo pin


class TempCtrlError(Exception):
    pass


def _checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def encode_package(cmd_id: int, param: bytes = b"") -> bytes:
    pkg = struct.pack("<IHH", HEAD_WORD, cmd_id, len(param)) + param
    return pkg + bytes([_checksum(pkg)])


def decode_package(buf: bytes) -> Tuple[int, bytes, int]:
    """从缓冲区解析一帧，返回 (cmd_id, param, 消费字节数)。

    找不到头 / 长度不足 / 校验失败均抛 TempCtrlError；
    长度不足时调用方应继续收数据（用 NeedMoreData 区分）。
    """
    pos = buf.find(struct.pack("<I", HEAD_WORD))
    if pos < 0:
        raise TempCtrlError("frame head not found")
    buf = buf[pos:]
    if len(buf) < 9:
        raise NeedMoreData(f"only {len(buf)}B after head")
    _, cmd_id, param_len = struct.unpack("<IHH", buf[:8])
    if len(buf) < 9 + param_len:
        raise NeedMoreData(f"need {9 + param_len}B, have {len(buf)}B")
    frame = buf[:9 + param_len]
    if _checksum(frame[:-1]) != frame[-1]:
        raise TempCtrlError(f"checksum err: {frame.hex()}")
    return cmd_id, frame[8:-1], pos + 9 + param_len


class NeedMoreData(TempCtrlError):
    pass


def _check_state(param: bytes, min_len: int) -> None:
    if len(param) < min_len:
        raise TempCtrlError(f"param too short: {len(param)} < {min_len}")
    if param[0] != STATE_OK:
        raise TempCtrlError(f"device state code = {param[0]:#04x}")


def decode_temps(param: bytes,
                 compensation: Optional[List[float]] = None) -> List[float]:
    """0x01 响应 → 24 路摄氏温度。compensation = 每路温补（缺省全 0）。"""
    _check_state(param, 1 + 2 * DUT_NUM)
    comp = compensation or [0.0] * DUT_NUM
    out = []
    for i in range(DUT_NUM):
        raw = struct.unpack("<h", param[1 + 2 * i:3 + 2 * i])[0]
        out.append((raw - TEMP_DEVIATION) / 10.0 - comp[i])
    return out


def decode_fan_speeds(param: bytes) -> List[int]:
    """0x02 响应 → 4 路风扇转速（RPM）。注意：旧代码按大端解析。"""
    _check_state(param, 1 + 2 * FAN_NUM)
    return [struct.unpack(">H", param[1 + 2 * i:3 + 2 * i])[0]
            for i in range(FAN_NUM)]


def decode_faults(param: bytes) -> dict:
    """0x07 响应 → {'temp_faults': 3B 位图, 'fan_faults': 4B 位图}。"""
    _check_state(param, 1 + 2 * DUT_NUM + 3 + 1 + 4 + 4)
    off = 1 + 2 * DUT_NUM
    temp_faults = param[off:off + 3]
    off += 3 + 1 + 4           # 3B 温控故障 + 1B 对齐 + 4B 测试保留
    fan_faults = param[off:off + 4]
    return {"temp_faults": list(temp_faults), "fan_faults": list(fan_faults)}


def decode_voltages(param: bytes) -> dict:
    """0x08 响应 → {'detect': 6×u16 mV, 'shunt': 6×u16}（各 2 pogo × 3 路）。"""
    n = DETECT_VOL_CH * POGO_PIN_NUM
    _check_state(param, 1 + 4 * n)
    detect, shunt = [], []
    for i in range(n):
        detect.append(struct.unpack("<H", param[1 + 2 * i:3 + 2 * i])[0])
        shunt.append(struct.unpack("<H", param[1 + 2 * n + 2 * i:
                                                3 + 2 * n + 2 * i])[0])
    return {"detect": detect, "shunt": shunt}


class TempCtrlClient:
    """一块温控板的 TCP 短连接客户端（查询/设置一次一连接）。"""

    def __init__(self, host: str, port: int = 64200, timeout: float = 2.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def _transact(self, cmd_id: int, param: bytes = b"") -> bytes:
        req = encode_package(cmd_id, param)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        buf = b""
        try:
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            sock.sendall(req)
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                buf += chunk
                try:
                    got_cmd, got_param, _ = decode_package(buf)
                    if got_cmd != cmd_id:
                        raise TempCtrlError(
                            f"cmd echo mismatch: {got_cmd:#x} != {cmd_id:#x}")
                    return got_param
                except NeedMoreData:
                    continue
        except socket.timeout:
            raise TempCtrlError(f"timeout waiting {self.host}:{self.port}")
        finally:
            sock.close()
        raise TempCtrlError(f"connection closed, incomplete frame: {buf.hex()}")

    # ---- 查询 ----

    def query_temps(self,
                    compensation: Optional[List[float]] = None) -> List[float]:
        return decode_temps(self._transact(CMD_QUERY_TEMP), compensation)

    def query_fan_speeds(self) -> List[int]:
        return decode_fan_speeds(self._transact(CMD_QUERY_FAN_SPEED))

    def query_faults(self) -> dict:
        return decode_faults(self._transact(CMD_QUERY_FAULT))

    def query_voltages(self) -> dict:
        return decode_voltages(self._transact(CMD_QUERY_VOLTAGE))

    # ---- 设置 ----

    def set_temp(self, celsius: float) -> bytes:
        """设定所有 DUT 目标温度（℃）。"""
        return self._transact(CMD_SET_TEMP,
                              struct.pack("<h", int(round(celsius * 10))))

    def set_fan_speed(self, speed: int) -> bytes:
        return self._transact(CMD_SET_FAN_SPEED,
                              struct.pack("<h", int(speed)))

    def set_on_off(self, on: bool) -> bytes:
        return self._transact(CMD_ON_OFF, bytes([0x01 if on else 0x00]))

    def set_5v(self, on: bool) -> bytes:
        return self._transact(CMD_SET_VOLTAGE, bytes([0x01 if on else 0x00]))
