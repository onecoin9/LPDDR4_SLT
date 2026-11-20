"""SLT2 装甲容器：license.lic / client_id 的 AES-256-GCM 封套（防随手可读）。

契约 = docs/LICENSE_DESIGN.md「SLT2 装甲容器」：
- 文件形态：ASCII 单行 "SLT2." + base64(nonce[12] || ciphertext||tag)，整文件
  <= 32 KiB；客户用文本工具打开只能看到无意义字符串。
- 对称密钥 HKDF-SHA256(Ed25519 公钥原始 32B, salt/info 固定, 32B)——不引入
  新的秘密材料，密钥随签发公钥轮换；AAD 绑定 产品|文件类型，申请与授权
  文件不可互为使用。
- open 依次尝试每个候选公钥（keyId 在密文内，无法先验选择）；全部失败
  fail closed 抛 ValueError("LICENSE_CONTAINER_INVALID")。
- 内层明文与 Ed25519 签名语义完全不变；本层只提高读取成本，不防定向
  逆向（与 .pyd 同一边界，见 LICENSE_GUIDE 能力边界）。
本文件与 licensing_tools/license_container.py 必须逐字节一致（构建断言）。
"""

import base64
import binascii
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

CONTAINER_PREFIX = b"SLT2."
CONTAINER_SALT = b"slt-container-v2"
CONTAINER_NONCE_BYTES = 12
CONTAINER_TAG_BYTES = 16
CONTAINER_MAX_BYTES = 32768  # 与 license/request 文件的 32 KiB 上限一致
PRODUCT = "LPDDR4x_SCADA"
KIND_LICENSE = "license"
KIND_REQUEST = "request"
_KINDS = (KIND_LICENSE, KIND_REQUEST)
_INVALID = "LICENSE_CONTAINER_INVALID"


def _aad(kind: str) -> bytes:
    return f"{PRODUCT}|{kind}".encode("ascii")


def _wrap_key(public_key_b64: str, kind: str) -> bytes:
    raw = base64.b64decode(public_key_b64, validate=True)
    if len(raw) != 32:
        raise ValueError("容器公钥必须是 32 字节 Ed25519 公钥")
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=CONTAINER_SALT,
                info=CONTAINER_PREFIX + b"|" + kind.encode("ascii"))
    return hkdf.derive(raw)


def seal(kind: str, plaintext: bytes, public_key_b64: str) -> bytes:
    """把内层明文封成单行 ASCII 装甲；任何输入非法抛 ValueError。"""
    if kind not in _KINDS:
        raise ValueError("未知容器类型")
    if not isinstance(plaintext, (bytes, bytearray)) or not 0 < len(plaintext) <= CONTAINER_MAX_BYTES:
        raise ValueError("容器载荷长度非法")
    aesgcm = AESGCM(_wrap_key(public_key_b64, kind))
    nonce = os.urandom(CONTAINER_NONCE_BYTES)
    blob = nonce + aesgcm.encrypt(nonce, bytes(plaintext), _aad(kind))
    armored = CONTAINER_PREFIX + base64.b64encode(blob)
    if len(armored) > CONTAINER_MAX_BYTES:
        raise ValueError("装甲后超长")
    return armored


def open_container(kind: str, raw, public_keys_b64) -> bytes:
    """解开装甲返回内层明文；格式/解密失败一律抛 ValueError(_INVALID)。"""
    if kind not in _KINDS:
        raise ValueError("未知容器类型")
    if not isinstance(raw, (bytes, bytearray)) or not raw.startswith(CONTAINER_PREFIX):
        raise ValueError(_INVALID)
    raw = bytes(raw)
    if len(raw) > CONTAINER_MAX_BYTES:
        raise ValueError(_INVALID)
    try:
        blob = base64.b64decode(raw[len(CONTAINER_PREFIX):], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(_INVALID) from exc
    if len(blob) <= CONTAINER_NONCE_BYTES + CONTAINER_TAG_BYTES:
        raise ValueError(_INVALID)
    nonce, body = blob[:CONTAINER_NONCE_BYTES], blob[CONTAINER_NONCE_BYTES:]
    aad = _aad(kind)
    for public_key_b64 in public_keys_b64:
        if not isinstance(public_key_b64, str):
            continue
        try:
            key = _wrap_key(public_key_b64, kind)
        except Exception:  # noqa: BLE001 候选公钥损坏：跳过，保持 fail closed
            continue
        try:
            return AESGCM(key).decrypt(nonce, body, aad)
        except Exception:  # noqa: BLE001 GCM 认证失败=密钥不符或被篡改
            continue
    raise ValueError(_INVALID)
