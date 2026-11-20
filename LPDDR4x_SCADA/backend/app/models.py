"""REST 请求体模型（Pydantic）。

字段名与前端 `frontend/src/types/dut.ts` 的 SessionConfig 等契约一一对应，
禁止擅改（见 SSOT agent.md §5.3）。
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class IoControlConfig(BaseModel):
    """IO 控制（设置页下拉，2026-09-07 按旧上位机 SettingForm「无操作/测试板开机/
    测试板进入下载模式」原样移植；语义 = 旧码 CBCProtocol.cs EIOGroup）。

    action:
      none       = 无操作（上电后直接等 0x10，不碰开机键）
      power_key  = 测试板开机（上电后全板 12 路分批错峰按开机键 MCU_PWR）
      download   = 测试板进入下载模式（开机键+KPCOL，调试/刷机用）
    仅在通讯板启用（config.yaml commboard.enabled: true）时生效；
    batch/startDelaySec/intervalSec/pulseMs 对应旧设置页
    每批路数/开始延迟(秒)/批间隔(秒)/按键时长(毫秒)。
    """
    action: str = Field("none", pattern="^(none|power_key|download)$")
    batch: int = Field(4, ge=1, le=12)          # 每批路数（12 路分几批）
    startDelaySec: int = Field(0, ge=0, le=600)  # 首批延迟（秒）
    intervalSec: int = Field(5, ge=0, le=600)    # 批间隔（秒）
    pulseMs: int = Field(200, ge=10, le=10000)   # 按键时长（毫秒）


class MachineConfig(BaseModel):
    """机台表单（POST /api/config）——批次标识 = 工单号-LOT号。
    profile = 所选产品的 ProductProfile JSON（frontend/src/types/product.ts 契约，
    字段原样透传），2026-08-28 新增可选字段：后端据此编译 .cfg 并按
    <产品名>.json 落盘（products/ 目录）；缺省/旧客户端不传 → 沿用基线 cfg。
    ioControl = IO 控制选项（2026-09-07，旧上位机语义）；缺省不传 = 无操作。"""
    product: str = ""
    workOrder: str = ""
    lotNo: str = ""
    operator: str = ""
    profile: Optional[dict] = None
    ioControl: Optional[IoControlConfig] = None
    settingsRevision: Optional[str] = None


class StartBody(BaseModel):
    """POST /api/test/start —— 工程师单站测试：指定 site（slots 可省略=该站全部在线空闲通道）；
    只给 slots 作用于 SITE 1；两者都省 = 全部 site 的在线空闲通道（操作员"确定"）"""
    site: Optional[int] = None
    slots: Optional[List[int]] = None


class StopBody(BaseModel):
    """POST /api/test/stop —— site 语义同 start；全省 = 全部测试中的通道（"结束"）"""
    site: Optional[int] = None
    slots: Optional[List[int]] = None


class SweepStartBody(BaseModel):
    """POST /api/sweep/start —— 扫描主轴 = profile.params 中填了起始/步进/结束
    且勾选的那一行（有且仅有一个）。quick=True 每点仅 PL+LK 快测。"""
    profile: dict
    site: Optional[int] = None
    slots: Optional[List[int]] = None
    quick: bool = True
    stop_on_fail: bool = False
