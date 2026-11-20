"""只开机模式强制（2026-09-29 用户拍板）：power_only 下任何路径都不下发 cfg。

回归背景：on_datagram 的"DUT 重启自动重发"分支（READY→RUNNING/PASS/FAIL）原本
不查 run_mode——上一轮测完处于终态的通道，切"只开机"后再上电，DUT 一发 READY
就重新收到 cfg。拍板行为：**只开机=只发上电指令；完整运行=全链路**。
"""

import types
import unittest

from app.manualrun import (ManualRunner, ST_RUNNING, ST_PASS, ST_FAIL,
                           ST_CFG_SENT)
from app.protocol import build_frame, ROLE_SLAVE, CMD_AGING_REQ
from tests.test_manual_settings import (FakeHub, FakeTransport, ready_frame)


def aging_req_frame(minutes: int = 5) -> bytes:
    return build_frame(ROLE_SLAVE, CMD_AGING_REQ,
                       bytes([minutes & 0xFF, (minutes >> 8) & 0xFF]))


class TestPowerOnlyGate(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mdbg = types.SimpleNamespace(
            dut_lines=[4, 5, 6, 7], passthrough_base=2001,
            dut_port=lambda d: 43000 + d,
            board_host="192.0.2.1", ready_timeout_sec=180,
            run_mode="power_only", dut_channels=[5, 6, 7, 8],
            get_cfg_text=lambda: "Density=16\nFreq=3200\n")
        self.hub = FakeHub()
        self.runner = ManualRunner(self.mdbg, self.hub, port_base=43001)

    async def asyncSetUp(self):
        await self.runner.start()
        for d in list(self.runner._transports):
            self.runner._transports[d].close()
            self.runner._transports[d] = FakeTransport()

    async def asyncTearDown(self):
        await self.runner.close()

    def _sent(self, dut=1):
        return self.runner._transports[dut].sent

    def _warns(self):
        return [m for _, _, lv, m, _ in self.hub.logs if lv == "WARN"]

    async def test_reboot_after_pass_no_cfg(self):
        """上轮 PASS 残留 + 只开机：DUT 重发 READY 不触发 cfg 重下发。"""
        self.runner._set(1, ST_PASS, "上轮结果")
        self.runner.on_datagram(1, ready_frame())
        self.assertEqual(self.runner.state(1)["state"], ST_PASS)  # 状态不动
        self.assertEqual(self._sent(), [])                        # 一个包都没发
        self.assertTrue(any("只开机" in m for m in self._warns()))

    async def test_reboot_after_fail_no_cfg(self):
        self.runner._set(1, ST_FAIL, "上轮失败")
        self.runner.on_datagram(1, ready_frame())
        self.assertEqual(self._sent(), [])
        self.assertEqual(self.runner.state(1)["state"], ST_FAIL)

    async def test_reboot_while_running_no_cfg(self):
        self.runner._set(1, ST_RUNNING, "")
        self.runner.on_datagram(1, ready_frame())
        self.assertEqual(self._sent(), [])
        self.assertEqual(self.runner.state(1)["state"], ST_RUNNING)

    async def test_aging_req_ignored_in_power_only(self):
        """只开机下 DUT 问 0x12（旧测试余续）不续链：不答老化时长。"""
        self.runner._set(1, ST_RUNNING, "")
        self.runner.on_datagram(1, aging_req_frame())
        self.assertEqual(self._sent(), [])

    async def test_full_run_still_sends_cfg(self):
        """对照：完整运行 armed → READY → 照常 ACK+下发 cfg（门不过度拦截）。"""
        self.mdbg.run_mode = "full_run"
        self.runner.arm(1)
        self.runner.on_datagram(1, ready_frame())
        self.assertEqual(self.runner.state(1)["state"], ST_CFG_SENT)
        self.assertEqual(len(self._sent()), 2)          # ACK(0x10) + cfg(0x15)
        ack_data, cfg_data = self._sent()[0][0], self._sent()[1][0]
        self.assertEqual(ack_data[4], 0x10)
        self.assertEqual(cfg_data[4], 0x15)


if __name__ == "__main__":
    unittest.main()
