"""Shared, non-signing request format for customer and issuer tools."""
import datetime as dt
import json
import re
import uuid

from .license_container import KIND_REQUEST, open_container, seal

PRODUCT = "LPDDR4x_SCADA"
REQUEST_FORMAT = "slt-client-v1"
MAX_REQUEST_BYTES = 32768
REQUEST_FIELDS = {"format", "product", "clientId", "requestId", "requestedAt", "fingerprintVersion"}
# 申请封套公钥（公开材料，= 上位机 TRUSTED_KEYS / 管理端公钥）。多 keyId 并存
# 时以首个信任公钥为准（当前单一 key）；轮换签发密钥后旧工具产出的申请需
# 重新导出。
REQUEST_WRAP_KEY_B64 = "9r+m9/ggPCKg9JYxgh4+PjGZ7Wx4lb2GgZANo18TRRM="


def utc_text(value):
    return value.astimezone(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def validate_request(data):
    if not isinstance(data, dict) or set(data) != REQUEST_FIELDS:
        raise ValueError("Unsupported request fields")
    if data["format"] != REQUEST_FORMAT or data["product"] != PRODUCT:
        raise ValueError("Request belongs to a different product")
    if data["fingerprintVersion"] != "windows-machine-v1":
        raise ValueError("Unsupported machine fingerprint version")
    if not isinstance(data["clientId"], str) or not re.fullmatch(r"[0-9a-f]{64}", data["clientId"]):
        raise ValueError("Invalid client ID")
    for name in ("requestId", "requestedAt"):
        if not isinstance(data[name], str) or len(data[name]) > 80:
            raise ValueError("Invalid request metadata")
    uuid.UUID(data["requestId"])
    stamp = dt.datetime.fromisoformat(data["requestedAt"].replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Request timestamp requires a timezone")
    return data


def read_request(raw):
    """管理端读取申请：SLT2 装甲为主，兼容留档的 v1 明文（仅管理端使用）。"""
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("Request is too large")
    if raw.startswith(b"SLT2."):
        try:
            raw = open_container(KIND_REQUEST, raw, [REQUEST_WRAP_KEY_B64])
        except ValueError as exc:
            raise ValueError("Invalid sealed request") from exc
    return validate_request(json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object))


def peek_client_id(raw):
    """解装甲取 clientId，仅客户工具界面展示用；失败抛 ValueError。"""
    inner = open_container(KIND_REQUEST, raw, [REQUEST_WRAP_KEY_B64])
    return validate_request(json.loads(inner.decode("utf-8-sig"), object_pairs_hook=unique_object))["clientId"]


def create_request(client_id):
    """客户侧导出：SLT2 装甲（内容不可读）；内层仍是 canonical JSON。"""
    data = {"format": REQUEST_FORMAT, "product": PRODUCT, "clientId": client_id,
            "requestId": str(uuid.uuid4()), "requestedAt": utc_text(dt.datetime.now(dt.UTC)),
            "fingerprintVersion": "windows-machine-v1"}
    validate_request(data)
    inner = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return seal(KIND_REQUEST, inner, REQUEST_WRAP_KEY_B64)
