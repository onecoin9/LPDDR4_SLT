"""license_machine 单元测试：指纹规范化、占位策略、显式失败、无原始硬件 ID 泄漏。

运行（隔离树 backend）：python -m unittest discover -s tests -p test_license*.py
系统接口（注册表/PowerShell）全部 mock，不运行真实采集。
"""

import hashlib
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, ".")
from app import license_machine as lm  # noqa: E402
from app.license_machine import MachineFingerprintError, machine_fingerprint  # noqa: E402

_GUID = "12345678-1234-5678-9abc-def012345678"
_GUID_BRACED = "{12345678-1234-5678-9ABC-DEF012345678}"
_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_UUID_UPPER = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_ZERO_UUID = "00000000-0000-0000-0000-000000000000"
_FLAT_ZERO = "00000000000000000000000000000000"
_ALLF_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"
_FLAT_ALLF = "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"


def _expected_fp(guid, uuid_text):
    return hashlib.sha256(f"{guid}\n{uuid_text}".encode("utf-8")).hexdigest()


class MachineFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.guid_patcher = mock.patch.object(lm, "_read_machine_guid", return_value=_GUID)
        self.uuid_patcher = mock.patch.object(lm, "_read_smbios_uuid", return_value=_UUID)
        self.guid_patcher.start()
        self.uuid_patcher.start()
        self.addCleanup(self.guid_patcher.stop)
        self.addCleanup(self.uuid_patcher.stop)

    def test_fingerprint_is_stable_lowercase_sha256(self):
        fp1 = machine_fingerprint()
        fp2 = machine_fingerprint()
        self.assertEqual(fp1, fp2)
        self.assertIsNotNone(re.fullmatch(r"[0-9a-f]{64}", fp1))
        self.assertEqual(fp1, _expected_fp(_GUID, _UUID))

    def test_normalization_braces_and_case(self):
        with mock.patch.object(lm, "_read_machine_guid", return_value=_GUID_BRACED), \
                mock.patch.object(lm, "_read_smbios_uuid", return_value=_UUID_UPPER):
            self.assertEqual(machine_fingerprint(), _expected_fp(_GUID, _UUID))

    def test_all_zero_uuid_uses_fixed_placeholder(self):
        with mock.patch.object(lm, "_read_smbios_uuid", return_value=_ZERO_UUID):
            fp_zero = machine_fingerprint()
        self.assertNotEqual(fp_zero, _expected_fp(_GUID, _UUID))
        self.assertEqual(fp_zero, _expected_fp(_GUID, lm.PLACEHOLDER_UUID))

    def test_flat_all_zero_matches_dashed_zero(self):
        with mock.patch.object(lm, "_read_smbios_uuid", return_value=_FLAT_ZERO):
            a = machine_fingerprint()
        with mock.patch.object(lm, "_read_smbios_uuid", return_value=_ZERO_UUID):
            b = machine_fingerprint()
        self.assertEqual(a, b)

    def test_all_f_uuid_uses_placeholder(self):
        with mock.patch.object(lm, "_read_smbios_uuid", return_value=_ALLF_UUID):
            self.assertEqual(machine_fingerprint(),
                             _expected_fp(_GUID, lm.PLACEHOLDER_UUID))
        with mock.patch.object(lm, "_read_smbios_uuid", return_value=_FLAT_ALLF):
            self.assertEqual(machine_fingerprint(),
                             _expected_fp(_GUID, lm.PLACEHOLDER_UUID))

    def test_invalid_uuid_uses_placeholder(self):
        with mock.patch.object(lm, "_read_smbios_uuid", return_value="not-a-uuid"):
            self.assertEqual(machine_fingerprint(),
                             _expected_fp(_GUID, lm.PLACEHOLDER_UUID))

    def test_flat_uuid_normalized_to_dashed(self):
        flat = _UUID.replace("-", "")
        with mock.patch.object(lm, "_read_smbios_uuid", return_value=flat):
            self.assertEqual(machine_fingerprint(), _expected_fp(_GUID, _UUID))

    def test_missing_machine_guid_fails_explicitly(self):
        with mock.patch.object(lm, "_read_machine_guid",
                               side_effect=MachineFingerprintError("MachineGuid 缺失")):
            with self.assertRaises(MachineFingerprintError):
                machine_fingerprint()

    def test_empty_machine_guid_fails_explicitly(self):
        with mock.patch.object(lm, "_read_machine_guid", return_value="  "):
            with self.assertRaises(MachineFingerprintError):
                machine_fingerprint()

    def test_malformed_machine_guid_fails_explicitly(self):
        with mock.patch.object(lm, "_read_machine_guid", return_value="zzzz"):
            with self.assertRaises(MachineFingerprintError):
                machine_fingerprint()

    def test_cim_exception_fails_explicitly(self):
        with mock.patch.object(lm, "_read_smbios_uuid",
                               side_effect=MachineFingerprintError("CIM 执行异常")):
            with self.assertRaises(MachineFingerprintError):
                machine_fingerprint()

    def test_no_raw_hardware_ids_in_fingerprint(self):
        fp = machine_fingerprint()
        self.assertNotIn(_GUID.replace("-", ""), fp)
        self.assertNotIn(_UUID.replace("-", ""), fp)
        self.assertNotIn("12345678", fp)
        self.assertNotIn("aaaaaaaa", fp)

    def test_subprocess_fixed_command_hidden_and_timeout(self):
        self.uuid_patcher.stop()  # 恢复真实 _read_smbios_uuid 以观察 subprocess
        proc = mock.Mock(returncode=0, stdout=_UUID.encode("utf-8"))
        with mock.patch.object(lm.subprocess, "run", return_value=proc) as run:
            result = lm._read_smbios_uuid()
        self.assertEqual(result, _UUID)
        args, kwargs = run.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "powershell.exe")
        self.assertIn("-NoProfile", cmd)
        self.assertIn("-NonInteractive", cmd)
        self.assertIn("Get-CimInstance", cmd[cmd.index("-Command") + 1])
        self.assertIn("Win32_ComputerSystemProduct", cmd[cmd.index("-Command") + 1])
        self.assertEqual(kwargs["timeout"], lm._CIM_TIMEOUT_SECONDS)
        if sys.platform == "win32":
            self.assertTrue(kwargs["creationflags"] & lm._CREATE_NO_WINDOW)

    def test_powershell_nonzero_exit_fails(self):
        self.uuid_patcher.stop()
        proc = mock.Mock(returncode=1, stdout=b"")
        with mock.patch.object(lm.subprocess, "run", return_value=proc):
            with self.assertRaises(MachineFingerprintError):
                lm._read_smbios_uuid()

    def test_powershell_timeout_fails(self):
        self.uuid_patcher.stop()
        import subprocess as sp
        with mock.patch.object(lm.subprocess, "run",
                               side_effect=sp.TimeoutExpired("powershell", 15)):
            with self.assertRaises(MachineFingerprintError):
                lm._read_smbios_uuid()


if __name__ == "__main__":
    unittest.main()
