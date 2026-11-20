"""手动调试「设置」区 + 完整运行编排单测（debug/manual-4dut）。

覆盖：
- update_manual_debug_yaml：文本级更新 config.yaml（保留注释/其它节，缺键追加）
- ManualDebug.apply_settings：校验 + 内存生效 + 持久化（yaml / cfg 文件）
- ManualDebug.get_cfg_text：cfg 文件缺失/为空 → 回退 cfg_defaults 基线
- ManualDebug.sync_server_ip：bind 本机 IP 发网段定向广播（2026-09-17 现场坑）
- ManualRunner：arm → wait_ready →(0x10 READY)→ cfg_sent →(0x15 ACK)→ running；
  超时 / TestDone / DUT 重启锁存失败 / disarm
- DutLogFileSink：按日期分文件落盘

运行：cd backend && python -m unittest tests.test_manual_settings -v
"""

import asyncio
import json
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, ".")

from app import commboard                      # noqa: E402
from app.logchannel import DutLogFileSink      # noqa: E402
from app.manual import (ManualDebug, ManualDebugError,   # noqa: E402
                        update_manual_debug_yaml)
from app.manualrun import (BoardHealthMonitor, ManualRunner,  # noqa: E402
                           ST_CFG_SENT, ST_FAIL, ST_IDLE,
                           ST_PASS, ST_RUNNING, ST_TIMEOUT, ST_WAIT_READY)
from app.protocol import (CMD_READY, CMD_START_TEST, ROLE_SLAVE,  # noqa: E402
                          build_frame)

CFG = {"cfg_defaults": {"Density": 16, "Freq": 3200},
       "manual_debug": {"enabled": True, "board_host": "192.168.50.100",
                        "mb_port": 501, "dut_count": 4,
                        "dut_lines": [4, 5, 6, 7],
                        "local_ip": "192.168.50.10",
                        "log_dir": "", "cfg_file": "manual_debug.cfg",
                        "run_mode": "power_only", "ready_timeout_sec": 180}}

YAML_SAMPLE = """# 头部注释
server:
  host: 0.0.0.0
  port: 8000

manual_debug:
  enabled: true
  board_host: 192.168.50.100   # 通讯板 IP（原版固件）
  mb_port: 501                 # Modbus 端口
  dut_lines: [4, 5, 6, 7]      # 线号

# 后续节
tempctrl:
  enabled: false
"""


def ready_frame(ver: bytes = b"V1.0") -> bytes:
    payload = bytes(8) + b"sfda" + ver[:4].ljust(4, b" ")
    return build_frame(ROLE_SLAVE, CMD_READY, payload)


def ack_frame(status: int = 0) -> bytes:
    # HsgCodec.decode：status = payload[0] | payload[1]<<8（u16 LE，
    # 与固件 receive_config_with_ack 回包 AF 02 00 01 15 ss 00 一致）
    return build_frame(ROLE_SLAVE, CMD_START_TEST,
                       bytes([status & 0xFF, (status >> 8) & 0xFF]))


def done_frame(code: int = 0) -> bytes:
    return build_frame(ROLE_SLAVE, 0x17, bytes([code & 0xFF, code >> 8]))


class FakeHub:
    def __init__(self):
        self.logs = []
        self.updates = []          # (site, slot, kw) —— dut_status 发布
        self.results = []          # (site, slot, result, fail_item, duration)

    def log(self, site, slot, level, msg, cat="dut"):
        self.logs.append((site, slot, level, msg, cat))

    def syslog(self, level, msg):
        self.logs.append((None, None, level, msg, "system"))

    def update(self, site, slot, **kw):
        self.updates.append((site, slot, kw))

    def result(self, site, slot, result, fail_item, duration_sec):
        self.results.append((site, slot, result, fail_item, duration_sec))


class FakeTransport:
    def __init__(self):
        self.sent = []

    def sendto(self, data, addr):
        self.sent.append((data, addr))

    def close(self):
        pass


class TestYamlUpdate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "config.yaml")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(YAML_SAMPLE)

    def _read(self):
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def test_replace_existing_keeps_comment_and_others(self):
        update_manual_debug_yaml(self.path, {"board_host": "192.168.50.101",
                                             "run_mode": "full_run"})
        text = self._read()
        self.assertIn("board_host: 192.168.50.101   # 通讯板 IP（原版固件）", text)
        self.assertIn("  run_mode: full_run\n", text)          # 缺键追加到节尾
        self.assertIn("mb_port: 501                 # Modbus 端口", text)
        self.assertIn("tempctrl:\n  enabled: false", text)     # 其它节不动
        self.assertTrue(text.startswith("# 头部注释"))

    def test_append_before_next_section(self):
        update_manual_debug_yaml(self.path, {"local_ip": "192.168.50.10"})
        text = self._read()
        i_md = text.index("local_ip: 192.168.50.10")
        i_tc = text.index("tempctrl:")
        self.assertLess(i_md, i_tc)                            # 追加在节内

    def test_value_with_special_chars_quoted(self):
        update_manual_debug_yaml(self.path, {"log_dir": r"D:\SLT Logs\a#b"})
        self.assertIn('log_dir: "D:\\\\SLT Logs\\\\a#b"', self._read())

    def test_missing_section_500(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("server:\n  host: x\n")
        with self.assertRaises(ManualDebugError) as ctx:
            update_manual_debug_yaml(self.path, {"run_mode": "full_run"})
        self.assertEqual(ctx.exception.status, 500)

    def test_block_lists_from_packaging_are_replaced_completely(self):
        import yaml
        for indent in ("  ", "    "):
            with self.subTest(indent=indent):
                text = ("# keep header\nmanual_debug:\n  enabled: true\n"
                        "  dut_lines: # keep line comment\n"
                        + "".join(f"{indent}- {n}\n" for n in (4, 5, 6, 7))
                        + "  # keep between keys\n  dut_channels:\n"
                        + "".join(f"{indent}- {n}\n" for n in (5, 6, 7, 8))
                        + "tempctrl:\n  enabled: false\n")
                with open(self.path, "w", encoding="utf-8") as f:
                    f.write(text)
                update_manual_debug_yaml(self.path, {"dut_lines": [4, 5], "dut_channels": [5, 6]})
                saved = self._read()
                cfg = yaml.safe_load(saved)
                self.assertEqual(cfg["manual_debug"]["dut_lines"], [4, 5])
                self.assertEqual(cfg["manual_debug"]["dut_channels"], [5, 6])
                self.assertIn("# keep line comment", saved)
                self.assertIn("# keep between keys", saved)
                self.assertTrue(saved.endswith("tempctrl:\n  enabled: false\n"))
                update_manual_debug_yaml(self.path, {"dut_lines": [4, 5, 6], "dut_channels": [5, 6, 7]})
                self.assertEqual(yaml.safe_load(self._read())["manual_debug"]["dut_lines"], [4, 5, 6])

    def test_quoted_hash_does_not_become_a_comment(self):
        import yaml
        with open(self.path, "w", encoding="utf-8") as f:
            f.write('manual_debug:\n  log_dir: "old # directory" # real comment\n')
        update_manual_debug_yaml(self.path, {"log_dir": "new # directory"})
        self.assertEqual(yaml.safe_load(self._read())["manual_debug"]["log_dir"], "new # directory")
        self.assertIn("# real comment", self._read())
        self.assertNotIn("old # directory", self._read())

    def test_invalid_existing_yaml_is_not_overwritten(self):
        text = "manual_debug:\n  dut_lines: [4, 5]\n  - 4\n  - 5\n"
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)
        with self.assertRaises(ManualDebugError):
            update_manual_debug_yaml(self.path, {"dut_lines": [4]})
        self.assertEqual(self._read(), text)

    def test_atomic_replace_failure_keeps_original_and_cleans_temporary(self):
        from unittest.mock import patch
        before = self._read()
        with patch("app.manual.os.replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                update_manual_debug_yaml(self.path, {"dut_lines": [4, 5]})
        self.assertEqual(self._read(), before)
        self.assertEqual(os.listdir(self.tmp.name), ["config.yaml"])

    def test_add_remove_and_reload_packaged_multiline_config(self):
        import yaml
        cfg = json.loads(json.dumps(CFG))
        cfg["manual_debug"]["dut_channels"] = [5, 6, 7, 8]
        text = yaml.safe_dump(cfg, sort_keys=False)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)
        md = ManualDebug(cfg, data_dir=self.tmp.name)
        md.add_dut(self.path)
        after_add = yaml.safe_load(self._read())
        restored = ManualDebug(after_add, data_dir=self.tmp.name)
        self.assertEqual(restored.dut_lines, md.dut_lines)
        self.assertEqual(restored.dut_channels, md.dut_channels)
        restored.remove_dut(len(restored.dut_lines), self.path)
        after_remove = yaml.safe_load(self._read())
        self.assertEqual(after_remove["manual_debug"]["dut_lines"], cfg["manual_debug"]["dut_lines"])
        self.assertEqual(after_remove["manual_debug"]["dut_channels"], cfg["manual_debug"]["dut_channels"])


class TestApplySettings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg_path = os.path.join(self.tmp.name, "config.yaml")
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write(YAML_SAMPLE)
        self.md = ManualDebug(CFG, data_dir=self.tmp.name)

    def test_apply_and_persist(self):
        r = self.md.apply_settings(
            {"boardHost": "192.168.50.100", "localIp": "192.168.50.11",
             "logDir": "logs", "runMode": "full_run", "readyTimeoutSec": 120,
             "cfgContent": "Density=8\nFreq=3733\n"}, self.cfg_path)
        self.assertEqual(r["localIp"], "192.168.50.11")
        self.assertEqual(r["runMode"], "full_run")
        self.assertEqual(r["readyTimeoutSec"], 120)
        self.assertEqual(r["cfgContent"], "Density=8\nFreq=3733\n")
        # 2026-09-21：保存到 session_settings.json（不再写 config.yaml，
        # 重启后恢复默认）
        import json
        sf = os.path.join(self.tmp.name, "session_settings.json")
        saved = json.load(open(sf, encoding="utf-8"))
        self.assertEqual(saved["local_ip"], "192.168.50.11")
        self.assertEqual(saved["run_mode"], "full_run")
        self.assertEqual(saved["log_dir"], "logs")
        self.assertEqual(saved["ready_timeout_sec"], 120)
        # config.yaml 不被改动
        yaml_text = open(self.cfg_path, encoding="utf-8").read()
        self.assertNotIn("192.168.50.11", yaml_text)
        # cfg 内容写到 cfg_file 而非 yaml
        cfg_text = open(os.path.join(self.tmp.name, "manual_debug.cfg"),
                        encoding="utf-8").read()
        self.assertEqual(cfg_text, "Density=8\nFreq=3733\n")

    def test_validation(self):
        for body in ({"boardHost": "999.1.1.1"}, {"localIp": "abc"},
                     {"runMode": "xxx"}, {"readyTimeoutSec": 1},
                     {"readyTimeoutSec": "x"}, {"nope": 1}):
            with self.assertRaises(ManualDebugError) as ctx:
                self.md.apply_settings(body, self.cfg_path)
            self.assertEqual(ctx.exception.status, 400, body)

    def test_get_cfg_text_fallback_baseline(self):
        """cfg 文件缺失 → 回退 cfg_defaults 基线"""
        text = self.md.get_cfg_text()
        self.assertIn("Density=16\n", text)
        self.assertIn("Freq=3200\n", text)
        self.assertIn("LOG_TO_UART1=1\n", text)                # 出厂默认键

    def test_disabled_503(self):
        md = ManualDebug({"manual_debug": {"enabled": False}})
        with self.assertRaises(ManualDebugError) as ctx:
            md.apply_settings({"runMode": "full_run"}, self.cfg_path)
        self.assertEqual(ctx.exception.status, 503)

    def test_apply_power_off_on_fail(self):
        """判 FAIL 自动下电开关：camelCase 与 snake_case 别名都可写，
        非法值 400，session json 存 snake_case"""
        r = self.md.apply_settings({"powerOffOnFail": False}, self.cfg_path)
        self.assertFalse(r["powerOffOnFail"])
        self.assertFalse(self.md.power_off_on_fail)
        r = self.md.apply_settings({"power_off_on_fail": True}, self.cfg_path)
        self.assertTrue(r["powerOffOnFail"])
        with self.assertRaises(ManualDebugError) as ctx:
            self.md.apply_settings({"powerOffOnFail": "yes"}, self.cfg_path)
        self.assertEqual(ctx.exception.status, 400)
        saved = json.load(open(os.path.join(self.tmp.name,
                                            "session_settings.json"),
                               encoding="utf-8"))
        self.assertIs(saved["power_off_on_fail"], True)

    def test_apply_power_off_on_pass(self):
        """PASS 自动下电开关（2026-10-10 用户拍板）：默认 True，写法/校验/
        持久化与 powerOffOnFail 对称"""
        self.assertIs(self.md.power_off_on_pass, True)      # 默认开
        r = self.md.apply_settings({"powerOffOnPass": False}, self.cfg_path)
        self.assertFalse(r["powerOffOnPass"])
        self.assertFalse(self.md.power_off_on_pass)
        r = self.md.apply_settings({"power_off_on_pass": True}, self.cfg_path)
        self.assertTrue(r["powerOffOnPass"])
        self.assertTrue(self.md.power_off_on_pass)
        with self.assertRaises(ManualDebugError) as ctx:
            self.md.apply_settings({"powerOffOnPass": 1}, self.cfg_path)
        self.assertEqual(ctx.exception.status, 400)
        saved = json.load(open(os.path.join(self.tmp.name,
                                            "session_settings.json"),
                               encoding="utf-8"))
        self.assertIs(saved["power_off_on_pass"], True)

    def test_apply_dutlines(self):
        """dutLines（导入恢复 DUT 配置）：线表整体替换，通道表截齐/补全"""
        # CFG 夹具未配 dut_channels → 默认 [1,2,3,4]
        r = self.md.apply_settings({"dutLines": [0, 2]}, self.cfg_path)
        self.assertEqual(self.md.dut_lines, [0, 2])
        self.assertEqual(self.md.dut_channels, [1, 2])   # 截齐到新长度
        self.assertEqual(sorted(self.md._power), [1, 2])
        self.assertTrue(all(not v for v in self.md._power.values()))
        self.assertEqual(r["dutChannels"], [1, 2])
        # 补全方向：扩到 3 路 → 最小未占用补 3
        r = self.md.apply_settings({"dutLines": [0, 2, 4]}, self.cfg_path)
        self.assertEqual(self.md.dut_channels, [1, 2, 3])
        # 同给通道表：长度须一致
        r = self.md.apply_settings({"dutLines": [0, 2, 4],
                                    "dutChannels": [1, 3, 5]}, self.cfg_path)
        self.assertEqual(self.md.dut_lines, [0, 2, 4])
        self.assertEqual(self.md.dut_channels, [1, 3, 5])
        with self.assertRaises(ManualDebugError) as ctx:
            self.md.apply_settings({"dutLines": [0, 2],
                                    "dutChannels": [1, 3, 5]}, self.cfg_path)
        self.assertEqual(ctx.exception.status, 400)

    def test_apply_dutlines_powered_on_rejected(self):
        self.md._power[1] = True                          # 模拟上电中
        with self.assertRaises(ManualDebugError) as ctx:
            self.md.apply_settings({"dutLines": [0, 2]}, self.cfg_path)
        self.assertEqual(ctx.exception.status, 400)
        self.assertIn("下电", str(ctx.exception))
        self.assertEqual(self.md.dut_lines, [4, 5, 6, 7])  # 拒绝后不动

    def test_apply_dutlines_validation(self):
        for bad in ([], [0, 0], [8], ["x"], "04", list(range(9))):
            with self.assertRaises(ManualDebugError) as ctx:
                self.md.apply_settings({"dutLines": bad}, self.cfg_path)
            self.assertEqual(ctx.exception.status, 400, bad)

    def test_apply_snake_case_aliases(self):
        """「读取设置」导入 session json（snake_case 键）→ 别名映射生效；
        dut_count 静默跳过不报「未知设置项」"""
        r = self.md.apply_settings(
            {"board_host": "192.168.50.101", "run_mode": "full_run",
             "dut_count": 4, "dut_lines": [0, 2],
             "dut_channels": [1, 3]}, self.cfg_path)
        self.assertEqual(r["boardHost"], "192.168.50.101")
        self.assertEqual(r["runMode"], "full_run")
        self.assertEqual(self.md.dut_lines, [0, 2])
        self.assertEqual(self.md.dut_channels, [1, 3])
        # 保存的 session json 仍是 snake_case（下次启动可加载）
        import json
        saved = json.load(open(os.path.join(self.tmp.name,
                                            "session_settings.json"),
                               encoding="utf-8"))
        self.assertEqual(saved["dut_lines"], [0, 2])
        self.assertEqual(saved["dut_channels"], [1, 3])

    def test_ch_maps_dut_to_channel(self):
        """序号 → 真实通道号（2026-09-23：界面/日志归属/落盘的统一身份）"""
        import tempfile
        with tempfile.TemporaryDirectory() as d:      # 隔离 session 覆盖层
            md = ManualDebug({"manual_debug": {
                "enabled": True, "dut_count": 4, "dut_lines": [4, 5, 6, 7],
                "dut_channels": [5, 6, 7, 8]}}, data_dir=d)
            self.assertEqual([md.ch(i) for i in range(1, 5)], [5, 6, 7, 8])
            self.assertEqual(md.ch(0), 0)                        # 越界回退序号
            self.assertEqual(md.ch(9), 9)
            # 未配置 dut_channels → 回退序号本身（mock/单测形态）
            self.assertEqual(ManualDebug(CFG, data_dir=d).ch(2), 2)


class TestSyncServerIp(unittest.TestCase):
    def test_bind_and_directed_broadcast(self):
        """绑定本机 IP + 网段定向广播（Windows 多网卡坑的回归钉）"""
        import tempfile
        with tempfile.TemporaryDirectory() as d:      # 隔离 session 覆盖层
            md = ManualDebug(CFG, data_dir=d)
            calls = []

            def fake_discover(timeout=3.0, broadcast_addrs=None, bind_ip=None):
                calls.append({"timeout": timeout,
                              "broadcast_addrs": broadcast_addrs,
                              "bind_ip": bind_ip})
                return [{"device_id": 1, "serial": 2, "addr": "192.168.50.100"}]

            orig = commboard.discover
            commboard.discover = fake_discover
            self.addCleanup(setattr, commboard, "discover", orig)
            r = md.sync_server_ip()
            self.assertEqual(calls[0]["bind_ip"], "192.168.50.10")
            self.assertEqual(calls[0]["broadcast_addrs"], ["192.168.50.255"])
            self.assertTrue(r["boardSeen"])

            commboard.discover = lambda **k: []
            r = md.sync_server_ip()
            self.assertFalse(r["boardSeen"])


class TestManualRunner(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mdbg = types.SimpleNamespace(
            dut_lines=[4, 5, 6, 7], passthrough_base=2001,
            dut_port=lambda d: 43000 + d,  # 与 port_base=43001 旧语义一致
            board_host="192.0.2.1", ready_timeout_sec=180,
            run_mode="full_run", dut_channels=[5, 6, 7, 8],
            get_cfg_text=lambda: "Density=16\nFreq=3200\n")
        self.hub = FakeHub()
        self.mdbg.log_drain_sec = 0  # 本夹具测握手；真实尾日志窗口由 test_state_lifecycle 验证
        self.runner = ManualRunner(self.mdbg, self.hub, port_base=43001)

    async def asyncSetUp(self):
        await self.runner.start()
        # 替换为假 transport，抓发送帧（真 transport 会往 TEST-NET 地址发包）
        for d in list(self.runner._transports):
            self.runner._transports[d].close()
            self.runner._transports[d] = FakeTransport()

    async def asyncTearDown(self):
        await self.runner.close()

    def _sent_to(self, dut):
        return self.runner._transports[dut].sent

    def _arm_to_running(self, dut):
        """arm → READY → ACK 推到 running 终态前一站"""
        self.runner.arm(dut)
        self.runner.on_datagram(dut, ready_frame())
        self.runner.on_datagram(dut, ack_frame(0))
        self.assertEqual(self.runner.state(dut)["state"], ST_RUNNING)

    async def test_fail_auto_power_off(self):
        """FAIL 终态 → 自动下电（桩 set_power 断言被调），syslog 有记录"""
        calls = []
        self.mdbg.set_power = lambda d, on: calls.append((d, on))
        self.mdbg.power_off_on_fail = True
        self._arm_to_running(1)
        self.runner.on_datagram(1, done_frame(1))    # 测试 FAIL
        self.assertEqual(self.runner.state(1)["state"], ST_FAIL)
        await asyncio.sleep(0.05)                    # 等后台下电 task
        self.assertEqual(calls, [(1, False)])
        msgs = [m for _, _, lv, m, _ in self.hub.logs if lv == "INFO"]
        self.assertTrue(any("已自动下电" in m for m in msgs))

    async def test_timeout_auto_power_off(self):
        """timeout 终态同样触发自动下电"""
        calls = []
        self.mdbg.set_power = lambda d, on: calls.append((d, on))
        self.mdbg.power_off_on_fail = True
        self.runner._set(2, ST_TIMEOUT, "180s 内未就绪")
        await asyncio.sleep(0.05)
        self.assertEqual(calls, [(2, False)])

    async def test_pass_auto_power_off_default(self):
        """PASS 默认也自动下电（2026-10-10 用户拍板），syslog 报 PASS"""
        calls = []
        self.mdbg.set_power = lambda d, on: calls.append((d, on))
        self.mdbg.power_off_on_fail = True
        self.mdbg.power_off_on_pass = True
        self._arm_to_running(1)
        self.runner.on_datagram(1, done_frame(0))    # PASS
        self.assertEqual(self.runner.state(1)["state"], ST_PASS)
        await asyncio.sleep(0.05)
        self.assertEqual(calls, [(1, False)])
        msgs = [m for _, _, lv, m, _ in self.hub.logs if lv == "INFO"]
        self.assertTrue(any("测试 PASS，已自动下电" in m for m in msgs))

    async def test_pass_power_off_switchable(self):
        """power_off_on_pass=False → PASS 保持上电人工处置"""
        calls = []
        self.mdbg.set_power = lambda d, on: calls.append((d, on))
        self.mdbg.power_off_on_fail = True
        self.mdbg.power_off_on_pass = False
        self._arm_to_running(1)
        self.runner.on_datagram(1, done_frame(0))    # PASS
        self.assertEqual(self.runner.state(1)["state"], ST_PASS)
        await asyncio.sleep(0.05)
        self.assertEqual(calls, [])

    async def test_pass_off_switch_does_not_affect_fail(self):
        """power_off_on_pass=False 不影响 FAIL 仍自动下电（两开关独立）"""
        calls = []
        self.mdbg.set_power = lambda d, on: calls.append((d, on))
        self.mdbg.power_off_on_fail = True
        self.mdbg.power_off_on_pass = False
        self._arm_to_running(1)
        self.runner.on_datagram(1, done_frame(1))    # FAIL
        self.assertEqual(self.runner.state(1)["state"], ST_FAIL)
        await asyncio.sleep(0.05)
        self.assertEqual(calls, [(1, False)])

    async def test_switch_off_no_power_off(self):
        """power_off_on_fail=false → FAIL 也不下电"""
        calls = []
        self.mdbg.set_power = lambda d, on: calls.append((d, on))
        self.mdbg.power_off_on_fail = False
        self.runner._set(1, ST_FAIL, "item-x")
        await asyncio.sleep(0.05)
        self.assertEqual(calls, [])

    async def test_power_off_error_does_not_crash(self):
        """自动下电抛异常（通讯板离线）：状态机照常收尾，记 ERROR"""
        def boom(d, on):
            raise OSError("board offline")
        self.mdbg.set_power = boom
        self.mdbg.power_off_on_fail = True
        self.runner._set(1, ST_FAIL, "item-x")
        self.assertEqual(self.runner.state(1)["state"], ST_FAIL)
        await asyncio.sleep(0.05)
        errs = [m for _, _, lv, m, _ in self.hub.logs if lv == "ERROR"]
        self.assertTrue(any("自动下电失败" in m for m in errs))

    async def test_auto_power_off_survives_index_shift(self):
        """竞态修复（2026-10-10）：FAIL 后、后台下电 task 执行前发生
        remove 导致序号位移——按通道号重解析，下的仍是原来 FAIL 那路
        （旧 dut 序号 3 → 移除第 1 路后位移为 2，线号/通道配对不变）"""
        calls = []
        self.mdbg.set_power = lambda d, on: calls.append((d, on))
        self.mdbg.power_off_on_fail = True
        self.runner._set(3, ST_FAIL, "item-x")       # 旧序号 3，通道 7
        # task 尚未执行，模拟 main.py 移除第 1 路：mdbg 列表收缩 + runner 平移
        self.mdbg.dut_lines.pop(0)
        self.mdbg.dut_channels.pop(0)                # 通道表 [6,7,8]，ch7 → 序号 2
        self.runner.drop_dut(1)
        await asyncio.sleep(0.05)                    # 此刻才放行后台 task
        self.assertEqual(calls, [(2, False)])        # 不是旧序号 3（会下错路）

    async def test_auto_power_off_skips_removed_channel(self):
        """竞态修复：FAIL 的那路本身在 task 执行前被移除 → 跳过下电并记
        WARN，绝不拿旧序号去下别的路"""
        calls = []
        self.mdbg.set_power = lambda d, on: calls.append((d, on))
        self.mdbg.power_off_on_fail = True
        self.runner._set(2, ST_FAIL, "item-x")       # 通道 6
        self.mdbg.dut_lines.pop(1)
        self.mdbg.dut_channels.pop(1)                # 通道表 [5,7,8]，ch6 没了
        self.runner.drop_dut(2)
        await asyncio.sleep(0.05)
        self.assertEqual(calls, [])
        warns = [m for _, _, lv, m, _ in self.hub.logs if lv == "WARN"]
        self.assertTrue(any("跳过自动下电" in m for m in warns))

    async def test_state_change_triggers_on_change(self):
        """事件驱动（2026-10-10）：每次状态转换都调 on_change（main.py 注入
        的 manual_state 推送回调）；快照带 enteredAt（服务端墙钟）供前端
        活跃态本地平滑 tick，idle 初态为 None"""
        calls = []
        self.runner.on_change = lambda: calls.append(1)
        self.runner.arm(1)                           # idle → wait_ready
        self.runner.on_datagram(1, ready_frame())    # → cfg_sent
        self.runner.on_datagram(1, ack_frame(0))     # → running
        self.runner.on_datagram(1, done_frame(0))    # → pass
        self.assertEqual(len(calls), 4)              # 每次转换各一次
        snap = self.runner.snapshot()["duts"]
        self.assertIsInstance(snap[0]["enteredAt"], float)
        self.assertIsNone(snap[1]["enteredAt"])      # idle 未进过状态

    async def test_auto_power_off_broadcasts_again(self):
        """自动下电完成后再推一次 on_change（powerOn → False 即时上屏）"""
        self.mdbg.set_power = lambda d, on: None
        self.mdbg.power_off_on_fail = True
        calls = []
        self.runner.on_change = lambda: calls.append(1)
        self.runner._set(1, ST_FAIL, "item-x")       # 转换推第 1 次
        await asyncio.sleep(0.05)                    # 下电 task 完成推第 2 次
        self.assertEqual(len(calls), 3)              # FAIL → 下电中 → 下电完成

    async def test_timer_freezes_on_terminal(self):
        """下电即暂停（2026-10-10）：FAIL 终态后 sinceSec 冻结不再增长；
        重新 arm（重新上电）从零重计"""
        self.mdbg.set_power = lambda d, on: None    # 自动下电桩
        self.mdbg.power_off_on_fail = True
        self._arm_to_running(1)
        self.runner.on_datagram(1, done_frame(1))    # FAIL（自动下电路径）
        self.assertEqual(self.runner.state(1)["state"], ST_FAIL)
        s1 = self.runner.snapshot()["duts"][0]["sinceSec"]
        await asyncio.sleep(0.1)
        s2 = self.runner.snapshot()["duts"][0]["sinceSec"]
        self.assertEqual(s1, s2)                     # 冻结：两次快照相同
        # timeout 同样冻结
        self.runner._set(2, ST_TIMEOUT, "x")
        t1 = self.runner.snapshot()["duts"][1]["sinceSec"]
        await asyncio.sleep(0.1)
        t2 = self.runner.snapshot()["duts"][1]["sinceSec"]
        self.assertEqual(t1, t2)
        # 重新布防（重新上电）→ 从零重计
        self.runner.arm(1)
        self.assertEqual(self.runner.state(1)["state"], ST_WAIT_READY)
        await asyncio.sleep(0.05)
        s3 = self.runner.snapshot()["duts"][0]["sinceSec"]
        self.assertLessEqual(s3, 1)                  # 重新计数（旧值不复活）

    async def test_timer_freezes_on_manual_power_off(self):
        """手动/全部下电（disarm → idle）也冻结计数"""
        self.runner.arm(1)
        await asyncio.sleep(0.05)
        self.runner.disarm(1)
        s1 = self.runner.snapshot()["duts"][0]["sinceSec"]
        await asyncio.sleep(0.1)
        s2 = self.runner.snapshot()["duts"][0]["sinceSec"]
        self.assertEqual(s1, s2)

    async def test_sync_duts_after_add(self):
        """运行期 add_dut 后 sync_duts：补状态表 + 绑新透传端口；幂等"""
        self.mdbg.dut_lines.append(0)
        self.mdbg.dut_channels.append(1)
        # 夹具 dut_port = lambda d: 43000+d → 新 DUT5 绑 43005
        await self.runner.sync_duts()
        self.assertIn(5, self.runner._st)
        self.assertEqual(self.runner.state(5)["state"], ST_IDLE)
        self.assertEqual(self.runner.state(5)["channel"], 1)
        self.assertIn(5, self.runner._transports)
        self.runner.arm(5)                          # 新 DUT 立即可布防
        self.assertEqual(self.runner.state(5)["state"], ST_WAIT_READY)
        await self.runner.sync_duts()               # 重复调用不重复绑定
        self.assertEqual(len(self.runner._duts), 5)

    async def test_drop_dut_then_readd(self):
        """drop_dut：被移除路 transport 关闭、其余按键位平移（通道身份与
        状态保留）；之后可重新 add 同一通道"""
        self.runner.arm(3)      # dut3（通道 7）活动态——平移后应保留
        self.assertEqual(self.runner.state(3)["state"], ST_WAIT_READY)
        # 模拟 remove_dut 收缩列表（配对不变）：去掉线号 5 / 通道 6
        self.mdbg.dut_lines.pop(1)
        self.mdbg.dut_channels.pop(1)               # → [5,7,8]
        self.runner.drop_dut(2)
        self.assertEqual(sorted(self.runner._st), [1, 2, 3])
        self.assertEqual(sorted(self.runner._transports), [1, 2, 3])
        # 原 dut3（通道 7，wait_ready）平移到序号 2，状态与通道身份保留
        self.assertEqual(self.runner.state(2)["state"], ST_WAIT_READY)
        self.assertEqual(self.runner.state(2)["channel"], 7)
        self.assertEqual(self.runner.state(3)["channel"], 8)
        # 重新 add 同一通道（最小未占用又轮到 6）：sync_duts 绑新端口
        self.mdbg.dut_lines.append(5)
        self.mdbg.dut_channels.append(6)
        await self.runner.sync_duts()
        self.assertEqual(self.runner.state(4)["state"], ST_IDLE)
        self.assertEqual(self.runner.state(4)["channel"], 6)
        self.assertIn(4, self.runner._transports)
        self.runner.arm(4)                          # 立即可布防
        self.assertEqual(self.runner.state(4)["state"], ST_WAIT_READY)

    async def test_resync_after_dutlines_import(self):
        """线表整体替换（apply_settings 导入 dutLines）→ resync 全量重建：
        状态归 idle、按键位重绑新端口、可立即布防"""
        self.runner.arm(1)                          # 先有活动态
        self.assertEqual(self.runner.state(1)["state"], ST_WAIT_READY)
        # 模拟 apply_settings 替换线表：4 路 → 2 路，配对全变
        self.mdbg.dut_lines = [0, 2]
        self.mdbg.dut_channels = [1, 3]
        await self.runner.resync()
        self.assertEqual(self.runner._duts, [1, 2])
        self.assertEqual(sorted(self.runner._st), [1, 2])
        self.assertEqual(self.runner.state(1)["state"], ST_IDLE)
        self.assertEqual(self.runner.state(1)["channel"], 1)
        self.assertEqual(self.runner.state(2)["channel"], 3)
        self.assertEqual(sorted(self.runner._transports), [1, 2])
        self.runner.arm(2)                          # 新配置立即可布防
        self.assertEqual(self.runner.state(2)["state"], ST_WAIT_READY)

    async def test_full_handshake(self):
        """arm → wait_ready →(READY)→ cfg_sent + 发 0x15 →(ACK)→ running"""
        self.runner.arm(1)
        self.assertEqual(self.runner.state(1)["state"], ST_WAIT_READY)
        self.runner.on_datagram(1, ready_frame())
        st = self.runner.state(1)
        self.assertEqual(st["state"], ST_CFG_SENT)
        self.assertIn("版本", st["detail"])
        # READY 后同窗连发两帧：0x10 ACK（9B 固定形态）+ 0x15 cfg（TBSM02 实证时序）
        self.assertEqual(len(self._sent_to(1)), 2)
        ackframe, addr = self._sent_to(1)[0]
        self.assertEqual(addr, ("192.0.2.1", 43001))
        self.assertEqual(ackframe, bytes([0xAF, 0x02, 0x00, 0x00, 0x10,
                                          0x00, 0x00, 0x55, 0xEF]))
        frame, addr = self._sent_to(1)[1]
        self.assertEqual(addr, ("192.0.2.1", 43001))
        self.assertEqual(frame[0], 0xAF)
        self.assertEqual(frame[4], CMD_START_TEST)
        self.assertIn(b"Density=16\n", frame)
        self.runner.on_datagram(1, ack_frame(0))
        self.assertEqual(self.runner.state(1)["state"], ST_RUNNING)

    async def test_cfg_resend_until_ack(self):
        """旧码 StartRetryTimer(5000) 语义：CFG_SENT 态周期重发（加速验证）"""
        import app.manualrun as mr
        orig = mr.RESEND_SEC
        mr.RESEND_SEC = 0.05
        self.addCleanup(setattr, mr, "RESEND_SEC", orig)
        self.runner.arm(2)
        self.runner.on_datagram(2, ready_frame())
        await asyncio.sleep(0.13)
        self.assertGreaterEqual(len(self._sent_to(2)), 2)      # 首发 + ≥1 次重发
        self.runner.on_datagram(2, ack_frame(0))
        n = len(self._sent_to(2))
        await asyncio.sleep(0.12)
        self.assertEqual(len(self._sent_to(2)), n)             # ACK 后停发

    async def test_ack_nonzero_fail(self):
        self.runner.arm(1)
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, ack_frame(3))
        st = self.runner.state(1)
        self.assertEqual(st["state"], ST_FAIL)
        self.assertIn("status=3", st["detail"])

    async def test_timeout(self):
        self.mdbg.ready_timeout_sec = 0.1
        self.runner.arm(3)
        await asyncio.sleep(0.25)
        self.assertEqual(self.runner.state(3)["state"], ST_TIMEOUT)

    async def test_done_pass_fail(self):
        self.runner.arm(1)
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, ack_frame(0))
        self.runner.on_datagram(1, done_frame(0))
        self.assertEqual(self.runner.state(1)["state"], ST_PASS)

        self.runner.arm(2)
        self.runner.on_datagram(2, ready_frame())
        self.runner.on_datagram(2, ack_frame(0))
        self.runner.on_datagram(2, done_frame(2))
        st = self.runner.state(2)
        self.assertEqual(st["state"], ST_FAIL)
        self.assertEqual(st["detail"], "signal_fail")

    async def test_ready_while_running_latches_fail_without_cfg(self):
        """重启只回 READY ACK，本轮失败，不重发 CFG 或延长计时。"""
        self._arm_to_running(1)
        before = self.runner.state(1)
        count = len(self._sent_to(1))
        self.runner.on_datagram(1, ready_frame())
        after = self.runner.state(1)
        self.assertEqual((after["state"], after["detail"]), (ST_FAIL, "dut_reboot"))
        self.assertEqual((after["runId"], after["t0"]), (before["runId"], before["t0"]))
        self.assertEqual(len(self._sent_to(1)), count + 1)
        self.assertEqual(self._sent_to(1)[-1][0][4], CMD_READY)
        self.assertEqual(self.hub.results[-1][:4], (1, 5, "FAIL", "dut_reboot"))
        for tasks in (self.runner._resend, self.runner._timer,
                      self.runner._runwatch, self.runner._progtask):
            self.assertNotIn(1, tasks)

    async def test_reboot_failure_ignores_late_ready_ack_and_pass(self):
        self._arm_to_running(1)
        self.runner.on_datagram(1, ready_frame())
        frozen = self.runner.state(1)
        for packet in (ready_frame(), ack_frame(), done_frame(), done_frame(1)):
            self.runner.on_datagram(1, packet)
        await asyncio.sleep(.03)
        self.assertEqual(self.runner.state(1)["state"], ST_FAIL)
        self.assertEqual(self.runner.state(1)["detail"], "dut_reboot")
        self.assertEqual(self.runner.state(1)["t1"], frozen["t1"])
        self.assertEqual(len(self.hub.results), 1)
        cfg_packets = [p for p, _ in self._sent_to(1) if p[4] == CMD_START_TEST]
        self.assertEqual(len(cfg_packets), 1)

    async def test_explicit_new_run_after_reboot_failure(self):
        self._arm_to_running(1)
        self.runner.on_datagram(1, ready_frame())
        old_id = self.runner.state(1)["runId"]
        self.assertEqual(self.runner.state(1)["state"], ST_FAIL)
        self.runner.disarm(1)
        self._arm_to_running(1)
        self.assertNotEqual(self.runner.state(1)["runId"], old_id)
        self.runner.on_datagram(1, done_frame())
        self.assertEqual(self.runner.state(1)["state"], ST_PASS)
        self.assertEqual([row[2] for row in self.hub.results], ["FAIL", "PASS"])

    async def test_duplicate_ready_before_cfg_ack_is_not_reboot(self):
        self.runner.arm(1)
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, ready_frame())
        self.assertEqual(self.runner.state(1)["state"], ST_CFG_SENT)
        self.assertEqual(self.hub.results, [])
        cfg_packets = [p for p, _ in self._sent_to(1) if p[4] == CMD_START_TEST]
        self.assertEqual(len(cfg_packets), 1)
        self.runner.on_datagram(1, ack_frame())
        self.assertEqual(self.runner.state(1)["state"], ST_RUNNING)

    async def test_disarm(self):
        self.runner.arm(1)
        self.runner.disarm(1)
        self.assertEqual(self.runner.state(1)["state"], ST_IDLE)
        self.runner.on_datagram(1, ready_frame())              # idle 态 READY 忽略
        self.assertEqual(self.runner.state(1)["state"], ST_IDLE)
        self.assertEqual(self._sent_to(1), [])

    async def test_snapshot(self):
        self.runner.arm(1)
        snap = self.runner.snapshot()
        self.assertEqual(snap["mode"], "full_run")
        self.assertEqual(len(snap["duts"]), 4)
        self.assertEqual(snap["duts"][0]["state"], ST_WAIT_READY)
        self.assertEqual(snap["duts"][1]["state"], ST_IDLE)

    async def test_logs_and_state_use_real_channel(self):
        """2026-09-23「界面 DUT 改真实值」：日志归属/CH 标签/状态快照用通道号
        （dut_channels=[5,6,7,8] → 序号 1 的日志落在 slot 5）"""
        self.runner.arm(1)
        self.runner.on_datagram(1, ready_frame())
        self.runner.on_datagram(1, ack_frame(0))
        self.runner.on_datagram(1, done_frame(0))
        # 只看通道级日志（start() 的 syslog 是系统级 slot=None，不算）
        dut_logs = [l for l in self.hub.logs if l[1] is not None]
        self.assertEqual({l[1] for l in dut_logs}, {5})    # 全部落在通道 5
        self.assertTrue(all("CH05" in l[3] for l in dut_logs))
        snap = self.runner.snapshot()
        self.assertEqual(snap["duts"][0]["channel"], 5)
        self.assertEqual(snap["duts"][3]["channel"], 8)

    async def test_publishes_hub_state(self):
        """2026-09-24 手动链路驱动 dut_status：卡片连接灯/TESTING/PASS 时长
        （此前手动链路不写 hub,心跳会话又收不到回包 → 卡片恒离线）"""
        self.runner.arm(1)
        kw = self.hub.updates[-1][2]
        self.assertEqual((self.hub.updates[-1][1], kw["state"], kw["connected"]),
                         (5, "TESTING", False))              # 上电等待属于测试流程
        self.runner.on_datagram(1, ready_frame())
        kw = self.hub.updates[-1][2]
        self.assertEqual((self.hub.updates[-1][1], kw["state"], kw["step"]),
                         (5, "TESTING", "下发配置"))
        self.assertTrue(kw["connected"])
        self.runner.on_datagram(1, ack_frame(0))
        kw = self.hub.updates[-1][2]
        self.assertEqual((self.hub.updates[-1][1], kw["state"], kw["step"]),
                         (5, "TESTING", "测试运行中"))
        self.runner.on_datagram(1, done_frame(0))
        self.assertEqual(self.hub.results[-1][:3], (1, 5, "PASS"))
        self.assertGreaterEqual(self.hub.results[-1][4], 0)   # 带运行时长
        self.assertIsInstance(self.hub.results[-1][4], float)   # 2026-09-24:整数秒
        self.assertIsInstance(self.runner.snapshot()["duts"][0]["sinceSec"], int)

    async def test_publishes_offline_and_idle_ready(self):
        """下电 → OFFLINE;power_only 的 IDLE 态收到 READY → 点亮连接灯"""
        self.runner.arm(2)
        self.runner.on_datagram(2, ready_frame())         # 先跑到 cfg_sent
        self.runner.disarm(2)                             # 下电
        kw = self.hub.updates[-1][2]
        self.assertEqual((self.hub.updates[-1][1], kw["state"], kw["connected"]),
                         (6, "OFFLINE", False))
        self.runner.on_datagram(2, ready_frame())         # 下电后的杂散 READY 不能重新上线
        kw = self.hub.updates[-1][2]
        self.assertEqual((kw["state"], kw["connected"]), ("OFFLINE", False))
        self.mdbg.run_mode = "power_only"
        self.runner._new_idle(2)                          # 明确新上电，才接受新 READY
        self.runner.on_datagram(2, ready_frame())
        kw = self.hub.updates[-1][2]
        self.assertEqual((kw["state"], kw["connected"]), ("IDLE", True))

    async def test_sink_keyed_by_real_channel(self):
        """落盘会话键 = 通道号：running 后 63001 的 [DUT5] 行落 dut5.log"""
        with tempfile.TemporaryDirectory() as d:
            sink = DutLogFileSink()
            sink.set_dir(d)
            self.runner.file_sink = sink
            self.runner.arm(1)
            self.runner.on_datagram(1, ready_frame())
            self.runner.on_datagram(1, ack_frame(0))
            self.assertIn(5, sink._ts)                       # 键是通道号 5，不是序号 1
            sink.write("[DUT5] hello")
            ts_dir = os.path.join(d, os.listdir(d)[0])
            self.assertEqual(os.listdir(ts_dir), ["dut5.log"])
            with open(os.path.join(ts_dir, "dut5.log"),
                      encoding="utf-8") as f:
                self.assertIn("[DUT5] hello", f.read())
            sink.set_dir("")                                 # 关句柄，Windows 才能清临时目录


class TestBoardHealthMonitor(unittest.IsolatedAsyncioTestCase):
    """[2026-09-28 强逻辑] 通讯板坏 → 所连全部测试板立即离线（边沿触发）"""

    def setUp(self):
        self.hub = FakeHub()
        self.board_ok = True

        def board_state():
            if not self.board_ok:
                raise RuntimeError("通讯板无应答")
            return {"ok": True, "state": "NONE"}

        self.mdbg = types.SimpleNamespace(
            board_host="192.0.2.1", dut_lines=[4, 5, 6, 7],
            dut_channels=[5, 6, 7, 8],
            ch=lambda d: d + 4, board_state=board_state)

    async def test_down_edge_offlines_all(self):
        mon = BoardHealthMonitor(self.mdbg, self.hub)
        self.assertTrue(await mon.check())          # 首查建基线：不广播
        self.assertEqual(self.hub.updates, [])
        self.board_ok = False
        self.assertFalse(await mon.check())         # 掉线边沿：批量 OFFLINE
        self.assertEqual(len(self.hub.updates), 4)
        self.assertEqual([slot for _, slot, _ in self.hub.updates],
                         [5, 6, 7, 8])              # 按真实通道号下线
        for _, _, kw in self.hub.updates:
            self.assertEqual((kw["state"], kw["connected"]),
                             ("OFFLINE", False))
            self.assertEqual(kw["testInfo"], "通讯板离线")
        self.assertTrue(any("全部离线" in l[3] for l in self.hub.logs))
        n = len(self.hub.updates)
        self.assertFalse(await mon.check())         # 持续离线：不重复广播
        self.assertEqual(len(self.hub.updates), n)

    async def test_recovery_edge_only_logs(self):
        mon = BoardHealthMonitor(self.mdbg, self.hub)
        await mon.check()
        self.board_ok = False
        await mon.check()                           # → 离线
        n = len(self.hub.updates)
        self.board_ok = True
        self.assertTrue(await mon.check())          # 恢复边沿：仅 INFO，不动状态
        self.assertEqual(len(self.hub.updates), n)  # 等回帧自然上线
        self.assertTrue(any("恢复" in l[3] for l in self.hub.logs))


class TestDutLogFileSink(unittest.TestCase):
    def test_write_and_disable(self):
        with tempfile.TemporaryDirectory() as d:
            sink = DutLogFileSink()
            sink.write("ignored")                              # 未设目录不落盘
            self.assertEqual(os.listdir(d), [])
            sink.set_dir(d)
            # 未 begin_run 的 DUT 行与系统行都不落盘
            sink.write("[DUT1] before-run")                    # 未运行 → 丢弃
            sink.write("system line without tag")              # 总览 → 丢弃
            self.assertEqual(os.listdir(d), [])
            sink.begin_run(1)                                  # DUT1 进入运行
            sink.write("[DUT1] hello")
            sink.write("[DUT2] world")                         # DUT2 未运行 → 丢弃
            # 2026-09-20 层级修订：<dir>/<ts>/dut1.log
            ts_dirs = os.listdir(d)
            self.assertEqual(len(ts_dirs), 1)                  # 一个时间戳文件夹
            ts_dir = os.path.join(d, ts_dirs[0])
            self.assertTrue(all(c.isdigit() or c == "_" for c in ts_dirs[0]))
            files = os.listdir(ts_dir)
            self.assertEqual(files, ["dut1.log"])              # 文件名不带时间戳
            content = open(os.path.join(ts_dir, files[0]), encoding="utf-8").read()
            self.assertIn("[DUT1] hello", content)
            self.assertNotIn("world", content)
            sink.end_run(1)                                    # 结束 → 后续丢弃
            sink.write("[DUT1] after-run")
            content = open(os.path.join(ts_dir, files[0]), encoding="utf-8").read()
            self.assertNotIn("after-run", content)
            sink.set_dir("")                                   # 关停
            sink.write("nope")

    def test_unwritable_dir_survives(self):
        """2026-09-29 修订：落盘故障不再自禁用（旧缺陷=一条 OSError 把整个
        sink 静默关死且无日志）——现在丢当条、warner 告警、换回可写目录即恢复。"""
        warns = []
        sink = DutLogFileSink(warner=warns.append)
        sink.set_dir(os.path.join("Z:\\__no_such_drive__", "x")
                     if os.name == "nt" else "/proc/__no_such__/x")
        sink.begin_run(1)
        sink.write("[DUT1] line")                    # 不抛异常，只丢当条
        self.assertNotEqual(sink._dir, "")           # 不再清 _dir 自禁用
        self.assertEqual(len(warns), 1)              # 告警可见（旧缺陷的盲点）
        with tempfile.TemporaryDirectory() as d:
            sink.set_dir(d)                          # 换回可写目录 → 恢复落盘
            sink.begin_run(1)
            sink.write("[DUT1] back")
            ts_dir = os.path.join(d, os.listdir(d)[0])
            with open(os.path.join(ts_dir, "dut1.log"), encoding="utf-8") as f:
                self.assertIn("[DUT1] back", f.read())
            sink.set_dir("")                          # 关句柄，Windows 才能清临时目录


if __name__ == "__main__":
    unittest.main(verbosity=2)
