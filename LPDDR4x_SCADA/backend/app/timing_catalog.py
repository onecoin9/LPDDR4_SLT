"""MT6785 writable timing fields. Units are fixed per field, never inferred from UI text."""
from decimal import Decimal, InvalidOperation

TIMING_SCHEMA = 1
TIMING_CAPABILITY = "T1:"
CATALOG = []


def _add(key, reg, field, width, zh, en, *, ns=False):
    CATALOG.append(dict(id=len(CATALOG), key=key, register=reg, field=field,
                        width=width, min=60 if ns else 0, max=400 if ns else (1 << width) - 1,
                        unit="ns" if ns else ("flag" if width == 1 else "register"),
                        scale=100 if ns else 1, purposeZh=zh, purposeEn=en))


def _pair(key, reg, width, zh, en, *, half_field=None, half_reg="SHU_AC_TIME_05T"):
    _add(key, reg, f"{reg}_{key}", width, zh, en)
    half_field = half_field or f"SHU_AC_TIME_05T_{key}_05T"
    _add(key + "_05T", half_reg, half_field, 1,
         f"{key} 的半周期修正位：0关闭，1启用；修正方向由控制器字段定义",
         f"Half-cycle adjustment for {key}: 0 off, 1 on; direction follows the controller field")


_pair("TRCD", "SHU_ACTIM0", 4, "激活到读写命令的等待计数", "ACTIVATE to READ/WRITE wait counter")
_pair("TRRD", "SHU_ACTIM0", 3, "不同Bank之间连续激活的等待计数", "Wait counter between ACTIVATE commands to different banks")
_pair("TWR", "SHU_ACTIM0", 5, "写恢复等待计数；需与器件nWR配置配合", "Write-recovery counter; must agree with the device nWR setting", half_field="SHU_AC_TIME_05T_TWR_M05T")
_pair("TWTR", "SHU_ACTIM0", 4, "写转读等待计数；包含平台低频修正后的最终值", "Final WRITE-to-READ counter, after platform low-frequency adjustments", half_field="SHU_AC_TIME_05T_TWTR_M05T")
_pair("TRC", "SHU_ACTIM1", 5, "同一Bank两次激活之间的等待计数", "Wait counter between two ACTIVATE commands to the same bank")
_pair("TRAS", "SHU_ACTIM1", 4, "Bank激活到预充电的等待计数", "ACTIVATE-to-PRECHARGE wait counter")
_pair("TRP", "SHU_ACTIM1", 4, "单Bank预充电到再次激活的等待计数", "Single-bank PRECHARGE-to-ACTIVATE wait counter")
_pair("TRPAB", "SHU_ACTIM1", 3, "全Bank预充电后的等待计数", "Wait counter after all-bank PRECHARGE")
_pair("TFAW", "SHU_ACTIM2", 5, "四次激活命令窗口计数", "Four-ACTIVATE window counter")
_pair("TR2W", "SHU_ACTIM2", 4, "读转写等待计数，覆盖ODT分支选定的值", "READ-to-WRITE counter, overriding the selected ODT branch")
_pair("TRTP", "SHU_ACTIM2", 3, "读到预充电的等待计数", "READ-to-PRECHARGE wait counter")
_add("EARLYCKECNT", "SHU_ACTIM2", "SHU_ACTIM2_EARLYCKECNT", 3, "提前控制CKE的等待计数", "Counter for early CKE control")
_pair("TXP", "SHU_ACTIM2", 3, "退出低功耗到有效命令的等待计数", "Power-down exit to valid-command wait counter")
_add("REFCNT", "SHU_ACTIM3", "SHU_ACTIM3_REFCNT", 8, "刷新周期计数；与温度和刷新策略共同决定刷新间隔", "Refresh-period counter; depends on temperature and refresh policy")
_add("TRFC", "SHU_ACTIM3", "SHU_ACTIM3_TRFC", 8, "全Bank刷新时间；按当前频率换算，未单独设置TXREFCNT时自动推导其值", "All-bank refresh time; converted at the current clock, also deriving TXREFCNT unless explicitly set", ns=True)
_add("TR2MRR", "SHU_ACTIM3", "SHU_ACTIM3_TR2MRR", 4, "读到模式寄存器读的等待计数", "READ-to-mode-register-READ wait counter")
_add("MANTMRR", "SHU_ACTIM3", "SHU_ACTIM3_MANTMRR", 4, "手动模式寄存器读的控制器间隔计数", "Controller interval counter for manual mode-register READ")
_add("TRFCPB", "SHU_ACTIM3", "SHU_ACTIM3_TRFCPB", 8, "单Bank刷新时间，按当前频率转换", "Per-bank refresh time, converted at the current clock", ns=True)
_add("TZQCS", "SHU_ACTIM4", "SHU_ACTIM4_TZQCS", 8, "ZQ校准等待计数；此字段没有半周期修正位", "ZQ-calibration wait counter; this field has no half-cycle bit")
_add("REFCNT_FR_CLK", "SHU_ACTIM4", "SHU_ACTIM4_REFCNT_FR_CLK", 8, "刷新参考时钟计数，需与REFCNT共同设置", "Refresh reference-clock counter; coordinate with REFCNT")
_add("TXREFCNT", "SHU_ACTIM4", "SHU_ACTIM4_TXREFCNT", 10, "退出自刷新相关的内部等待计数；不是直接的ns数值", "Internal self-refresh-exit counter; not a direct nanosecond value")
_add("TMRR2W", "SHU_ACTIM5", "SHU_ACTIM5_TMRR2W", 4, "模式寄存器读到普通写的等待计数", "Mode-register READ to normal WRITE wait counter")
_pair("TWTPD", "SHU_ACTIM5", 5, "写之后进入低功耗的等待计数", "WRITE-to-power-down wait counter", half_field="SHU_AC_TIME_05T_TWTPD_M05T")
_pair("TR2PD", "SHU_ACTIM5", 5, "读之后进入低功耗的等待计数", "READ-to-power-down wait counter")
_pair("TPBR2PBR", "SHU_ACTIM5", 8, "两次单Bank刷新之间的等待计数", "Wait counter between per-bank REFRESH commands", half_field="SHU_ACTIM5_TPBR2PBR_05T", half_reg="SHU_ACTIM5")
for _key, _width, _zh, _en in (
    ("XRTW2W", 5, "跨Rank写转写等待计数", "Cross-rank WRITE-to-WRITE wait counter"),
    ("XRTW2R", 4, "跨Rank写转读等待计数", "Cross-rank WRITE-to-READ wait counter"),
    ("XRTR2W", 4, "跨Rank读转写等待计数", "Cross-rank READ-to-WRITE wait counter"),
    ("XRTR2R", 5, "跨Rank读转读等待计数", "Cross-rank READ-to-READ wait counter"),
):
    _add(_key, "SHU_ACTIM_XRT", "SHU_ACTIM_XRT_" + _key, _width, _zh, _en)
_add("FSPCHG_PRDCNT", "SHU_CONF2", "SHU_CONF2_FSPCHG_PRDCNT", 8, "频点切换的等待计数", "Frequency-set-point change wait counter")
_add("MRW_INTV", "SHU_SCINTV", "SHU_SCINTV_MRW_INTV", 5, "控制器模式寄存器写间隔；不直接等同JEDEC的tMRW时间", "Controller mode-register WRITE interval; not a direct JEDEC tMRW time")
_add("TZQLAT2", "SHU_SCINTV", "SHU_SCINTV_TZQLAT2", 5, "ZQ校准相关的延迟计数", "ZQ-calibration latency counter")
_add("CKEPRD", "SHU_CKECTRL", "SHU_CKECTRL_CKEPRD", 3, "CKE脉宽计数", "CKE pulse-width counter")
_add("CMDCKE", "SHU_CKECTRL", "SHU_CKECTRL_CMDCKE", 3, "有效命令与CKE动作之间的等待计数", "Counter between a valid command and a CKE action")
_add("CKELCKCNT", "CKECTRL", "CKECTRL_CKELCKCNT", 3, "CKE拉低后继续提供有效时钟的计数", "Valid-clock counter after CKE goes LOW")

BY_KEY = {r["key"]: r for r in CATALOG}
LEGACY_KEYS = set("TDQS2DQ TRCD TRP TRAS TWR TXRefCnt TRPAB TRC TRFC TRFCPB TXP TRTP TWTR TPBR2PBR TPBR2ACT TR2MRW TW2MRW TMRR2MRW TMRW TMRD TMRWCKEL TPDE TPDX TMRRI TRRD TFAW TZQCS TRAS时序 TWR时序 TXRefCnt时序".split())


def wire_value(row, value):
    """Validate a customer value and return the exact integer wire representation."""
    try:
        n = Decimal(str(value).strip())
    except (ValueError, InvalidOperation):
        raise ValueError("number") from None
    if not n.is_finite():
        raise ValueError("number")
    if not Decimal(row["min"]) <= n <= Decimal(row["max"]):
        raise ValueError("range")
    if n != n.quantize(Decimal("0.01") if row["scale"] == 100 else Decimal(1)):
        raise ValueError("number")
    return int(n * row["scale"])


def encode_profile(profile):
    """Compact register contract; absent fields inherit firmware defaults."""
    selected = []
    if profile.get("pl1Enabled"):
        for r in profile.get("params", []):
            name = str(r.get("name", "")).strip()
            if r.get("checked") and name in BY_KEY:
                field = BY_KEY[name]
                selected.append((field["id"], wire_value(field, r.get("value", ""))))
    return ",".join(f"{key}:{value}" for key, value in sorted(selected))


def requires_capability(cfg):
    return any(line.split("=", 1)[0].strip().upper() == "TIMINGREGV" for line in cfg.splitlines() if "=" in line)


def firmware_error(cfg, version):
    versions = [line.split('=',1)[1].strip() for line in cfg.splitlines()
                if '=' in line and line.split('=',1)[0].strip().upper() == 'TIMINGREGV']
    identity = str(version).replace("\x00", "").strip()
    if '3' in versions:
        return None if identity.startswith('T3:') else 'timing_firmware_update_required'
    if '2' in versions:
        return None if identity.startswith(('T2:', 'T3:')) else 'timing_firmware_update_required'
    if requires_capability(cfg) and not identity.startswith((TIMING_CAPABILITY,'T2:','T3:')):
        return 'timing_firmware_update_required'
    return None
