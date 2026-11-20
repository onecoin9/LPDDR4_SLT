"""应用层协议：hsg 0xAF 帧编解码（HsgCodec）——P2 实现。

帧格式（两份权威源码逐字节核对一致）：
  `0xAF | lenL | lenH | 角色 | cmd | data[len] | checksum | 0xEF`
  - len 为 u16 **小端**，=data 长度，总帧长 = len + 7
  - 角色：0x00=上位机(server) / 0x01=下位机(slave)
  - checksum = 0x55 XOR 逐个 data 字节
权威定义（内部工程源码，此处仅记录文件名）：
  - DutProtocol.cs（EncodeCmdPackage/DecodeCmdPackage）
  - hsg_device_protocol.c（send_command_with_ack/receive_config_with_ack，platform-mt6785 preloader）

命令字与载荷：
  PC→DUT  0x15 START_TEST   data = 整份 .cfg 文本（key=value\\n，见 cfg.py）
          ACK 帧           len=2 data=[0x00,status]，checksum=0x55^status（DUT 收到 0x15 后回）
  DUT→PC  0x10 READY        16B：apHWCode/apHWSubCode/apHWVer/apSWVer(各 u16 LE) + sfData[4] + sfVer[4]（ASCII）
          0x11 DRAM 信息    5B：总容量Gb / R0容量 / R0 Die / R1容量 / R1 Die
          0x16 FAIL         2B 状态码 LE（0=PASS, 01=校验错, 02=信号失败, 03=无效设置/容量校验, 04=初始化失败）
          0x17 PASS/DONE    2B 状态码 LE，0=成功
          0x18 过程数据     头{instanceId u8, dataType u8} + 载荷；DT_STRING=0/DT_UBYTE=1/DT_USHORT=2/DT_UINT=4
                             本工程扩展约定（旧上位机不解释 instanceId）：instanceId=1 → DT_STRING 载荷为
                             Progress 的 JSON；其余 → 文本日志行。

保留未实现（2026-09-03 用户拍板删除死路径；完整工程侧 2026-09-02 已实证 DUT 固件
PL/LK/Android 三层均不发送、不接收、不定义 0x12/0x13——旧上位机的这两帧协议在本
DUT 上永远不会有对端）：
  - 0x12 请求/应答老化时间（原 AgingTimeRequest/AgingTimeAck）
  - 0x13 唤醒按键请求（原 PwrKeySet）
  常量 CMD_AGING_REQ/CMD_PWR_KEY 保留仅作帧号占位，编解码与应答逻辑已移除；
  若未来固件实现，按 git 历史恢复 connection/protocol 的对应块。

本层不承载的语义（映射到其它通道）：
  - 运行日志：真实链路走通讯板转发的 UDP 63001 日志通道（见 logchannel.py），不经 0x18；
  - 心跳：真实协议无心跳命令，DUT 上电发一次 0x10 后静默——HsgCodec.encode(Heartbeat) 返回 None；
    mock 用周期 0x10 模拟保活。链路活性 = 会话 last_seen（connection.py）。
  - 停止测试：无协议命令，P3 经通讯板 Modbus 复位/下电实现。
"""

import json
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

HEAD = 0xAF
TAIL = 0xEF
ROLE_SERVER = 0x00
ROLE_SLAVE = 0x01

CMD_READY = 0x10
CMD_DRAM_INFO = 0x11
CMD_AGING_REQ = 0x12
CMD_PWR_KEY = 0x13
CMD_START_TEST = 0x15
CMD_FAIL = 0x16
CMD_DONE = 0x17
CMD_RECORD = 0x18

DT_STRING, DT_UBYTE, DT_USHORT, DT_UINT = 0x00, 0x01, 0x02, 0x04

# 0x16/0x17 状态码 → 失败描述。
# 三层来源合一（2026-08-31 按旧码核对）：
# - 固件 hsg_device_protocol.h 仅定义 0x00/0x01(addr_scan)/0x03(density)；
# - 旧上位机 DutProtocol STATUS_*（0x01 checksum / 0x02 signal / 0x03 invalid
#   setting / 0x04 init fail）与 DutMaster ERR_CODE_*（0x05 温控 / 0x06 超时 /
#   0x07 FAIL2 / 0x08 取消 / 0x09 环境）；
# - StateCode 0xF7-0xFE 环境/链路类（DutMaster.StateMachine.cs:141-155）。
# 语义注意：旧上位机对 0x17 只认 code==0 为 PASS（非 0 忽略等超时）；对 0x16
# code==0 记 FAIL1（成功有瑕疵/大电流）。本 codec 保持更严格的防御语义：
# 0x17 非 0 → FAIL(code 名)；0x16 code==0 → generic_fail(FAIL1)。
STATUS_TEXT = {
    0x00: "generic_fail",        # 仅 0x16 会用到（0x17 的 0 = PASS）
    0x01: "addr_scan_fail",      # 固件：地址扫描失败（旧上位机称 checksum_error）
    0x02: "signal_fail",
    0x03: "density_check_fail",  # 固件：容量校验失败（旧上位机称 invalid_setting）
    0x04: "init_fail",
    0x05: "temp_abnormal",       # ERR_CODE_TEMP_BAD
    0x06: "timeout",             # ERR_CODE_TIMEOUT
    0x07: "fail2",               # ERR_CODE_FAIL2
    0x08: "cancel",              # ERR_CODE_CANCEL
    0x09: "env_abnormal",        # ERR_OTHER_ENV_BAD
    0x0A: "mr_check_fail",       # 固件（2026-08-31 新增）：MR 读回值与产品档案设定值不符
    0xF7: "temp_comm_error",     # SCODE_TEMP_CONNECT_ERROR
    0xF8: "fan_error",           # SCODE_TEMP_FUN_ERROR
    0xF9: "temp_mainboard_error",
    0xFA: "temp_not_reached",    # SCODE_TEMP_ERROR
    0xFB: "commboard_timeout",   # SCODE_TB_COMMUNICATE_ERROR
    0xFC: "aging_log_fail",      # SCODE_RUNIN_FAILE（外部老化日志触发失败）
    0xFD: "dut_conn_timeout",    # SCODE_DUT_CONN_TIMEOUT
    0xFE: "dut_reboot",          # SCODE_DUT_REBOOT
    0xFF: "invalid",
}


def _status_name(code: int) -> str:
    return STATUS_TEXT.get(code & 0xFFFF, f"status_0x{code & 0xFFFF:04X}")


# ---------------------------------------------------------------- 语义消息：上位机 → DUT

@dataclass
class Heartbeat:
    """链路探测。真实协议无对应命令——encode 返回 None，不发线包。"""


@dataclass
class StartTest:
    """启动测试（0x15）：data = 整份 .cfg 文本"""
    cfg: str


@dataclass
class StopTest:
    """停止测试：无协议命令（P3 经通讯板复位/下电），encode 返回 None"""
    reason: str = ""


@dataclass
class Ack:
    """对 DUT 命令的 ACK（len=2，data=[0x00, status]）"""
    cmd: int
    status: int = 0


@dataclass
class AgingTimeAck:
    """保留未实现：0x12 应答（DUT 固件不发送 0x12，此应答永不触发；见模块 docstring）"""
    minutes: int


# ---------------------------------------------------------------- 语义消息：DUT → 上位机

@dataclass
class Ready:
    """0x10：DUT 上电就绪 + 版本信息"""
    apHWCode: int = 0
    apHWSubCode: int = 0
    apHWVer: int = 0
    apSWVer: int = 0
    sfData: bytes = b""
    sfVer: bytes = b""
    identity: str = ""

    @property
    def version(self) -> str:
        if self.identity:
            return self.identity
        return f"{self.sfData.decode('ascii', 'replace')}_{self.sfVer.decode('ascii', 'replace')}"


@dataclass
class DramInfo:
    """0x11：DRAM 容量/Rank/Die 信息"""
    totalGb: int = 0
    rank0Gb: int = 0
    rank0Die: int = 0
    rank1Gb: int = 0
    rank1Die: int = 0

    def __str__(self):
        return f"容量{self.totalGb}Gb R0:{self.rank0Gb}Gb×{self.rank0Die}Die R1:{self.rank1Gb}Gb×{self.rank1Die}Die"


@dataclass
class AgingTimeRequest:
    """0x12：DUT 请求老化时长（载荷 2B，旧上位机忽略内容直接应答）"""


@dataclass
class AgingTimeAnswer:
    """0x12 应答：老化分钟数（旧码 GenerateAginTimeAckPackage：载荷 = BE u16）"""
    minutes: int = 0

    def encode_frame(self) -> bytes:
        hi = (self.minutes >> 8) & 0xFF
        lo = self.minutes & 0xFF
        return build_frame(ROLE_SERVER, CMD_AGING_REQ, bytes([hi, lo]))


@dataclass
class PwrKeySet:
    """0x13：DUT 请求 startSec 秒后按开机键 span100ms×100 毫秒
    （旧码 DecodePwrKeySetPackage：data[0]=startSec, data[1]=span×0.1s）"""
    startSecond: int = 0
    span100ms: int = 0


@dataclass
class Progress:
    """测试进度（承载于 0x18 instanceId=1 的 DT_STRING JSON——本工程扩展约定）"""
    step: str
    stage: str                  # 软件执行阶段：PL / LK / APK
    progress: float             # 0-100，整次测试的百分比
    durationSec: float
    countdownSec: float


@dataclass
class DutLog:
    """DUT 记录行（0x18 普通 DT_STRING；运行日志主通道为 UDP 63001）"""
    level: str
    msg: str


@dataclass
class TestDone:
    """测试结束（0x17 状态 0 → PASS；0x16 或 0x17 非 0 → FAIL）"""
    result: str                 # PASS / FAIL
    failItem: str = ""
    durationSec: float = 0.0    # 帧内无时长，由会话侧计算（>0 时为 mock/显式提供）


class BaseCodec(ABC):
    """编解码器接口。UDP 数据报天然有边界，decode 以单报文为单位。"""

    @abstractmethod
    def encode(self, msg) -> Optional[bytes]:
        """语义消息 → 线格式；本协议不承载的消息（心跳/停止）返回 None"""

    @abstractmethod
    def decode(self, data: bytes) -> Optional[Any]:
        """线格式 → 语义消息；无法解析返回 None（由调用方丢弃并计错）"""


def build_frame(role: int, cmd: int, payload: bytes) -> bytes:
    """按权威格式组帧：0xAF | lenL | lenH | role | cmd | data | xor | 0xEF"""
    n = len(payload)
    checksum = 0x55
    for b in payload:
        checksum ^= b
    return bytes([HEAD, n & 0xFF, (n >> 8) & 0xFF, role, cmd]) + payload + bytes([checksum, TAIL])


def parse_frame(data: bytes):
    """解帧：返回 (cmd, payload) 或 None。

    校验：帧头/帧尾/长度/校验和。角色不在此过滤（HsgCodec.decode 按 PC 视角要求 0x01）。
    """
    if len(data) < 7 or data[0] != HEAD or data[-1] != TAIL:
        return None
    n = data[1] | (data[2] << 8)
    if len(data) != n + 7:
        return None
    payload = data[5:5 + n]
    checksum = 0x55
    for b in payload:
        checksum ^= b
    if checksum != data[5 + n]:
        return None
    return data[4], payload


class HsgCodec(BaseCodec):
    """0xAF 帧协议编解码（后端=PC/server 视角）。"""

    # ---- PC → DUT ----

    def encode(self, msg) -> Optional[bytes]:
        if isinstance(msg, StartTest):
            return build_frame(ROLE_SERVER, CMD_START_TEST, msg.cfg.encode("utf-8"))
        if isinstance(msg, Ack):
            return build_frame(ROLE_SERVER, msg.cmd, bytes([0x00, msg.status & 0xFF]))
        # 0x12 AgingTimeAck 应答已随死路径移除（DUT 不发送 0x12；见模块 docstring）
        if isinstance(msg, (Heartbeat, StopTest)):
            return None        # 真实协议不承载（见模块 docstring）
        return None

    # ---- DUT → PC ----

    def decode(self, data: bytes):
        parsed = parse_frame(data)
        if parsed is None:
            return None
        cmd, payload = parsed
        if data[3] != ROLE_SLAVE:      # PC 只接受来自下位机的帧
            return None

        if cmd == CMD_READY and len(payload) == 16:
            if payload.startswith((b"T1:", b"T2:", b"T3:")):
                try:
                    return Ready(identity=payload.rstrip(b"\x00").decode("ascii", "strict"))
                except UnicodeDecodeError:
                    return None
            hw, sub, hv, sw = struct.unpack_from("<HHHH", payload, 0)
            return Ready(hw, sub, hv, sw, payload[8:12], payload[12:16])
        # DUT 对 0x15 的 ACK（receive_config_with_ack 回 AF 02 00 01 15 ss 00 ..）
        if cmd == CMD_START_TEST and len(payload) == 2:
            return Ack(cmd=cmd, status=payload[0] | (payload[1] << 8))
        if cmd == CMD_DRAM_INFO and len(payload) == 5:
            return DramInfo(*payload)
        # 0x12/0x13（2026-09-19 恢复：与旧上位机 DutMaster.RecvDataHandle 逐条对齐——
        # 0x12 应答 AgingTime、0x13 转通讯板按键，属测试链时序控制的一部分）
        if cmd == CMD_AGING_REQ and len(payload) >= 2:
            return AgingTimeRequest()
        if cmd == CMD_PWR_KEY and len(payload) == 2:
            return PwrKeySet(startSecond=payload[0], span100ms=payload[1])
        if cmd == CMD_DONE and len(payload) == 2:
            code = payload[0] | (payload[1] << 8)
            if code == 0:
                return TestDone(result="PASS")
            return TestDone(result="FAIL", failItem=_status_name(code))
        if cmd == CMD_FAIL and len(payload) == 2:
            code = payload[0] | (payload[1] << 8)
            return TestDone(result="FAIL", failItem=_status_name(code))
        if cmd == CMD_RECORD and len(payload) >= 2:
            instance_id, data_type = payload[0], payload[1]
            body = payload[2:]
            if instance_id == 1 and data_type == DT_STRING:
                # 本工程扩展：进度 JSON
                try:
                    obj = json.loads(body.decode("utf-8"))
                    return Progress(step=str(obj.get("step", "")),
                                    stage=str(obj.get("stage", "")),
                                    progress=float(obj.get("progress", 0.0)),
                                    durationSec=float(obj.get("durationSec", 0.0)),
                                    countdownSec=float(obj.get("countdownSec", 0.0)))
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                    pass
            if data_type == DT_STRING:
                return DutLog("INFO", body.decode("utf-8", "replace"))
            # DT_UBYTE/USHORT/UINT 过程数组：P4 按测试项解释，暂以十六进制摘要记日志
            return DutLog("INFO", f"record dt=0x{data_type:02X} n={len(body)} "
                                  f"{body.hex(' ', 8)[:96]}")
        return None
