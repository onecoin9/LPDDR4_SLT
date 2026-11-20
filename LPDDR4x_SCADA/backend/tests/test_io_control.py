"""IO 控制（无操作/测试板开机/下载模式）——旧上位机逻辑移植测试。

对齐源（LPDDR4x_SLT_Standard）：
  - SettingForm.cs:151-156 下拉选项 → EIOGroup（无操作=INVALID/测试板开机=MCU_PWR/
    下载模式=MCU_KPCOL）
  - CBCProtocol.GenerateIoSecuritySetPackage + GetoutGroupData：12 路按批均分
    （余数给前批）、旧治具线序 group*4+numInGroup+1、按键 startStatus=0+脉宽 ms
  - DutsManager ST_WORKING 链：断电→上电→(按键)→等 0x10；未上线 =
    ExcuteConnTimeout → 0xFD dut_conn_timeout「测试板启动超时」

运行：cd backend && python -m unittest tests.test_io_control -v
"""

import asyncio
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, ".")

from app.commboard import (IO_GROUP_MCU_KPCOL, IO_GROUP_MCU_PWR,   # noqa: E402
                           IO_GROUP_PWR_EN, _batch_lines,
                           build_key_batch_controls)
from app.models import IoControlConfig, MachineConfig               # noqa: E402
from app.protocol import HsgCodec                                   # noqa: E402
from app.sequencer import Sequencer                                 # noqa: E402
from app.ws import Hub                                              # noqa: E402


class TestBatchSplit(unittest.TestCase):
    """旧码 GetoutGroupData 移植：12 路按批均分"""

    def test_batch_of_4(self):
        # 旧算法：12/4=3 无余数 → 每批 3 路
        self.assertEqual(_batch_lines(4, 1), [0, 1, 2])
        self.assertEqual(_batch_lines(4, 4), [9, 10, 11])

    def test_batch_of_5(self):
        # 12/5=2 余 2 → 前两批 3 路，后三批 2 路
        self.assertEqual(_batch_lines(5, 1), [0, 1, 2])
        self.assertEqual(_batch_lines(5, 2), [3, 4, 5])
        self.assertEqual(_batch_lines(5, 3), [6, 7])
        self.assertEqual(_batch_lines(5, 5), [10, 11])

    def test_invalid(self):
        self.assertEqual(_batch_lines(0, 1), [])
        self.assertEqual(_batch_lines(3, 4), [])


class TestKeyBatchControls(unittest.TestCase):
    """「测试板开机」按键包：批延迟累加、线序映射、按键极性"""

    def test_power_key_package(self):
        ctrls = build_key_batch_controls(IO_GROUP_MCU_PWR, batch=4,
                                         start_sec=2, interval_sec=5,
                                         pulse_ms=200)
        self.assertEqual(len(ctrls), 12)             # 全板 12 路
        # 批 1（线 0,1,2，旧线序映射 0→0/1→4/2→8）：start_sec=2，极性 0（按下）
        first = [c for c in ctrls if c.start_sec == 2]
        self.assertEqual(sorted(c.line for c in first), [0, 4, 8])
        self.assertTrue(all(c.group_id == IO_GROUP_MCU_PWR for c in ctrls))
        self.assertTrue(all(c.start_status == 0 for c in ctrls))   # 按键=低有效
        self.assertTrue(all(c.duration_msec == 200 for c in ctrls))
        # 批 2 在 7s、批 4 在 17s
        self.assertEqual(len([c for c in ctrls if c.start_sec == 7]), 3)
        self.assertEqual(len([c for c in ctrls if c.start_sec == 17]), 3)

    def test_power_group_polarity(self):
        """电源组极性=1（高有效），与按键组相反（旧 GenerateIOSetPackage）"""
        ctrls = build_key_batch_controls(IO_GROUP_PWR_EN, batch=12,
                                         start_sec=0, interval_sec=0,
                                         pulse_ms=0xFFFF)
        self.assertTrue(all(c.start_status == 1 for c in ctrls))

    def test_download_group(self):
        ctrls = build_key_batch_controls(IO_GROUP_MCU_KPCOL, batch=12,
                                         start_sec=0, interval_sec=0,
                                         pulse_ms=300)
        self.assertTrue(all(c.group_id == IO_GROUP_MCU_KPCOL for c in ctrls))


class TestIoControlModel(unittest.TestCase):

    def test_defaults_and_validation(self):
        io = IoControlConfig()
        self.assertEqual((io.action, io.batch, io.pulseMs), ("none", 4, 200))
        with self.assertRaises(ValueError):
            IoControlConfig(action="bogus")          # 白名单外拒绝
        m = MachineConfig(ioControl={"action": "power_key", "batch": 6})
        self.assertEqual(m.ioControl.action, "power_key")
        self.assertEqual(m.ioControl.batch, 6)


class TestPowerHookFlow(unittest.TestCase):
    """sequencer 上电前置阶段：上线者开测、未上线者记 dut_conn_timeout"""

    class _Rec:
        def __init__(self): self.rows = []
        def start_run(self, *a):
            class _W:
                def write_log(s, l, m): pass
                def close(s, note=""): pass
            return _W()
        def append_result(self, batch, site, slot, result, item, dur):
            self.rows.append((site, slot, result, item))

    def _mk(self, boot_timeout=0.3):
        hub = Hub()
        sessions = {slot: SimpleNamespace(ready_generation=0, connected=False,
                         subscribe=lambda: asyncio.Queue(), unsubscribe=lambda q: None,
                         send=lambda msg: None) for slot in (1, 2)}
        conns = SimpleNamespace(get=lambda site, slot: sessions.get(slot))
        seq = Sequencer({"dut": {"boot_timeout_sec": boot_timeout,
                                 "test_timeout_sec": 5}},
                        conns, hub, self._Rec())
        return hub, seq

    def test_boot_timeout_and_online_split(self):
        async def main():
            hub, seq = self._mk()
            # 通道 1 在窗口内上线；通道 2 不上线
            async def hook(targets):
                hub.ensure(1, 1)
                hub.ensure(1, 2)
                def ready():
                    seq.conns.get(1, 1).ready_generation += 1
                    hub.update(1, 1, connected=True)
                asyncio.get_running_loop().call_later(0.1, ready)
                return 0.0
            seq.power_hook = hook
            started = await seq.start([(1, 1), (1, 2)], "B")
            await asyncio.sleep(0.1)
            self.assertEqual(started, [(1, 1)])      # 只有上线者开测
            self.assertIn((1, 2, "FAIL", "dut_conn_timeout"),
                          seq.recorder.rows)         # 未上线者 0xFD
            st2 = hub.states[(1, 2)]
            self.assertEqual(st2["state"], "FAIL")
            self.assertEqual(st2["failItem"], "dut_conn_timeout")
            # 收尾清理在测任务
            for t in list(seq.tasks.values()):
                t.cancel()
            await asyncio.sleep(0.05)
        asyncio.run(main())

    def test_hook_error_aborts_start(self):
        async def main():
            hub, seq = self._mk()

            async def bad(targets):
                raise RuntimeError("通讯板无应答")
            seq.power_hook = bad
            started = await seq.start([(1, 1)], "B")
            self.assertEqual(started, [])
            self.assertEqual(len(seq.recorder.rows), 1)  # 电源失败也必须有终态
            self.assertIn("power_control_error", seq.recorder.rows[0][3])
            await seq.close()
        asyncio.run(main())


if __name__ == "__main__":
    unittest.main(verbosity=2)
