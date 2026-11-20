"""license_state 单元测试：双副本读写、最大时间、损坏修复、写失败、DPAPI 往返。

运行（隔离树 backend）：python -m unittest discover -s tests -p test_license*.py
注册表访问与 LOCALAPPDATA 全部替换/指向临时位置，不触碰真实注册表配置；
DPAPI 往返使用真实 Windows API（仅当前用户上下文，无弹窗）。
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, ".")
from app import license_state as ls  # noqa: E402
from app.license_state import (  # noqa: E402
    ClockStateStore,
    StateStoreError,
    WindowsClockStateStore,
    _encode_record,
)

CLIENT_A = "a" * 64
CLIENT_B = "b" * 64


class _FakeReg:
    """替换 license_state._reg_read_raw/_reg_write_raw 的内存注册表。"""

    def __init__(self):
        self.store = {}
        self.fail_read = False
        self.fail_write = False

    def read(self, path, name):
        if self.fail_read:
            raise StateStoreError("注册表读取失败")
        return self.store.get((path, name))

    def write(self, path, name, data):
        if self.fail_write:
            raise StateStoreError("注册表写入失败")
        self.store[(path, name)] = (bytes(data), ls._REG_BINARY_TYPE)


class MemClockStateStore(ClockStateStore):
    """测试注入的内存实现（接口行为与 Windows 实现一致）。"""

    def __init__(self):
        self.value = None
        self.fail_read = False
        self.writes = []

    def read(self):
        if self.fail_read:
            raise StateStoreError("内存存储读取失败")
        return self.value

    def write(self, timestamp):
        self.value = float(timestamp)
        self.writes.append(self.value)


class WindowsClockStateStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.env_patcher = mock.patch.dict(os.environ, {"LOCALAPPDATA": self._tmp.name})
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)
        self.reg = _FakeReg()
        self.read_patcher = mock.patch.object(ls, "_reg_read_raw", self.reg.read)
        self.write_patcher = mock.patch.object(ls, "_reg_write_raw", self.reg.write)
        self.read_patcher.start()
        self.write_patcher.start()
        self.addCleanup(self.read_patcher.stop)
        self.addCleanup(self.write_patcher.stop)

    def _store(self, client=CLIENT_A):
        return WindowsClockStateStore(client)

    def _read_file_blob(self):
        with open(os.path.join(self._tmp.name, "Acroview", "LPDDR4x_SCADA", CLIENT_A,
                               "clock_state.bin"), "rb") as fh:
            return fh.read()

    def test_fresh_read_returns_none(self):
        self.assertIsNone(self._store().read())

    def test_write_then_read_roundtrip(self):
        store = self._store()
        store.write(12345.5)
        self.assertEqual(store.read(), 12345.5)

    def test_both_copies_hold_same_record(self):
        store = self._store()
        store.write(777.0)
        file_blob = self._read_file_blob()
        reg_blob = self.reg.store[(self._store()._reg_key, ls._REG_VALUE)][0]
        self.assertEqual(file_blob, reg_blob)
        record = json.loads(ls._dpapi_unprotect(file_blob).decode("utf-8"))
        self.assertEqual(record["product"], ls.PRODUCT)
        self.assertEqual(record["clientId"], CLIENT_A)
        self.assertEqual(record["lastSeen"], 777.0)

    def test_read_takes_max_of_copies(self):
        store = self._store()
        store.write(100.0)
        # 手工把注册表副本推进到 200（绕过 write 的双写）
        newer = {"product": ls.PRODUCT, "clientId": CLIENT_A, "lastSeen": 200.0}
        self.reg.store[(self._store()._reg_key, ls._REG_VALUE)] = (
            ls._dpapi_protect(_encode_record(newer)), ls._REG_BINARY_TYPE)
        self.assertEqual(store.read(), 200.0)

    def test_one_valid_copy_repairs_the_other(self):
        store = self._store()
        store.write(300.0)
        with open(os.path.join(self._tmp.name, "Acroview", "LPDDR4x_SCADA", CLIENT_A,
                               "clock_state.bin"), "wb") as fh:
            fh.write(b"garbage-not-dpapi")
        self.assertEqual(store.read(), 300.0)  # 注册表副本有效
        self.assertEqual(self._read_file_blob(),
                         self.reg.store[(self._store()._reg_key, ls._REG_VALUE)][0])

    def test_missing_copy_is_recreated_on_read(self):
        store = self._store()
        store.write(400.0)
        del self.reg.store[(self._store()._reg_key, ls._REG_VALUE)]
        self.assertEqual(store.read(), 400.0)
        self.assertIn((self._store()._reg_key, ls._REG_VALUE), self.reg.store)

    def test_all_corrupt_copies_fail(self):
        store = self._store()
        store.write(500.0)
        with open(os.path.join(self._tmp.name, "Acroview", "LPDDR4x_SCADA", CLIENT_A,
                               "clock_state.bin"), "wb") as fh:
            fh.write(b"garbage")
        self.reg.store[(self._store()._reg_key, ls._REG_VALUE)] = (b"garbage", ls._REG_BINARY_TYPE)
        with self.assertRaises(StateStoreError):
            store.read()

    def test_other_machine_uses_independent_state(self):
        WindowsClockStateStore(CLIENT_B).write(600.0)
        store = self._store(CLIENT_A)
        self.assertIsNone(store.read())
        self.assertEqual(WindowsClockStateStore(CLIENT_B).read(), 600.0)

    def test_write_cannot_lower_high_watermark(self):
        store = self._store()
        store.write(1000)
        store.write(100)
        self.assertEqual(store.read(), 1000)

    def test_wrong_product_record_is_corrupt(self):
        bad = {"product": "OTHER", "clientId": CLIENT_A, "lastSeen": 600.0}
        blob = ls._dpapi_protect(_encode_record(bad))
        self.reg.store[(self._store()._reg_key, ls._REG_VALUE)] = (blob, ls._REG_BINARY_TYPE)
        with self.assertRaises(StateStoreError):
            self._store().read()

    def test_non_finite_last_seen_rejected_on_write(self):
        with self.assertRaises(StateStoreError):
            self._store().write(float("inf"))
        with self.assertRaises(StateStoreError):
            self._store().write(-1.0)

    def test_write_failure_raises(self):
        store = self._store()
        self.reg.fail_write = True
        with self.assertRaises(StateStoreError):
            store.write(123.0)

    def test_read_registry_failure_raises(self):
        store = self._store()
        store.write(123.0)
        self.reg.fail_read = True
        with self.assertRaises(StateStoreError):
            store.read()

    def test_no_leftover_temp_files(self):
        self._store().write(1.0)
        state_dir = os.path.join(self._tmp.name, "Acroview", "LPDDR4x_SCADA", CLIENT_A)
        leftovers = [n for n in os.listdir(state_dir) if n.startswith(".clock_state_")]
        self.assertEqual(leftovers, [])

    def test_invalid_client_id_rejected(self):
        with self.assertRaises(StateStoreError):
            WindowsClockStateStore("")
        with self.assertRaises(StateStoreError):
            WindowsClockStateStore("x" * 129)


@unittest.skipUnless(os.name == "nt", "DPAPI 仅 Windows 可用")
class DpapiTests(unittest.TestCase):
    def test_protect_unprotect_roundtrip(self):
        blob = ls._dpapi_protect(b"hello-dpapi")
        self.assertNotIn(b"hello-dpapi", blob)
        self.assertEqual(ls._dpapi_unprotect(blob), b"hello-dpapi")

    def test_unprotect_garbage_raises(self):
        with self.assertRaises(StateStoreError):
            ls._dpapi_unprotect(b"garbage-garbage-garbage")


if __name__ == "__main__":
    unittest.main()
