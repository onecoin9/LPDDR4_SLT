"""ProductProfile/默认参数 → .cfg 文本编译（0x15 载荷）。

.cfg = INI 风格 key=value 文本，下位机 hsg_device_config_decode 逐行解析
（键名大小写不敏感，未知键静默忽略——hsg_device_protocol.c:551-650 实证）。
配置来源：config.yaml 的 cfg_defaults 为基线（工程级），前端随「确定」上传的
ProductProfile JSON 覆盖其上（产品级，见 cfg_from_profile）。

同时提供：
- stages_from_cfg()：按 cfg 推导软件执行阶段序列 PL→LK→APK
  （PL=preloader 容量校验+分块写读；LK 需要 PatternTest 或 MemTester；
   APK 需要 MemTester/DvfsTest/AgingTime）——与 mt6785 三级测试链语义一致。

ProductProfile 语义映射（v1，2026-08-28；契约 = frontend/src/types/product.ts）：
  channels{ch1,ch2} + rankEnabled + rankCapacityGb[2](GB)
      → Channel{A,B}_Rank{0,1}_Enable/Size（Size 单位 Gb，GB×8；通道未启用
        或容量 0 → Enable=0。现行固件无「通道整体开关」键，用双 Rank 全关表达）
  pl1Enabled + params[]（勾选项）
      → 测试频率(M)→Freq；VDD1(mV)/VDD2H(mV)/VDDQ(mV)→VDD1/VDD2/VDDQ；
        时序参数名→同名 cfg 键（TRAS时序→TRAS 等三个除外）。
        [AC-TIM 2026-10-13] 产品级 timingUnit 字段（缺省 0）：0=增量ns（默认，
        不下发 TIMING_UNIT）；2=MCK 原始值（下发 TIMING_UNIT=2，直接项按半周期
        格点整数编译；TRFC 族仍恒绝对 ns——固件注入点 B 固定语义）。
        unsupported 时序键（平台无数值寄存器位域的 10 个）编译时告警跳过。
        固件四键 VDD1/VDD2/VDD2L/VDDQ（VDD2L 2026-09-03 接线 D4[2]，原恒 0）。
        VDD 超合理范围视为量纲可疑（产品配置截图为 10mV 显示单位的历史遗留），
        保留基线值并记告警，不做隐式 ×10 换算——量纲待用户/工程师确认。
  pl2Enabled=false → MemTester=0（memtester 阶段交由其余键决定）。
  mr{ch1,ch2}（按通道分组；无勾选项，行值非空即下发校验）→
      Channel{A,B}_MR{5..8}_2=期望值
      （int，支持 0x 前缀，整寄存器低 8 位比对；期望值由客户按颗粒规格书配置。
        下发条件 = 值合法 && 对应通道启用（CHn 启用 = 颗粒的通道配置）。
        固件 PL 阶段按通道逐启用 Rank MRR 读回 MR5/6/7/8 与期望值比对，
        不符发 0x16 状态码 0x0A mr_check_fail——颗粒身份/容量校验，贴错料早期拦截）。
  pl2.patterns[] → P2Mask=0x<hex>（2026-09-11 HSG-P2 接入）：
      位编号表与固件 memtester.c tests[] 严格同序（唯一真相源在固件侧注释），
      按勾选位合成 u64 掩码经 cfg → preloader → boot tag → LK cmdline →
      Android memtest.sh（MEMTESTER_TEST_MASK）。全部未勾选/未启用 → 不下发键，
      固件按"无键=全部执行"处理（向后兼容）。
  Density/DieNum/PatternTest/DvfsTest/AgingTime/Mode/LOG_TO_UART1
      → 产品 cfgOverrides 覆盖 config.yaml 基线；只接受登记的基础键。
"""

import re
from typing import Dict, List, Tuple

# PL2 pattern 位表（名称 → 固件测试表位号；与 memtester.c tests[] 顺序同步维护，
# 新增测试项只能在表尾追加，禁止插入/重排。Stuck Address 不受掩码控制）。
_P2_BIT_BY_NAME: Dict[str, tuple] = {
    # S1 基础 15（bit 0-14）
    "test_random_value": (0,),
    "test_xor_comparison": (1,),
    "test_sub_comparison": (2,),
    "test_mul_comparison": (3,),
    "test_div_comparison": (4,),
    "test_or_comparison": (5,),
    "test_and_comparison": (6,),
    "test_seqinc_comparison": (7,),
    "test_solid_bit": (8,),
    "test_block_sequential": (9,),
    "test_checkerboard": (10,),
    "test_bit_spread": (11,),
    "test_bit_flip": (12,),
    "test_walking_ones_zeros": (13, 14),   # 固件侧为 Walking Ones/Zeros 两项
    # S2 扩展 7（bit 15-21）
    "test_march_c_comparison": (15,),
    "test_eigenvalue_comparison": (16,),
    "test_pattern_array": (17,),
    "test_hammer_comparison": (18,),
    "test_bitadd_comparison": (19,),
    "test_gseed_comparison": (20,),
    "test_run_moving_inv": (21,),
    # S3 NEON 9（bit 22-30）
    "test_neon_random_value": (22,),
    "test_neon_solid_bit": (23,),
    "test_neon_block_sequential": (24,),
    "test_neon_checkerboard": (25,),
    "test_neon_bit_spread": (26,),
    "test_neon_walking_ones_zeros": (27,),
    "test_neon_run_moving_inv": (28,),
    "test_neon_bitadd_comparison": (29,),
    "test_neon_gseed_comparison": (30,),
    # S4 AC 8（bit 31-38）
    "test_ac_march_c": (31,),
    "test_ac_march_la": (32,),
    "test_ac_complement": (33,),
    "test_ac_step_len_parity_interleav_128": (34,),
    "test_ac_address_step_len_parity_interleav": (35,),
    "test_ac_rc_frame_march_raw": (36,),
    "test_ac_graycode": (37,),
    "test_ac_colharass": (38,),
}

# 生成顺序与旧上位机下发的 .cfg 样例一致（HG_LP4X_4GB..._NV.cfg）
_DEFAULTS = {
    "LOG_TO_UART1": 1,
    "LogLevel": 1,          # [HSG-LOG 2026-09-16] 日志档位：0=静默(只ERR) 1=测试档(默认)
                            # 2=全量(含SYS)；固件侧 cfg 无此键时默认 2（旧行为）
    "BadBlockMgmt": 0,      # [HSG-BB 2026-09-21] 坏区管理：1=memtester 遇错不停、
                            # 聚合记录全部坏区（固件分支 feature/badblock-mgmt 起支持，
                            # 旧固件静默忽略）；0=遇错即停（旧行为）
    "PatternTest": 1,
    "Density": 16,          # Gb
    "DieNum": 4,
    "MemTester": 1,
    "VideoTest": 0,
    "DvfsTest": 1,
    "EngineerMode": 0,
    "AgingTime": 5,         # 分钟
    "Freq": 3200,
    "VDD1": 1950,           # mV
    "VDD2": 1170,
    "VDD2L": 0,             # 0 = D4[2] 保持旧行为（板槽位不动）；下发正值才生效
    "VDDQ": 650,
    "ChannelA_Rank0_Enable": 1,
    "ChannelA_Rank0_Size": 8,   # Gb
    "ChannelA_Rank1_Enable": 0,
    "ChannelA_Rank1_Size": 0,
    "ChannelB_Rank0_Enable": 1,
    "ChannelB_Rank0_Size": 8,
    "ChannelB_Rank1_Enable": 0,
    "ChannelB_Rank1_Size": 0,
    "Mode": 0,              # 0:R0+R1 NORMAL / 1:BYTE+BYTE / 2:NORMAL+BYTE / 3:BYTE+NORMAL
}

# ---- cfg 键别名（2026-09-16）----
# 与固件 hsg_key_is 的显式别名表对齐：键名大小写不敏感 + 别名归一（不做前缀自动匹配）。
# 用户指令（2026-09-16）：上位机侧当前只登记 Freq/Frequency 一组。
# **新增一组 = 此处加一行 + SSOT §4.3 契约表登记 + 固件侧同名登记**。
_KEY_ALIASES = {"FREQUENCY": "FREQ"}

# 规范键名（大写）→ _DEFAULTS 中的真实键名（config.yaml 合并用）
_DEFAULT_BY_CANON = {k.upper(): k for k in _DEFAULTS}

# Product-owned board parameters which previously only came from config.yaml.
# Never accept an arbitrary key/value pass-through to firmware.
BOARD_CONFIG_RANGES = {
    'LOG_TO_UART1': (0, 1), 'PatternTest': (0, 1), 'Density': (1, 64),
    'DieNum': (1, 16), 'VideoTest': (0, 1), 'DvfsTest': (0, 1),
    'EngineerMode': (0, 1), 'AgingTime': (0, 1440), 'Mode': (0, 3),
}

# ---- P4：params 行名 → cfg 键 ----

# AC 时序参数（前端 params 行名 → cfg 键；同名项不列）。
# [AC-TIM 2026-09-20 固件已接入] WSL 权威仓 8709dd1c7：27 键 decode + 注入点
# A(DdrUpdateACTiming 拷表后覆盖)/B(TRFC 族终局直写)——本表即下发契约。
_TIMING_KEYS = {
    "TDQS2DQ": "TDQS2DQ", "TRCD": "TRCD", "TRP": "TRP", "TRAS时序": "TRAS",
    "TWR时序": "TWR", "TXRefCnt时序": "TXRefCnt", "TRPAB": "TRPAB",
    "TRC": "TRC", "TRFC": "TRFC", "TRFCPB": "TRFCPB", "TXP": "TXP",
    "TRTP": "TRTP", "TWTR": "TWTR", "TPBR2PBR": "TPBR2PBR",
    "TPBR2ACT": "TPBR2ACT", "TR2MRW": "TR2MRW", "TW2MRW": "TW2MRW",
    "TMRR2MRW": "TMRR2MRW", "TMRW": "TMRW", "TMRD": "TMRD",
    "TMRWCKEL": "TMRWCKEL", "TPDE": "TPDE", "TPDX": "TPDX", "TMRRI": "TMRRI",
    "TRRD": "TRRD", "TFAW": "TFAW", "TZQCS": "TZQCS",
}

# [AC-TIM 2026-10-13] 时序单位模式（TIMING_UNIT 键 ↔ 固件 g_hsg_timing.unit_mode）:
# 0=增量ns(默认,不下发键) 2=MCK 原始半周期值(reg<<1|05T 网格,整数,不×100 定标)。
# 模式 1=绝对ns 为固件预留,上位机不下发(按 0 处理并告警)。
# 单位模式只作用于直接项;TRFC 族恒为绝对 ns(固件注入点 B 固定语义,与模式无关)。
_TRFC_FAMILY = ("TRFC", "TRFCPB", "TXRefCnt")
# MCK 原始模式每参数半周期上限 = SHU 位域宽(固件注入点 A HT 表 maxreg)×2;
# 该模式固件不钳位——上位机必须拦截,v 合法域 [1, maxreg*2]
_TIMING_RAW_MAX = {
    "TRCD": 15, "TRP": 15, "TRAS": 15, "TWR": 31, "TRPAB": 7, "TRC": 31,
    "TXP": 7, "TRTP": 7, "TWTR": 15, "TPBR2PBR": 255, "TRRD": 7, "TFAW": 31,
    "TZQCS": 255,
}
# 本平台无数值寄存器位域的时序键(与 frontend/src/types/product.ts
# TIMING_UNSUPPORTED 同步维护):固件 decode 存而不施——上位机防线 =
# 编译时告警跳过,防手写 JSON 绕过 UI 灰化
_TIMING_UNSUPPORTED = {
    "TDQS2DQ", "TPBR2ACT", "TR2MRW", "TW2MRW", "TMRR2MRW",
    "TMRD", "TMRWCKEL", "TPDE", "TPDX", "TMRRI",
}

# VDD 合理范围（mV，LPDDR4x：1.8/1.1/0.6V 标称 ± margining 余量）
# VDD2L 2026-09-03 接线：cfg 键 VDD2L → 固件 D4[2] 槽（原恒 0）；0 = 不下发有效值
_VDD_RANGE = {"VDD1": (1000, 2400), "VDD2": (500, 1500),
              "VDD2L": (500, 1500), "VDDQ": (100, 1000)}

# 测试频率白名单（MT/s）：与固件 platform.c decode 后的白名单校验逐项一致
# （2026-09-03 扩档 1600/2400；1200/800 固件侧为 DIV4/半开环特殊档未放行）
_FREQ_VALID = {4266, 3733, 3200, 2400, 1600}

# params 行名 → VDD cfg 键（VDD2L 2026-09-03 已接线：键存在且非 0 时固件写 D4[2] 槽）
_VDD_PARAM_KEYS = {"VDD1(mV)": "VDD1", "VDD2H(mV)": "VDD2",
                   "VDD2L(mV)": "VDD2L", "VDDQ(mV)": "VDDQ"}

# 日志档位参数行名（LogLevel：0=静默 1=测试档 2=全量，2026-09-16 HSG-LOG）
_LOGLEVEL_PARAM_NAMES = frozenset({"LOGLEVEL", "日志档位"})

# 坏区管理参数行名（BadBlockMgmt：0=关 1=开，2026-09-21 HSG-BB）
_BADBLOCK_PARAM_NAMES = frozenset({"BADBLOCKMGMT", "坏区管理"})

# 测试频率的参数行名（前端为「测试频率(M)」；同时容忍手写档案里的 Freq/Frequency
# 写法，与 cfg 键别名同源，2026-09-16 用户指令）。统一大写后比较。
_FREQ_PARAM_NAMES = frozenset({"测试频率(M)".upper(), "FREQ", "FREQUENCY"})

# MR 读回比对的合法行名（前端 mr.ch1/ch2 行；"_2"为固件协议键的固定后缀）
_MR_NAME_RE = re.compile(r"^MR([5-8])_2$")


def base_cfg(cfg_yaml: dict) -> Dict[str, int]:
    """config.yaml → 基线 cfg 字典（未配置的键用出厂默认）

    键名大小写不敏感 + 别名归一（Frequency → Freq），
    2026-09-16 起与固件 hsg_key_is 的别名语义对齐；未登记键仍按原样忽略。
    """
    d = dict(_DEFAULTS)
    for k, v in (cfg_yaml or {}).get("cfg_defaults", {}).items():
        key = _DEFAULT_BY_CANON.get(canonical_key(k))
        if key is not None:
            d[key] = v
    return d


def canonical_key(name: str) -> str:
    """cfg 键 → 规范键名（去空白 + 大写 + 别名归一），与固件 decode 同语义。"""
    up = str(name).strip().upper()
    return _KEY_ALIASES.get(up, up)


def log_uart_warning(d: Dict[str, int]) -> List[str]:
    """LOG_TO_UART1=0 时必须给出提醒（2026-09-16 用户指令）。

    背景（2026-09-15 定案 + 2026-09-16 用户确认）：preloader `print.c` 的
    `outchar()` 被 `g_hsg_config.log_to_uart1` 门控，=0 时所有 printf/pal_log_err
    一字不出；banner 走 `uart1_puts` 直写 UART1 不经该门，仍可见——现场表现为
    "有 banner、config 之后静默"，极易误判成停机。**日志静默 ≠ 停机**。
    """
    if d.get("LOG_TO_UART1") == 0:
        return ["LOG_TO_UART1=0：已关闭治具串口日志输出——PL/LK/APK 日志不会上串口"
                "（banner 仍可见，日志静默≠停机）；生产静默跑可接受，需抓日志请置 1"]
    return []


def cfg_text(d: dict) -> str:
    return "".join(f"{k}={v}\n" for k, v in d.items())


def build_cfg(cfg_yaml: dict) -> str:
    """config.yaml 的 cfg_defaults 节 → .cfg 文本（后端启动基线）"""
    return cfg_text(base_cfg(cfg_yaml))


def _to_int(val: str) -> int:
    return int(float(val))


def cfg_from_profile(profile: dict, base: Dict[str, int]) -> Tuple[Dict[str, int], List[str]]:
    """ProductProfile(JSON) 覆盖基线 → (cfg 字典, 告警列表)。映射语义见模块头注释。"""
    d = dict(base)
    warns: List[str] = []
    if not isinstance(profile, dict):
        return d, warns
    for key, value in (profile.get('cfgOverrides') or {}).items():
        if key in BOARD_CONFIG_RANGES:
            d[key] = value

    # 1) 通道 / Rank 拓扑（rankEnabled 关闭 = 容量未指定，保留基线）
    if profile.get("rankEnabled"):
        caps = profile.get("rankCapacityGb") or [None, None]
        chans = profile.get("channels") or {}
        for ci, ck in enumerate(("ch1", "ch2")):
            letter = "AB"[ci]
            ch_on = bool(chans.get(ck))
            for ri in (0, 1):
                en, size = 0, 0
                if ch_on:
                    try:
                        size = int(round(float(caps[ri]) * 8))    # GB → Gb
                    except (TypeError, ValueError):
                        warns.append(f"rankCapacityGb[{ri}] 非法，通道{letter} Rank{ri} 按未配置处理")
                        size = 0
                    en = 1 if size > 0 else 0
                d[f"Channel{letter}_Rank{ri}_Enable"] = en
                d[f"Channel{letter}_Rank{ri}_Size"] = size

    # 2) PL1 阶段全局参数（pl1Enabled 关闭 = 参数不参与编译，保留基线）
    if profile.get("pl1Enabled"):
        from .timing_catalog import BY_KEY, encode_profile
        register_profile = profile.get("timingSchema") in (1, 2)
        # [AC-TIM 2026-10-13] 时序单位模式（产品级字段 timingUnit，旧档案缺省 = 0）：
        # 0=增量ns（默认，不下发 TIMING_UNIT 键，cfg 与旧版逐字节一致）
        # 2=MCK 原始值（下发 TIMING_UNIT=2，直接项按半周期格点整数编译）
        try:
            timing_unit = int(profile.get("timingUnit", 0))
        except (TypeError, ValueError):
            timing_unit = 0
            warns.append("timingUnit 非法，按增量ns(0)处理")
        else:
            if timing_unit == 1:
                warns.append("timingUnit=1（绝对ns）为固件预留模式，按增量ns(0)处理")
                timing_unit = 0
            elif timing_unit not in (0, 2):
                warns.append(f"timingUnit={timing_unit} 非法（合法 0/2），按增量ns(0)处理")
                timing_unit = 0
        if timing_unit == 2:
            d["TIMING_UNIT"] = 2
        for p in profile.get("params") or []:
            if not isinstance(p, dict) or not p.get("checked"):
                continue
            name = str(p.get("name", "")).strip()
            val = str(p.get("value", "")).strip()
            if register_profile and (name in BY_KEY or profile.get("timingSchema") == 2 and name not in _VDD_PARAM_KEYS and name.upper() not in (_FREQ_PARAM_NAMES | _LOGLEVEL_PARAM_NAMES | _BADBLOCK_PARAM_NAMES)):
                continue  # The versioned registry is encoded once, after ordinary parameters.
            if not val:
                continue
            if name.strip().upper() in _FREQ_PARAM_NAMES:
                try:
                    freq = _to_int(val)
                except ValueError:
                    freq = None
                    warns.append(f"测试频率非法：{val!r}，保留 {d['Freq']}")
                if freq is not None:
                    if freq in _FREQ_VALID:
                        d["Freq"] = freq
                    else:
                        warns.append(f"测试频率 {freq} 不在固件白名单 "
                                     f"{sorted(_FREQ_VALID, reverse=True)}，保留 {d['Freq']}")
            elif name in _VDD_PARAM_KEYS:
                key = _VDD_PARAM_KEYS[name]
                try:
                    mv = _to_int(val)
                except ValueError:
                    warns.append(f"{name} 非法：{val!r}，保留 {d[key]}")
                    continue
                lo, hi = _VDD_RANGE[key]
                if not (lo <= mv <= hi or key == 'VDD2L' and mv == 0):
                    warns.append(f"{name}={mv} 超出合理范围 [{lo},{hi}]mV"
                                 f"（疑似 10mV 显示单位），保留 {d[key]}")
                else:
                    d[key] = mv
            elif name in _TIMING_KEYS:
                # [AC-TIM 2026-09-20] 产品时序参数接入(docs/timing-params/03 §4.1):
                # UI 填 ns(支持小数/负数,如 1.0 / -2.5)→ 线格式 0.01ns 定标整数。
                # 增量族(14 直接项):值=Δns,|Δ|≤10 合法,0/解析失败=不下发;
                # TRFC 族(TRFC/TRFCPB/TXRefCnt):恒绝对 ns,60~400 合法。
                # [AC-TIM 2026-10-13] timingUnit=2(MCK 原始)模式:直接项按半周期
                # 格点整数编译(v=reg*2 无05T / reg*2-1 带05T),不×100 定标;
                # unsupported 键恒不下发(平台无数值寄存器位域)。
                key = _TIMING_KEYS[name]
                if name in _TIMING_UNSUPPORTED:
                    warns.append(f"时序参数 {name} 本平台无寄存器位域(unsupported)，不下发")
                    continue
                if key in _TRFC_FAMILY:
                    # TRFC 族恒绝对 ns,与单位模式无关(固件注入点 B 固定语义)
                    try:
                        ns = float(val)
                    except ValueError:
                        warns.append(f"时序参数 {name} 非法：{val!r}，忽略")
                        continue
                    if not 60.0 <= ns <= 400.0:
                        warns.append(f"{name}={ns}ns 超出绝对值域 [60,400]ns，忽略")
                        continue
                    d[key] = int(round(ns * 100))   # 0.01ns 定标
                elif timing_unit == 2:
                    # MCK 原始模式:整数半周期格点;固件此模式不钳位,按 SHU 位域上限拦截
                    try:
                        raw = _to_int(val)
                    except ValueError:
                        warns.append(f"时序参数 {name} 非法：{val!r}，忽略")
                        continue
                    mx = _TIMING_RAW_MAX.get(key)
                    if mx is None:
                        warns.append(f"时序参数 {name} 不支持 MCK 原始模式，忽略")
                        continue
                    if not 1 <= raw <= mx * 2:
                        warns.append(f"{name}={raw} 超出 MCK 原始域 [1,{mx * 2}]，忽略")
                        continue
                    d[key] = raw
                else:
                    # 增量 ns 模式(默认)
                    try:
                        ns = float(val)
                    except ValueError:
                        warns.append(f"时序参数 {name} 非法：{val!r}，忽略")
                        continue
                    if not -10.0 <= ns <= 10.0:
                        warns.append(f"{name}={ns}ns 超出增量域 |Δ|≤10ns，忽略")
                        continue
                    if ns == 0:
                        continue              # 0 = 标称不动,不下发
                    d[key] = int(round(ns * 100))   # 0.01ns 定标
            elif name.strip().upper() in _LOGLEVEL_PARAM_NAMES:
                try:
                    lv = _to_int(val)
                except ValueError:
                    lv = None
                    warns.append(f"日志档位非法：{val!r}，保留 {d['LogLevel']}")
                if lv is not None:
                    if 0 <= lv <= 2:
                        d["LogLevel"] = lv
                    else:
                        warns.append(f"日志档位 {lv} 超出范围 [0,2]，保留 {d['LogLevel']}")
            elif name.strip().upper() in _BADBLOCK_PARAM_NAMES:
                # [HSG-BB 2026-09-21] 坏区管理开关：1=memtester 遇错不停、
                # 聚合记录全部坏区；需 feature/badblock-mgmt 起固件，旧固件静默忽略
                try:
                    bb = _to_int(val)
                except ValueError:
                    bb = None
                    warns.append(f"坏区管理非法：{val!r}，保留 {d['BadBlockMgmt']}")
                if bb is not None:
                    if 0 <= bb <= 1:
                        d["BadBlockMgmt"] = bb
                    else:
                        warns.append(f"坏区管理 {bb} 超出范围 [0,1]，保留 {d['BadBlockMgmt']}")
            elif name == "锁定测试容量(MB)":
                # [HSG-SIZE 2026-09-11] 测试容量可配置：勾选且值>0 → MemTestSize=<MB>。
                # 固件链(preloader decode→boot tag→LK cmdline)尚未支持该键——当前
                # 固件对未知键静默忽略(前向兼容,下发无害)；memtest.sh 消费逻辑已留
                # TODO 注释,固件链更新后无需再动上位机即自动生效。0 = 不锁定(自动配额)。
                try:
                    mb = _to_int(val)
                except ValueError:
                    mb = None
                    warns.append(f"锁定测试容量非法：{val!r}，忽略")
                if mb is not None and mb > 0:
                    if not (16 <= mb <= 8192):
                        warns.append(f"锁定测试容量 {mb}MB 超出合理范围 [16,8192]，忽略")
                    else:
                        d["MemTestSize"] = mb
            # 其余（锁定测试容量(MB) 等）现行固件无键 → 跳过（P5 扩展）

    # 3) PL2 关闭 → 停 memtester（patterns 表待 P5 固件键后编译）
    if profile.get("pl2Enabled") is False:
        d["MemTester"] = 0

    # 3.5) PL2 pattern 掩码（2026-09-11 HSG-P2）：pl2Enabled 时按勾选合成
    #      P2Mask=0x...（位表 _P2_BIT_BY_NAME 与固件 tests[] 同序）。
    #      全部未勾选 → 不下发键并告警（固件无键=全部执行）。
    if profile.get("pl2Enabled"):
        mask = 0
        unknown = set()
        n_rows = 0
        for mode_rows in ((profile.get("pl2") or {}).get("patterns") or {}).values():
            for row in mode_rows or []:
                if not isinstance(row, dict):
                    continue
                n_rows += 1
                if not row.get("checked"):
                    continue
                bits = _P2_BIT_BY_NAME.get(str(row.get("name", "")).strip())
                if bits is None:
                    unknown.add(str(row.get("name", "")))
                else:
                    for b in bits:
                        mask |= 1 << b
        for name in sorted(unknown):
            warns.append(f"PL2 pattern {name} 不在固件位表（两侧位表失同步?），忽略")
        if n_rows and mask == 0:
            warns.append("PL2 pattern 全部未勾选：不下发 P2Mask，固件将执行全部测试项")
        else:
            d["P2Mask"] = f"0x{mask:X}"

    # 4) MR 读回比对（mr.ch1/ch2 按通道分组；无勾选项，行值非空即下发
    #    → Channel{A,B}_MR{5..8}_2=期望值（与固件 hsg_mr_chk_key 键名逐字符一致）。
    #    固件 PL 阶段按通道逐启用 Rank MRR 读回整寄存器比对，不符发 0x16/0x0A。
    #    下发条件：值合法 && 通道启用（CHn 启用 = 颗粒的通道配置））
    mr = profile.get("mr") or {}
    chans = profile.get("channels") or {}
    for ci, ck in enumerate(("ch1", "ch2")):
        if not chans.get(ck):
            continue                          # 颗粒无此通道 → 整组跳过
        letter = "AB"[ci]
        for row in mr.get(ck) or []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip()
            val = str(row.get("value", "")).strip()
            if not val:
                continue                      # 只有用户填值后才校验
            m = _MR_NAME_RE.match(name)       # MR5_2..MR8_2（"_2"为固件键固定后缀）
            if not m:
                warns.append(f"MR 名称非法：{name!r}（须为 MR5_2~MR8_2），忽略")
                continue
            try:
                expect = int(val, 0)          # 支持 0x 前缀与十进制
            except ValueError:
                warns.append(f"MR {name} 期望值非法：{val!r}，忽略")
                continue
            if not (0 <= expect <= 0xFF):
                warns.append(f"MR {name} 期望值 {expect} 超出 8 位范围，忽略")
                continue
            d[f"Channel{letter}_{name}"] = expect

    if profile.get("pl1Enabled") and profile.get("timingSchema") in (1, 2):
        if profile.get('timingSchema') == 2:
            from .timing_ns import encode, WIRE_VERSION
            encoded = encode(profile)
        else:
            encoded = encode_profile(profile)
        if encoded:
            d["TimingRegV"] = WIRE_VERSION if profile['timingSchema'] == 2 else 1
            d["TReg"] = encoded

    # 5) LOG_TO_UART1=0 提醒（放最前，便于现场一眼看到；2026-09-16 用户指令）
    warns[:0] = log_uart_warning(d)

    return d, warns


def parse_cfg(text: str) -> Dict[str, int]:
    """解析 .cfg 文本为 {规范键(大写): 整数值}（下位机 decode 逻辑的 Python 版；
    与固件 hsg_parse_u32/u64 一致支持 0x 前缀十六进制，如 P2Mask=0x7F...；
    键名大小写不敏感 + 别名归一，如 Frequency → FREQ，2026-09-16）"""
    out: Dict[str, int] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        try:
            out[canonical_key(k)] = int(v.strip(), 0)
        except ValueError:
            pass
    return out


def stages_from_cfg_text(text: str) -> List[str]:
    return stages_from_map(parse_cfg(text))


def stages_from_map(m: Dict[str, int]) -> List[str]:
    stages = ["PL"]
    if m.get("PATTERNTEST", 1) or m.get("MEMTESTER", 1):
        stages.append("LK")
    if m.get("MEMTESTER", 1) or m.get("DVFSTEST", 1) or m.get("AGINGTIME", 0) > 0:
        stages.append("APK")
    return stages

# aging_minutes() 已随 0x12 死路径移除（2026-09-03，DUT 固件不发起 0x12；
# 需要时用 parse_cfg(text).get("AGINGTIME", 0) 或查 git 历史）
