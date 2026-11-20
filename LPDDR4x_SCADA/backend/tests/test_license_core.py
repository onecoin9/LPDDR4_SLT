"""license_core 单元测试：固定接口、严格格式校验、验签、时间/回拨、导入原子性。

运行（隔离树 backend）：python -m unittest discover -s tests -p test_license*.py
临时 Ed25519 测试密钥经构造参数注入，不依赖管理端密钥、不读外部公钥文件。
"""

import base64
import json
import os
import re
import sys
import tempfile
import threading
import unittest
import uuid
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, ".")
from app.license_container import (  # noqa: E402
    KIND_LICENSE,
    KIND_REQUEST,
    open_container,
    seal,
)
from app.license_core import (  # noqa: E402
    CLIENT_FORMAT,
    LICENSE_FORMAT,
    PRODUCT_NAME,
    LicenseDenied,
    LicenseError,
    LicenseService,
    _canonical_json,
)
from app.license_machine import MachineFingerprintError  # noqa: E402
from app.license_state import ClockStateStore, StateStoreError  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

FP = "ab" * 32            # 本机指纹（64 位十六进制）
FP_OTHER = "cd" * 32      # 其他机器指纹
T0 = 1_760_000_000        # 固定墙钟基准（epoch 秒）
STATUS_KEYS = {"state", "allowedToStart", "clientId", "expiresAt",
               "daysRemaining", "customer", "licenseId", "message"}


def _keypair():
    priv = Ed25519PrivateKey.generate()
    raw = priv.public_key().public_bytes(serialization.Encoding.Raw,
                                         serialization.PublicFormat.Raw)
    return priv, base64.b64encode(raw).decode()


def _z(offset=0):
    return datetime.fromtimestamp(T0 + offset, tz=timezone.utc) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


class _MemStore(ClockStateStore):
    """测试注入的内存 ClockStateStore。"""

    def __init__(self):
        self.value = None
        self.fail_read = False
        self.fail_write = False
        self.writes = []

    def read(self):
        if self.fail_read:
            raise StateStoreError("内存存储读取失败")
        return self.value

    def write(self, timestamp):
        if self.fail_write:
            raise StateStoreError("内存存储写入失败")
        self.value = float(timestamp)
        self.writes.append(self.value)


class ServiceCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.priv, self.pub_b64 = _keypair()
        self.trusted = {"k1": self.pub_b64}
        self.mem = _MemStore()
        self.wall = [float(T0)]
        self.mono = [0.0]
        self.machine = mock.Mock(return_value=FP)
        self.svc = LicenseService(
            self.tmp.name, machine_provider=self.machine, state_store=self.mem,
            trusted_keys=self.trusted, now=lambda: self.wall[0],
            monotonic=lambda: self.mono[0])

    def payload(self, **over):
        data = {
            "version": 1, "product": PRODUCT_NAME,
            "licenseId": "11111111-2222-3333-4444-555555555555",
            "clientId": FP,
            "issuedAt": _z(-10), "notBefore": _z(-5), "expiresAt": _z(100000),
            "customer": "测试客户",
            "requestId": "66666666-7777-8888-9999-000000000000",
        }
        data.update(over)
        return data

    def plain(self, priv=None, key_id="k1", **over):
        """旧版明文 envelope（v1）：仅用于验证 v2-only 拒绝路径。"""
        env = {"format": LICENSE_FORMAT, "keyId": key_id,
               "payload": self.payload(**over)}
        sig = (priv or self.priv).sign(_canonical_json(env))
        env["signature"] = base64.b64encode(sig).decode()
        return json.dumps(env, ensure_ascii=False, sort_keys=True).encode("utf-8")

    def armored(self, raw: bytes) -> bytes:
        return seal(KIND_LICENSE, raw, self.pub_b64)

    def signed(self, priv=None, key_id="k1", **over):
        env = {"format": LICENSE_FORMAT, "keyId": key_id,
               "payload": self.payload(**over)}
        sig = (priv or self.priv).sign(_canonical_json(env))
        env["signature"] = base64.b64encode(sig).decode()
        inner = json.dumps(env, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
        return self.armored(inner)

    def install(self, data=None, **over):
        data = data if data is not None else self.signed(**over)
        with open(os.path.join(self.tmp.name, "license.lic"), "wb") as fh:
            fh.write(data)
        return data

    def file_bytes(self):
        with open(os.path.join(self.tmp.name, "license.lic"), "rb") as fh:
            return fh.read()


class StatusTests(ServiceCase):
    def test_missing_license(self):
        st = self.svc.status()
        self.assertEqual(st["state"], "missing")
        self.assertFalse(st["allowedToStart"])
        self.assertEqual(st["clientId"], FP)  # 缺失时也暴露 clientId 供申请

    def test_status_keys_exact(self):
        self.install()
        st = self.svc.status()
        self.assertEqual(set(st), STATUS_KEYS)

    def test_valid_license(self):
        self.install()
        st = self.svc.status()
        self.assertEqual(st["state"], "valid")
        self.assertTrue(st["allowedToStart"])
        self.assertEqual(st["clientId"], FP)
        self.assertEqual(st["expiresAt"], _z(100000))
        self.assertEqual(st["customer"], "测试客户")
        self.assertEqual(st["licenseId"], "11111111-2222-3333-4444-555555555555")
        self.assertEqual(st["daysRemaining"], 2)  # ceil(100000/86400)

    def test_expired(self):
        self.install(expiresAt=_z(-1), issuedAt=_z(-10), notBefore=_z(-5))
        st = self.svc.status()
        self.assertEqual(st["state"], "expired")
        self.assertFalse(st["allowedToStart"])

    def test_not_yet_valid(self):
        self.install(notBefore=_z(100), expiresAt=_z(200000))
        st = self.svc.status()
        self.assertEqual(st["state"], "not_yet_valid")

    def test_boundary_not_before_inclusive(self):
        self.install(notBefore=_z(0), expiresAt=_z(100000), issuedAt=_z(0))
        self.assertEqual(self.svc.status()["state"], "valid")

    def test_boundary_expires_exclusive(self):
        self.install(notBefore=_z(-1), expiresAt=_z(0), issuedAt=_z(-1))
        self.assertEqual(self.svc.status()["state"], "expired")

    def test_machine_mismatch(self):
        self.install(clientId=FP_OTHER)
        st = self.svc.status()
        self.assertEqual(st["state"], "machine_mismatch")
        self.assertFalse(st["allowedToStart"])

    def test_machine_unavailable(self):
        self.machine.side_effect = MachineFingerprintError("CIM 失败")
        self.install()
        st = self.svc.status()
        self.assertEqual(st["state"], "machine_unavailable")
        self.assertIsNone(st["clientId"])

    def test_storage_error_on_read_failure(self):
        self.install()
        self.mem.fail_read = True
        st = self.svc.status()
        self.assertEqual(st["state"], "storage_error")
        self.assertFalse(st["allowedToStart"])

    def test_status_write_failure_is_storage_error(self):
        self.install()
        self.mem.fail_write = True
        st = self.svc.status()
        self.assertEqual(st["state"], "storage_error")

    def test_status_never_raises_when_everything_broken(self):
        self.mem.fail_read = True
        self.machine.side_effect = MachineFingerprintError("CIM 失败")
        st = self.svc.status()
        self.assertEqual(st["state"], "machine_unavailable")

    def test_fingerprint_cached_across_status(self):
        self.install()
        self.svc.status()
        self.svc.status()
        self.assertEqual(self.machine.call_count, 1)

    def test_now_accepts_aware_datetime(self):
        self.install()
        svc = LicenseService(
            self.tmp.name, machine_provider=self.machine, state_store=self.mem,
            trusted_keys=self.trusted,
            now=lambda: datetime.fromtimestamp(self.wall[0], tz=timezone.utc),
            monotonic=lambda: self.mono[0])
        self.assertEqual(svc.status()["state"], "valid")

    def test_now_rejects_naive_datetime(self):
        self.install()
        with self.assertRaises(ValueError):
            LicenseService(self.tmp.name, now=lambda: datetime.fromtimestamp(self.wall[0]))


class RequireValidTests(ServiceCase):
    def test_seen_expiry_survives_restart_and_small_clock_rollback(self):
        self.install(expiresAt=_z(10))
        self.svc.require_valid()
        self.wall[0] = T0 + 20
        self.assertEqual(self.svc.status()["state"], "expired")
        self.assertGreaterEqual(self.mem.value, T0 + 20)
        restarted = LicenseService(self.tmp.name, machine_provider=self.machine,
                                   state_store=self.mem, trusted_keys=self.trusted,
                                   now=lambda: T0 + 5, monotonic=lambda: 0)
        self.assertEqual(restarted.status()["state"], "expired")

    def test_require_valid_ok_persists_time(self):
        self.install()
        self.svc.require_valid()
        self.assertEqual(self.mem.value, float(T0))

    def test_require_valid_missing_raises_and_writes_nothing(self):
        with self.assertRaises(LicenseDenied) as ctx:
            self.svc.require_valid()
        self.assertEqual(ctx.exception.status["state"], "missing")
        self.assertEqual(self.mem.writes, [])
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "license.lic")))

    def test_require_valid_expired_raises(self):
        self.install(expiresAt=_z(-1))
        with self.assertRaises(LicenseDenied) as ctx:
            self.svc.require_valid()
        self.assertEqual(ctx.exception.status["state"], "expired")

    def test_require_valid_denial_writes_nothing(self):
        self.install(clientId=FP_OTHER)
        with self.assertRaises(LicenseDenied):
            self.svc.require_valid()
        self.assertEqual(self.mem.writes, [])

    def test_require_valid_storage_error_raises(self):
        self.install()
        self.mem.fail_read = True
        with self.assertRaises(LicenseDenied) as ctx:
            self.svc.require_valid()
        self.assertEqual(ctx.exception.status["state"], "storage_error")

    def test_require_valid_forced_persist_failure_denies(self):
        self.install()
        self.mem.fail_write = True
        with self.assertRaises(LicenseDenied) as ctx:
            self.svc.require_valid()
        self.assertEqual(ctx.exception.status["state"], "storage_error")


class ClockTests(ServiceCase):
    def test_clock_rollback_beyond_tolerance(self):
        self.install()
        self.mem.value = float(T0 + 1000)  # 持久化未来时间
        self.wall[0] = float(T0)           # 墙钟回拨
        st = self.svc.status()
        self.assertEqual(st["state"], "clock_rollback")
        with self.assertRaises(LicenseDenied):
            self.svc.require_valid()

    def test_clock_rollback_within_tolerance_uses_max(self):
        self.install()
        self.mem.value = float(T0 + 200)   # 回拨 200s < 300s 容忍
        self.wall[0] = float(T0)
        self.assertEqual(self.svc.status()["state"], "valid")

    def test_expiry_judged_by_max_time(self):
        self.install(expiresAt=_z(100))
        self.mem.value = float(T0 + 200)    # 容忍范围内，有效期按最大值判定
        self.assertEqual(self.svc.status()["state"], "expired")

    def test_monotonic_floor_advances_time(self):
        self.install(expiresAt=_z(100))
        self.mono[0] = 150.0               # 墙钟暂停，单调时钟推进（容忍内）
        self.assertEqual(self.svc.status()["state"], "expired")

    def test_monotonic_floor_beyond_tolerance_is_rollback(self):
        self.install()
        self.mono[0] = 400.0               # 墙钟冻结而单调推进 >300s = 回拨特征
        self.assertEqual(self.svc.status()["state"], "clock_rollback")

    def test_monotonic_floor_survives_wall_backward_within_run(self):
        self.install()
        self.mono[0] = 100.0
        self.wall[0] = float(T0 - 50)      # 单次小幅回拨
        self.assertEqual(self.svc.status()["state"], "valid")


class FormatTests(ServiceCase):
    def _expect_invalid(self, data):
        self.install(data=data)
        self.assertEqual(self.svc.status()["state"], "invalid")

    def test_tampered_payload(self):
        env = {"format": LICENSE_FORMAT, "keyId": "k1", "payload": self.payload()}
        sig = self.priv.sign(_canonical_json(env))
        env["payload"] = self.payload(customer="篡改")  # 签名后改载荷
        env["signature"] = base64.b64encode(sig).decode()
        self._expect_invalid(self.armored(_canonical_json(env)))

    def test_extra_envelope_field(self):
        env = json.loads(self.plain())
        env["extra"] = 1
        sig = self.priv.sign(_canonical_json(
            {"format": env["format"], "keyId": env["keyId"], "payload": env["payload"]}))
        env["signature"] = base64.b64encode(sig).decode()
        self._expect_invalid(self.armored(json.dumps(env).encode()))

    def test_duplicate_envelope_key(self):
        raw = ('{"format":"slt-license-v1","format":"slt-license-v1"}')
        self._expect_invalid(self.armored(raw.encode()))

    def test_plaintext_v1_rejected(self):
        """v2-only：旧版明文 envelope（签名合法）也必须拒绝。"""
        self._expect_invalid(self.plain())

    def test_armored_char_flip_rejected(self):
        good = self.signed()
        text = good.decode("ascii")
        flip = "A" if text[30] != "A" else "B"
        self._expect_invalid((text[:30] + flip + text[31:]).encode("ascii"))

    def test_armored_wrong_kind_rejected(self):
        inner = self.plain()  # license 内容封装成 request 类型
        wrong = seal(KIND_REQUEST, inner, self.pub_b64)
        self._expect_invalid(wrong)

    def test_unknown_format(self):
        env = json.loads(self.plain())
        env["format"] = "slt-license-v2"
        sig = self.priv.sign(_canonical_json(
            {"format": env["format"], "keyId": env["keyId"], "payload": env["payload"]}))
        env["signature"] = base64.b64encode(sig).decode()
        self._expect_invalid(self.armored(json.dumps(env).encode()))

    def test_unknown_key_id(self):
        self._expect_invalid(self.signed(key_id="k-unknown"))

    def test_wrong_signing_key(self):
        other_priv, _ = _keypair()
        self._expect_invalid(self.signed(priv=other_priv))

    def test_empty_trusted_keys_fail_closed(self):
        svc = LicenseService(
            self.tmp.name, machine_provider=self.machine, state_store=self.mem,
            trusted_keys={}, now=lambda: self.wall[0],
            monotonic=lambda: self.mono[0])
        self.install()
        self.assertEqual(svc.status()["state"], "invalid")

    def test_malformed_trusted_key_entry(self):
        svc = LicenseService(
            self.tmp.name, machine_provider=self.machine, state_store=self.mem,
            trusted_keys={"k1": "not-valid-base64!!"},
            now=lambda: self.wall[0], monotonic=lambda: self.mono[0])
        self.install()
        self.assertEqual(svc.status()["state"], "invalid")

    def test_short_signature(self):
        env = json.loads(self.plain())
        env["signature"] = base64.b64encode(b"x" * 32).decode()
        self._expect_invalid(self.armored(json.dumps(env).encode()))

    def test_bad_base64_signature(self):
        env = json.loads(self.plain())
        env["signature"] = "!!!not-base64!!!"
        self._expect_invalid(self.armored(json.dumps(env).encode()))

    def test_float_time_rejected(self):
        self._expect_invalid(self.signed(expiresAt=1.0))

    def test_naive_time_rejected(self):
        self._expect_invalid(self.signed(expiresAt="2030-01-01T00:00:00"))

    def test_non_utc_offset_rejected(self):
        self._expect_invalid(self.signed(expiresAt="2030-01-01T08:00:00+08:00"))

    def test_bool_version_rejected(self):
        self._expect_invalid(self.signed(version=True))

    def test_string_version_rejected(self):
        self._expect_invalid(self.signed(version="1"))

    def test_version_two_rejected(self):
        self._expect_invalid(self.signed(version=2))

    def test_wrong_product(self):
        self._expect_invalid(self.signed(product="OTHER"))

    def test_bad_client_id(self):
        self._expect_invalid(self.signed(clientId="ZZ" * 32))
        self._expect_invalid(self.signed(clientId="ab" * 31))

    def test_customer_too_long(self):
        self._expect_invalid(self.signed(customer="长" * 129))
        self.install(customer="长" * 128)
        self.assertEqual(self.svc.status()["state"], "valid")

    def test_missing_payload_field(self):
        payload = self.payload()
        del payload["requestId"]
        env = {"format": LICENSE_FORMAT, "keyId": "k1", "payload": payload}
        sig = self.priv.sign(_canonical_json(env))
        env["signature"] = base64.b64encode(sig).decode()
        self._expect_invalid(self.armored(json.dumps(env).encode()))

    def test_extra_payload_field(self):
        payload = self.payload()
        payload["limits"] = {}
        env = {"format": LICENSE_FORMAT, "keyId": "k1", "payload": payload}
        sig = self.priv.sign(_canonical_json(env))
        env["signature"] = base64.b64encode(sig).decode()
        self._expect_invalid(self.armored(json.dumps(env).encode()))

    def test_bad_license_id(self):
        self._expect_invalid(self.signed(licenseId="not-a-uuid"))

    def test_not_before_after_expires(self):
        self._expect_invalid(self.signed(notBefore=_z(500), expiresAt=_z(400)))

    def test_not_before_equals_expires(self):
        self._expect_invalid(self.signed(notBefore=_z(400), expiresAt=_z(400)))

    def test_issued_after_expires(self):
        self._expect_invalid(self.signed(issuedAt=_z(500), expiresAt=_z(400)))

    def test_oversize_license(self):
        self._expect_invalid(b" " * 40000)

    def test_non_utf8_license(self):
        self._expect_invalid(b"\xff\xfe\x00\x01")

    def test_nan_constant_rejected(self):
        self._expect_invalid(self.signed(expiresAt=float("nan")))


class ImportTests(ServiceCase):
    def test_import_success_replaces_old(self):
        first = self.signed()
        st = self.svc.import_license(first)
        self.assertEqual(st["state"], "valid")
        second = self.signed(licenseId="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        st = self.svc.import_license(second)
        self.assertEqual(st["state"], "valid")
        self.assertEqual(st["licenseId"], "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        self.assertEqual(self.file_bytes(), second)

    def test_import_failure_keeps_old_license(self):
        old = self.install()
        st = self.svc.import_license(b"garbage")
        self.assertEqual(st["state"], "invalid")
        self.assertEqual(self.svc.status()["state"], "valid")
        self.assertEqual(self.file_bytes(), old)

    def test_import_tampered_keeps_old(self):
        old = self.install()
        good = self.signed().decode("ascii")
        flip = "A" if good[30] != "A" else "B"
        st = self.svc.import_license((good[:30] + flip + good[31:]).encode("ascii"))
        self.assertEqual(st["state"], "invalid")
        self.assertEqual(self.file_bytes(), old)

    def test_import_machine_mismatch_keeps_old(self):
        old = self.install()
        st = self.svc.import_license(self.signed(clientId=FP_OTHER))
        self.assertEqual(st["state"], "machine_mismatch")
        self.assertEqual(self.file_bytes(), old)

    def test_import_machine_unavailable_keeps_old(self):
        old = self.install()
        self.machine.side_effect = MachineFingerprintError("CIM 失败")
        st = self.svc.import_license(self.signed())
        self.assertEqual(st["state"], "machine_unavailable")
        self.assertEqual(self.file_bytes(), old)

    def test_import_genuine_expired_license_keeps_old(self):
        old = self.install()
        expired = self.signed(expiresAt=_z(-1))
        st = self.svc.import_license(expired)
        self.assertEqual(st["state"], "expired")
        self.assertEqual(self.file_bytes(), old)

    def test_import_oversize_rejected(self):
        st = self.svc.import_license(b"x" * 40000)
        self.assertEqual(st["state"], "invalid")
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "license.lic")))

    def test_import_forces_state_persist(self):
        before = len(self.mem.writes)
        self.svc.import_license(self.signed())
        self.assertGreater(len(self.mem.writes), before)

    def test_import_denied_during_clock_rollback(self):
        self.mem.value = float(T0 + 1000)
        st = self.svc.import_license(self.signed())
        self.assertEqual(st["state"], "clock_rollback")
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "license.lic")))

    def test_import_future_and_storage_failure_keep_old(self):
        old = self.install()
        self.assertEqual(self.svc.import_license(self.signed(notBefore=_z(500)))["state"], "not_yet_valid")
        self.assertEqual(self.file_bytes(), old)
        self.mem.fail_write = True
        self.assertEqual(self.svc.import_license(self.signed())["state"], "storage_error")
        self.assertEqual(self.file_bytes(), old)

    def test_default_store_is_windows_persistent_not_disabled(self):
        with mock.patch("app.license_core.WindowsClockStateStore", return_value=self.mem) as factory:
            svc = LicenseService(self.tmp.name, machine_provider=lambda: FP,
                                 trusted_keys=self.trusted, now=lambda: T0,
                                 monotonic=lambda: 0)
            self.assertEqual(svc.import_license(self.signed())["state"], "valid")
            factory.assert_called_once_with(FP)
            self.assertTrue(self.mem.writes)

    def test_import_accepts_str(self):
        st = self.svc.import_license(self.signed().decode("utf-8"))
        self.assertEqual(st["state"], "valid")

    def test_import_unicode_customer(self):
        st = self.svc.import_license(self.signed(customer="中文字符™"))
        self.assertEqual(st["state"], "valid")

    def test_concurrent_imports_leave_consistent_file(self):
        licenses = []
        for i in range(6):
            payload = self.payload(
                licenseId=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"lic{i}")))
            env = {"format": LICENSE_FORMAT, "keyId": "k1", "payload": payload}
            sig = self.priv.sign(_canonical_json(env))
            env["signature"] = base64.b64encode(sig).decode()
            licenses.append(self.armored(json.dumps(
                env, ensure_ascii=False, sort_keys=True).encode()))
        barrier = threading.Barrier(6)

        def worker(blob):
            barrier.wait(timeout=10)
            self.svc.import_license(blob)

        threads = [threading.Thread(target=worker, args=(b,)) for b in licenses]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        final = self.file_bytes()
        self.assertIn(final, licenses)  # 原子替换：内容必为某一完整许可
        st = self.svc.status()
        self.assertEqual(st["state"], "valid")


class ExportRequestTests(ServiceCase):
    def test_export_request_armored_and_inner_fields(self):
        blob = self.svc.export_request()
        self.assertTrue(blob.startswith(b"SLT2."))          # 客户不可读装甲
        inner = open_container(KIND_REQUEST, blob, [self.pub_b64])
        req = json.loads(inner.decode("utf-8"))
        self.assertEqual(set(req), {"format", "product", "clientId", "requestId",
                                    "requestedAt", "fingerprintVersion"})
        self.assertEqual(req["format"], CLIENT_FORMAT)
        self.assertEqual(req["product"], PRODUCT_NAME)
        self.assertEqual(req["clientId"], FP)
        self.assertEqual(req["fingerprintVersion"], "windows-machine-v1")
        uuid.UUID(req["requestId"])  # 不抛异常即合法
        self.assertIsNotNone(re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", req["requestedAt"]))

    def test_export_request_inner_is_canonical_utf8(self):
        blob = self.svc.export_request()
        inner = open_container(KIND_REQUEST, blob, [self.pub_b64])
        req = json.loads(inner.decode("utf-8"))
        self.assertEqual(inner, _canonical_json(req))

    def test_export_request_rejects_plaintext_reader(self):
        """申请文件本身不可再作为明文 JSON 使用（防随手可读的直接证据）。"""
        blob = self.svc.export_request()
        with self.assertRaises(ValueError):
            json.loads(blob.decode("utf-8"))

    def test_export_request_machine_error_raises(self):
        self.machine.side_effect = MachineFingerprintError("CIM 失败")
        with self.assertRaises(LicenseError):
            self.svc.export_request()


if __name__ == "__main__":
    unittest.main()
