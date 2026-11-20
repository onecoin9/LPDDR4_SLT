"""cfg_from_profile 编译器单元测试（P4：ProductProfile JSON → .cfg）。

契约 = frontend/src/types/product.ts（ProductProfile）。
运行：cd backend && python -m unittest discover -s tests -v
"""

import sys
import unittest

sys.path.insert(0, ".")
from app.cfg import (  # noqa: E402
    _DEFAULTS,
    base_cfg,
    cfg_from_profile,
    parse_cfg,
    stages_from_map,
)


def profile(**kw):
    """前端 defaultProfiles 的最小骨架（LPDDR4x-16Gb 形态）"""
    p = {
        "name": "TEST-PROFILE",
        "rankEnabled": True,
        "pl1Enabled": True,
        "pl2Enabled": True,
        "rankCapacityGb": [1, 1],          # GB
        "channels": {"ch1": True, "ch2": True},
        "mr": {"ch1": [], "ch2": []},
        "params": [
            {"id": 1, "name": "VDD1(mV)", "value": "1900", "checked": True},
            {"id": 2, "name": "VDD2H(mV)", "value": "1150", "checked": True},
            {"id": 3, "name": "VDDQ(mV)", "value": "600", "checked": True},
            {"id": 4, "name": "测试频率(M)", "value": "3733", "checked": True},
            {"id": 5, "name": "TRCD", "value": "1.0", "checked": True},
        ],
        "pl2": {"testMode": "全映射读写测试", "ascEnabled": True,
                "ascOrder": "升序", "patterns": []},
    }
    p.update(kw)
    return p


class TestTopology(unittest.TestCase):
    """通道/Rank 拓扑映射：GB → Gb、通道关 = 双 Rank 全关"""

    def test_dual_channel_1gb_each(self):
        d, w = cfg_from_profile(profile(), dict(_DEFAULTS))
        self.assertEqual(w, [])
        self.assertEqual(d["ChannelA_Rank0_Enable"], 1)
        self.assertEqual(d["ChannelA_Rank0_Size"], 8)     # 1GB → 8Gb
        self.assertEqual(d["ChannelB_Rank1_Size"], 8)

    def test_channel_disabled_kills_both_ranks(self):
        d, _ = cfg_from_profile(profile(channels={"ch1": True, "ch2": False}), dict(_DEFAULTS))
        self.assertEqual(d["ChannelB_Rank0_Enable"], 0)
        self.assertEqual(d["ChannelB_Rank0_Size"], 0)
        self.assertEqual(d["ChannelB_Rank1_Size"], 0)
        self.assertEqual(d["ChannelA_Rank0_Size"], 8)

    def test_half_gb_and_zero_capacity(self):
        # 前端 LPDDR4x-8Gb 默认：0.5GB/rank → 4Gb；0 容量 → Enable=0
        d, _ = cfg_from_profile(profile(rankCapacityGb=[0.5, 0]), dict(_DEFAULTS))
        self.assertEqual(d["ChannelA_Rank0_Size"], 4)
        self.assertEqual(d["ChannelA_Rank1_Enable"], 0)
        self.assertEqual(d["ChannelA_Rank1_Size"], 0)

    def test_rank_disabled_keeps_baseline(self):
        d, _ = cfg_from_profile(profile(rankEnabled=False), dict(_DEFAULTS))
        self.assertEqual(d["ChannelA_Rank0_Size"], _DEFAULTS["ChannelA_Rank0_Size"])
        self.assertEqual(d["ChannelA_Rank1_Enable"], _DEFAULTS["ChannelA_Rank1_Enable"])


class TestParams(unittest.TestCase):
    """PL1 参数映射：频率/VDD/时序键；未勾选不参与"""

    def test_vdd_freq_timing(self):
        d, w = cfg_from_profile(profile(), dict(_DEFAULTS))
        self.assertEqual(w, [])
        self.assertEqual(d["VDD1"], 1900)
        self.assertEqual(d["VDD2"], 1150)
        self.assertEqual(d["VDDQ"], 600)
        self.assertEqual(d["Freq"], 3733)
        # [AC-TIM] ns → 0.01ns 定标:1.0ns → 100
        self.assertEqual(d["TRCD"], 100)

    def test_timing_scaling_and_domains(self):
        # [AC-TIM 2026-09-20] 定标/域检查(增量|Δ|≤10;TRFC 族 60..400 绝对;0=不下发)
        mk = lambda n, v: profile(params=[{"id": 1, "name": n, "value": v, "checked": True}])
        d, w = cfg_from_profile(mk("TRP", "-2.5"), dict(_DEFAULTS))
        self.assertEqual(d["TRP"], -250)                      # -2.5ns → -250
        d, w = cfg_from_profile(mk("TRFC", "180"), dict(_DEFAULTS))
        self.assertEqual(d["TRFC"], 18000)                    # 180ns 绝对 → 18000
        d, w = cfg_from_profile(mk("TRAS时序", "0"), dict(_DEFAULTS))
        self.assertNotIn("TRAS", d)                           # 0 = 标称不动,不下发
        d, w = cfg_from_profile(mk("TWR时序", "15"), dict(_DEFAULTS))
        self.assertNotIn("TWR", d)                            # 增量越界拒绝
        self.assertTrue(any("TWR" in x for x in w))
        d, w = cfg_from_profile(mk("TXRefCnt时序", "50"), dict(_DEFAULTS))
        self.assertNotIn("TXRefCnt", d)                       # 绝对域越界拒绝
        self.assertTrue(any("TXRefCnt" in x for x in w))

    def test_suspicious_vdd_unit_warns_and_keeps_baseline(self):
        # 前端默认 VDD1=180（疑似 10mV 显示单位）→ 越界告警 + 保留基线 1950
        d, w = cfg_from_profile(profile(params=[
            {"id": 1, "name": "VDD1(mV)", "value": "180", "checked": True}]),
            dict(_DEFAULTS))
        self.assertEqual(d["VDD1"], _DEFAULTS["VDD1"])
        self.assertTrue(any("VDD1" in x for x in w))

    def test_unchecked_param_ignored(self):
        d, w = cfg_from_profile(profile(params=[
            {"id": 1, "name": "TRCD", "value": "99", "checked": False}]),
            dict(_DEFAULTS))
        self.assertNotIn("TRCD", d)
        self.assertEqual(w, [])

    def test_vdd2l_wired_with_range_check(self):
        # 2026-09-03 VDD2L 接线：合法值下发 D4[2]，量纲可疑值（10mV 单位遗留）拒绝并告警
        d, w = cfg_from_profile(profile(params=[
            {"id": 1, "name": "VDD2L(mV)", "value": "1100", "checked": True}]),
            dict(_DEFAULTS))
        self.assertEqual(d["VDD2L"], 1100)
        self.assertEqual(w, [])

        d, w = cfg_from_profile(profile(params=[
            {"id": 1, "name": "VDD2L(mV)", "value": "110", "checked": True}]),
            dict(_DEFAULTS))
        self.assertEqual(d["VDD2L"], _DEFAULTS["VDD2L"])   # 越范围回退基线 0
        self.assertTrue(any("VDD2L" in x for x in w))

    def test_pl1_disabled_keeps_baseline(self):
        d, _ = cfg_from_profile(profile(pl1Enabled=False), dict(_DEFAULTS))
        self.assertEqual(d["VDD1"], _DEFAULTS["VDD1"])
        self.assertEqual(d["Freq"], _DEFAULTS["Freq"])

    def test_timing_key_alias(self):
        # 前端带"时序"后缀的三个行名 → 无后缀 cfg 键
        # [AC-TIM] 值改为 ns 语义定标:TRAS 1.2ns→120;TXRefCnt 140ns 绝对→14000
        d, _ = cfg_from_profile(profile(params=[
            {"id": 1, "name": "TRAS时序", "value": "1.2", "checked": True},
            {"id": 2, "name": "TXRefCnt时序", "value": "140", "checked": True}]),
            dict(_DEFAULTS))
        self.assertEqual(d["TRAS"], 120)
        self.assertEqual(d["TXRefCnt"], 14000)


class TestStages(unittest.TestCase):
    """pl2Enabled=false → MemTester=0 → 阶段序列收窄（mock_dut 消费同一推导）"""

    def test_pl2_off_drops_memtester(self):
        # 基线 DvfsTest=1 时 APK 仍在（固件语义：MemTester/AgingTime/DvfsTest
        # 任一 → 进 Android，mt_boot.c）；无 memtester 的效果要 DvfsTest/AgingTime
        # 也为 0 才在阶段序列上体现
        base = dict(_DEFAULTS)
        d, _ = cfg_from_profile(profile(pl2Enabled=False), base)
        self.assertEqual(d["MemTester"], 0)
        m = parse_cfg("".join(f"{k}={v}\n" for k, v in d.items()))
        self.assertEqual(stages_from_map(m), ["PL", "LK", "APK"])

        base.update({"DvfsTest": 0, "AgingTime": 0})
        d, _ = cfg_from_profile(profile(pl2Enabled=False), base)
        m = parse_cfg("".join(f"{k}={v}\n" for k, v in d.items()))
        self.assertEqual(stages_from_map(m), ["PL", "LK"])   # PatternTest=1 仍在

    def test_default_full_chain(self):
        d, _ = cfg_from_profile(profile(), dict(_DEFAULTS))
        self.assertEqual(d["MemTester"], 1)                   # 基线不变


class TestMrCheck(unittest.TestCase):
    """MR 读回比对（2026-09-01 改按通道分组）：mr{ch1,ch2} 行值非空即下发
    → Channel{A,B}_MR{5..8}_2=期望值（与固件 hsg_mr_chk_key 键名逐字符一致；
    无勾选项——只有用户填值后才校验；CHn 启用 = 颗粒的通道配置）"""

    def _rows(self, *rows):
        return [{"name": n, "value": v} for n, v in rows]

    def _mr(self, ch1=None, ch2=None):
        return {"ch1": ch1 or [], "ch2": ch2 or []}

    def test_filled_rows_compile_per_channel(self):
        d, w = cfg_from_profile(profile(mr=self._mr(
            ch1=self._rows(("MR5_2", "0x1A"), ("MR8_2", "0x3C")),
            ch2=self._rows(("MR6_2", "17")),
        )), dict(_DEFAULTS))
        self.assertEqual(w, [])
        self.assertEqual(d["ChannelA_MR5_2"], 0x1A)
        self.assertEqual(d["ChannelA_MR8_2"], 0x3C)
        self.assertEqual(d["ChannelB_MR6_2"], 17)         # 十进制也接受
        self.assertNotIn("ChannelB_MR5_2", d)             # 各通道独立

    def test_empty_value_ignored(self):
        d, w = cfg_from_profile(profile(mr=self._mr(
            ch1=self._rows(("MR5_2", ""), ("MR6_2", "  ")),
        )), dict(_DEFAULTS))
        self.assertNotIn("ChannelA_MR5_2", d)             # 空值 = 不校验
        self.assertNotIn("ChannelA_MR6_2", d)
        self.assertEqual(w, [])

    def test_channel_disabled_skips_keys(self):
        d, _ = cfg_from_profile(profile(
            channels={"ch1": True, "ch2": False},
            mr=self._mr(ch2=self._rows(("MR5_2", "0x1A")))),
            dict(_DEFAULTS))
        self.assertNotIn("ChannelB_MR5_2", d)             # 颗粒无此通道 → 整组跳过

    def test_bad_name_and_value_warn(self):
        d, w = cfg_from_profile(profile(mr=self._mr(
            ch1=self._rows(("MR9_2", "1"), ("MR5_1", "1"), ("MR5_2", "xyz"),
                           ("MR6_2", "0x1FF")),
        )), dict(_DEFAULTS))
        self.assertEqual(len(w), 4)                       # MR9 非法/_1 后缀非法/非法值/超 8 位
        self.assertNotIn("ChannelA_MR9_2", d)
        self.assertNotIn("ChannelA_MR5_2", d)
        self.assertNotIn("ChannelA_MR6_2", d)


class TestRoundtrip(unittest.TestCase):
    """编译结果必须能被下位机 decode 的 Python 版（parse_cfg）无损读回"""

    def test_parse_cfg_roundtrip(self):
        d, _ = cfg_from_profile(profile(rankCapacityGb=[2, 0],
                                        channels={"ch1": True, "ch2": False}),
                                dict(_DEFAULTS))
        m = parse_cfg("".join(f"{k}={v}\n" for k, v in d.items()))
        self.assertEqual(len(m), len(d))
        for k, v in d.items():
            # P2Mask 等十六进制字符串值：parse 后为 int（与固件 decode 语义一致）
            self.assertEqual(m[k.upper()], int(str(v), 0))


class TestKeyAliases(unittest.TestCase):
    """cfg 键别名（2026-09-16 用户指令）：上位机侧目前只登记 Freq/Frequency 一组。

    与固件 hsg_key_is 的显式别名表对齐——大小写不敏感 + 显式别名，不做前缀匹配。
    """

    def test_base_cfg_accepts_freq_spellings(self):
        for key in ("Freq", "freq", "FREQ", "Frequency", "frequency", "FREQUENCY"):
            with self.subTest(key=key):
                d = base_cfg({"cfg_defaults": {key: 3733}})
                self.assertEqual(d["Freq"], 3733)

    def test_base_cfg_still_ignores_unknown_key(self):
        d = base_cfg({"cfg_defaults": {"NoSuchKey": 1}})
        self.assertNotIn("NoSuchKey", d)

    def test_parse_cfg_normalizes_alias_to_canonical(self):
        m = parse_cfg("Frequency=3733\n")
        self.assertEqual(m["FREQ"], 3733)          # 规范键 = FREQ
        self.assertNotIn("FREQUENCY", m)
        # 两种写法落到同一键 → 后写覆盖（与固件 decode 逐行覆盖语义一致）
        m2 = parse_cfg("Frequency=3733\nfreq=3200\n")
        self.assertEqual(m2["FREQ"], 3200)

    def test_profile_param_accepts_freq_spellings(self):
        for name in ("测试频率(M)", "Freq", "Frequency"):
            with self.subTest(name=name):
                d, _ = cfg_from_profile(profile(params=[
                    {"id": 4, "name": name, "value": "3733", "checked": True},
                ]), base_cfg({}))
                self.assertEqual(d["Freq"], 3733)


class TestLogToUartWarning(unittest.TestCase):
    """LOG_TO_UART1=0 提醒（2026-09-16 用户指令）：门控机制见 cfg.log_uart_warning。"""

    def test_warns_when_log_output_disabled(self):
        _, warns = cfg_from_profile(profile(),
                                    base_cfg({"cfg_defaults": {"LOG_TO_UART1": 0}}))
        self.assertTrue(any("LOG_TO_UART1=0" in w for w in warns), warns)
        self.assertIn("已关闭治具串口日志输出", warns[0])   # 放最前，便于一眼看到

    def test_silent_when_log_output_enabled(self):
        _, warns = cfg_from_profile(profile(), base_cfg({}))
        self.assertFalse(any("LOG_TO_UART1" in w for w in warns), warns)


class TestLogLevel(unittest.TestCase):
    """LogLevel 日志档位键（HSG-LOG 2026-09-16）：0=静默(只ERR) 1=测试档 2=全量。

    固件侧 cfg 无此键时默认 2（旧行为）；上位机基线恒带 LogLevel=1。
    """

    def test_default_is_test_level(self):
        d = base_cfg({})
        self.assertEqual(d["LogLevel"], 1)

    def test_base_cfg_override_case_insensitive(self):
        d = base_cfg({"cfg_defaults": {"loglevel": 0}})
        self.assertEqual(d["LogLevel"], 0)

    def test_profile_param_row(self):
        d, warns = cfg_from_profile(profile(params=[
            {"id": 99, "name": "LogLevel", "value": "2", "checked": True},
        ]), base_cfg({}))
        self.assertEqual(d["LogLevel"], 2)
        self.assertFalse(any("日志档位" in w for w in warns), warns)

    def test_profile_param_out_of_range_keeps_default(self):
        d, warns = cfg_from_profile(profile(params=[
            {"id": 99, "name": "LogLevel", "value": "9", "checked": True},
        ]), base_cfg({}))
        self.assertEqual(d["LogLevel"], 1)
        self.assertTrue(any("日志档位" in w for w in warns), warns)

    def test_parse_cfg_roundtrip(self):
        m = parse_cfg("LogLevel=0\n")
        self.assertEqual(m["LOGLEVEL"], 0)


class TestBadBlockMgmt(unittest.TestCase):
    """BadBlockMgmt 坏区管理键（HSG-BB 2026-09-21）：0=关(遇错即停) 1=开(继续+记录)。

    固件分支 feature/badblock-mgmt 起支持；旧固件对未知键静默忽略。
    上位机基线恒带 BadBlockMgmt=0（显式关闭，与固件缺省一致）。
    """

    def test_default_off(self):
        d = base_cfg({})
        self.assertEqual(d["BadBlockMgmt"], 0)

    def test_base_cfg_override_case_insensitive(self):
        d = base_cfg({"cfg_defaults": {"badblockmgmt": 1}})
        self.assertEqual(d["BadBlockMgmt"], 1)

    def test_profile_param_row(self):
        d, warns = cfg_from_profile(profile(params=[
            {"id": 99, "name": "坏区管理", "value": "1", "checked": True},
        ]), base_cfg({}))
        self.assertEqual(d["BadBlockMgmt"], 1)
        self.assertFalse(any("坏区管理" in w for w in warns), warns)

    def test_profile_param_out_of_range_keeps_default(self):
        d, warns = cfg_from_profile(profile(params=[
            {"id": 99, "name": "BadBlockMgmt", "value": "5", "checked": True},
        ]), base_cfg({}))
        self.assertEqual(d["BadBlockMgmt"], 0)
        self.assertTrue(any("坏区管理" in w for w in warns), warns)

    def test_parse_cfg_roundtrip(self):
        m = parse_cfg("BadBlockMgmt=1\n")
        self.assertEqual(m["BADBLOCKMGMT"], 1)


class TestTimingUnit(unittest.TestCase):
    """[AC-TIM 2026-10-13] 时序单位模式（TIMING_UNIT 键 ↔ 固件 g_hsg_timing.unit_mode）。

    0=增量ns（默认，不下发键，行为与旧版逐字节一致）；
    2=MCK 原始半周期值（reg<<1|05T 网格，整数，不×100 定标）；
    1=绝对ns 固件预留（按 0 处理并告警）。
    TRFC 族恒绝对 ns，与单位模式无关（固件注入点 B 固定语义）。
    """

    def mk(self, *rows, **kw):
        params = [{"id": i + 1, "name": n, "value": v, "checked": True}
                  for i, (n, v) in enumerate(rows)]
        return cfg_from_profile(profile(params=params, **kw), dict(_DEFAULTS))

    def test_default_no_timing_unit_key(self):
        # 旧档案无 timingUnit → 不下发键，Δns 语义不变（零回归）
        d, w = self.mk(("TRCD", "1.0"))
        self.assertNotIn("TIMING_UNIT", d)
        self.assertEqual(d["TRCD"], 100)
        self.assertEqual(w, [])

    def test_mode0_explicit_emits_nothing(self):
        # 显式 timingUnit=0 也保持不下发键（固件默认即 0）
        d, w = self.mk(("TRCD", "1.0"), timingUnit=0)
        self.assertNotIn("TIMING_UNIT", d)
        self.assertEqual(d["TRCD"], 100)

    def test_mode2_raw_passthrough(self):
        # v=reg*2（无05T）与 reg*2-1（带05T）均原样下发，不×100
        # （TWR/TRC 位域 5bit，半周期上限 62，容纳 reg20）
        d, w = self.mk(("TWR时序", "40"), ("TRC", "39"), timingUnit=2)
        self.assertEqual(d["TIMING_UNIT"], 2)
        self.assertEqual(d["TWR"], 40)      # reg20 无05T
        self.assertEqual(d["TRC"], 39)      # reg20 带05T
        self.assertEqual(w, [])

    def test_mode2_out_of_range_rejected(self):
        # TRCD 位域 4bit → 半周期上限 30；31 越界拒绝（固件此模式不钳位，上位机拦）
        d, w = self.mk(("TRCD", "31"), timingUnit=2)
        self.assertNotIn("TRCD", d)
        self.assertTrue(any("TRCD" in x for x in w))
        # 负数/0 拒绝
        d, w = self.mk(("TRP", "0"), timingUnit=2)
        self.assertNotIn("TRP", d)
        self.assertTrue(any("TRP" in x for x in w))

    def test_mode2_trfc_still_absolute_ns(self):
        # TRFC 族不受单位模式影响：恒绝对 ns ×100
        d, w = self.mk(("TRFC", "180"), ("TXRefCnt时序", "140"), timingUnit=2)
        self.assertEqual(d["TIMING_UNIT"], 2)
        self.assertEqual(d["TRFC"], 18000)
        self.assertEqual(d["TXRefCnt"], 14000)
        self.assertEqual(w, [])

    def test_mode1_reserved_falls_back(self):
        d, w = self.mk(("TRCD", "1.0"), timingUnit=1)
        self.assertNotIn("TIMING_UNIT", d)
        self.assertEqual(d["TRCD"], 100)    # 按 Δns 处理
        self.assertTrue(any("预留" in x for x in w))

    def test_invalid_timing_unit_falls_back(self):
        d, w = self.mk(("TRCD", "1.0"), timingUnit=7)
        self.assertNotIn("TIMING_UNIT", d)
        self.assertEqual(d["TRCD"], 100)
        self.assertTrue(any("timingUnit" in x for x in w))

    def test_unsupported_timing_key_skipped(self):
        # 平台无数值寄存器位域的键：手写 JSON 勾选也不编译（UI 灰化的后端防线）
        for name in ("TR2MRW", "TDQS2DQ", "TMRRI"):
            with self.subTest(name=name):
                d, w = self.mk((name, "5"))
                self.assertNotIn(name, d)
                self.assertTrue(any(name in x and "unsupported" in x for x in w))

    def test_supported_timing_still_compiles_in_mode0(self):
        # 防线只拦 unsupported，正常键不受影响
        d, w = self.mk(("TMRW", "1.5"), ("TRRD", "2"))
        self.assertEqual(d["TMRW"], 150)
        self.assertEqual(d["TRRD"], 200)
        self.assertEqual(w, [])


if __name__ == "__main__":
    unittest.main()
