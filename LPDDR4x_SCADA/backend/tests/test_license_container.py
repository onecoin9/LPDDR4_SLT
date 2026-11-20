"""license_container 单元测试：SLT2 装甲往返、AAD 类型绑定、fail closed。"""

import base64
import sys
import unittest

sys.path.insert(0, ".")
from app.license_container import (  # noqa: E402
    CONTAINER_PREFIX,
    KIND_LICENSE,
    KIND_REQUEST,
    open_container,
    seal,
)
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

PUB = base64.b64encode(
    Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
).decode()
OTHER_PUB = base64.b64encode(
    Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
).decode()


class ContainerTests(unittest.TestCase):
    def test_roundtrip_license_and_request(self):
        for kind in (KIND_LICENSE, KIND_REQUEST):
            armored = seal(kind, b'{"k":1}', PUB)
            self.assertTrue(armored.startswith(CONTAINER_PREFIX))
            self.assertEqual(open_container(kind, armored, [PUB]), b'{"k":1}')

    def test_ciphertext_not_plaintext(self):
        armored = seal(KIND_LICENSE, b'{"secret":"value"}', PUB)
        self.assertNotIn(b"secret", armored)
        self.assertNotIn(b"value", armored)

    def test_nonces_unique(self):
        self.assertNotEqual(seal(KIND_LICENSE, b"x", PUB),
                            seal(KIND_LICENSE, b"x", PUB))

    def test_cross_kind_rejected(self):
        armored = seal(KIND_REQUEST, b'{"k":1}', PUB)
        with self.assertRaises(ValueError):
            open_container(KIND_LICENSE, armored, [PUB])

    def test_wrong_public_key_rejected(self):
        armored = seal(KIND_LICENSE, b'{"k":1}', PUB)
        with self.assertRaises(ValueError):
            open_container(KIND_LICENSE, armored, [OTHER_PUB])
        # 多候选中含正确公钥即可解开
        self.assertEqual(open_container(KIND_LICENSE, armored,
                                        [OTHER_PUB, PUB]), b'{"k":1}')

    def test_tampered_ciphertext_rejected(self):
        armored = bytearray(seal(KIND_LICENSE, b'{"k":1}', PUB))
        armored[-6] ^= 0x01
        with self.assertRaises(ValueError):
            open_container(KIND_LICENSE, bytes(armored), [PUB])

    def test_bad_prefix_and_empty_rejected(self):
        for bad in (b"", b"SLT2", b"SLT3.abcd", b'{"format":"slt-license-v1"}',
                    CONTAINER_PREFIX, CONTAINER_PREFIX + b"!!!not-base64!!!",
                    CONTAINER_PREFIX + base64.b64encode(b"tooshort")):
            with self.assertRaises(ValueError):
                open_container(KIND_LICENSE, bad, [PUB])

    def test_non_ascii_and_oversize_rejected(self):
        with self.assertRaises(ValueError):
            open_container(KIND_LICENSE, "SLT2.\xff\xfe".encode("latin-1"), [PUB])
        with self.assertRaises(ValueError):
            open_container(KIND_LICENSE, b"SLT2." + b"A" * 40000, [PUB])

    def test_seal_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            seal(KIND_LICENSE, b"", PUB)                    # 空载荷
        with self.assertRaises(ValueError):
            seal(KIND_LICENSE, b"x" * 40000, PUB)           # 载荷超长
        with self.assertRaises(ValueError):
            seal("unknown", b"x", PUB)                      # 未知类型
        with self.assertRaises(ValueError):
            seal(KIND_LICENSE, b"x", "not-base64!!")        # 公钥非法
        with self.assertRaises(ValueError):
            seal(KIND_LICENSE, b"x", base64.b64encode(b"short").decode())

    def test_empty_candidates_fail_closed(self):
        armored = seal(KIND_LICENSE, b'{"k":1}', PUB)
        with self.assertRaises(ValueError):
            open_container(KIND_LICENSE, armored, [])


if __name__ == "__main__":
    unittest.main()
