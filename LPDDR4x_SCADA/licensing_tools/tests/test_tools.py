import base64
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization

from licensing_tools.client_request import REQUEST_WRAP_KEY_B64, create_request, read_request
from licensing_tools.license_container import KIND_LICENSE, KIND_REQUEST, open_container, seal
from licensing_tools.private_key import create_key, load_key, dpapi
from licensing_tools.issue_license import issue


def _seal_request(inner_text: str) -> bytes:
    return seal(KIND_REQUEST, inner_text.encode("utf-8"), REQUEST_WRAP_KEY_B64)


class Issuer(unittest.TestCase):
    def test_real_dpapi_private_key_roundtrip_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            private = Path(folder) / "issuer.private.key"; public = Path(folder) / "public.json"
            create_key(private, public)
            identity, key = load_key(private)
            self.assertEqual(identity, json.loads(public.read_text())["keyId"])
            self.assertNotIn(base64.b64encode(key.private_bytes_raw()).decode(), private.read_text())
            with self.assertRaises(FileExistsError): create_key(private, public)
            record = json.loads(private.read_text()); record["keyId"] = "slt-tampered"
            private.write_text(json.dumps(record))
            with self.assertRaises(ValueError): load_key(private)

    def test_dpapi_corruption_rejected(self):
        encrypted = dpapi(b"private test data")
        with self.assertRaises(OSError): dpapi(encrypted[:-4] + b"XXXX", True)

    def test_request_armored_and_inner_validation(self):
        raw = create_request("a" * 64)
        self.assertTrue(raw.startswith(b"SLT2."))            # 装甲：客户不可读
        self.assertEqual(read_request(raw)["clientId"], "a" * 64)
        good = json.loads(open_container(KIND_REQUEST, raw, [REQUEST_WRAP_KEY_B64]))
        for mutation in (
            lambda data: {**data, "product": "OTHER"},
            lambda data: {**data, "extra": 1},
            lambda data: {**data, "clientId": "z" * 64},
        ):
            bad = mutation(good)
            with self.assertRaises(ValueError):
                read_request(_seal_request(json.dumps(bad, sort_keys=True, separators=(",", ":"))))

    def test_request_plaintext_v1_still_readable_admin_side(self):
        """管理端兼容读取留档的 v1 明文申请（客户侧只产 v2）。"""
        raw = create_request("b" * 64)
        inner = json.loads(open_container(KIND_REQUEST, raw, [REQUEST_WRAP_KEY_B64]))
        self.assertEqual(read_request(json.dumps(inner).encode())["clientId"], "b" * 64)

    def test_signed_30_days_armored_and_canonical_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            private = folder / "issuer.private.key"; public = folder / "public.json"
            create_key(private, public)
            request = folder / "client_id"; request.write_bytes(create_request("a" * 64))
            output = folder / "license.lic"
            issue(request, private, "中文测试客户", None, output, days=30)
            armored = output.read_text(encoding="utf-8")
            self.assertTrue(armored.startswith("SLT2."))     # 签发产物装甲
            key = load_key(private)[1]
            public_b64 = base64.b64encode(key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
            envelope = json.loads(open_container(KIND_LICENSE, armored.encode("ascii"), [public_b64]))
            sig = envelope.pop("signature")
            key.public_key().verify(base64.b64decode(sig), json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
            payload = envelope["payload"]
            end = dt.datetime.fromisoformat(payload["expiresAt"]); start = dt.datetime.fromisoformat(payload["issuedAt"])
            self.assertEqual(end - start, dt.timedelta(days=30))
            with self.assertRaises(FileExistsError): issue(request, private, "customer", None, output, days=30)
            with self.assertRaises(ValueError): issue(request, private, "customer", None, folder / "other.lic", days=True)


if __name__ == "__main__": unittest.main()

