"""授权核心：LicenseService（机器绑定 + 有效期 + 抗回拨判定）。

契约 = docs/LICENSE_DESIGN.md「固定接口与格式」：
- LicenseService(license_dir, *, machine_provider=None, state_store=None,
  trusted_keys=None, now=None, monotonic=None)；许可固定 license_dir/license.lic。
- status() → {state, allowedToStart, clientId, expiresAt, daysRemaining,
  customer, licenseId, message}；state ∈ valid/missing/expired/not_yet_valid/
  invalid/machine_mismatch/clock_rollback/storage_error/machine_unavailable。
- require_valid() 未授权抛 LicenseDenied(status)，不修改测试状态/硬件；
  export_request() → UTF-8 bytes（下载文件名 client_id）；import_license(bytes)
  → status，验签通过后原子替换，失败保持旧许可。
- 机器识别异常、验签库异常、存储失败一律禁止起测；接口不抛出、不中断
  应用与授权界面（状态反映异常）。
时间判定：墙钟、进程单调时钟、持久化已观察最大值三者取高；墙钟落后最大值
超过 300s → clock_rollback；否则用最大值判断有效期（notBefore<=now<
expiresAt）。起测成功与导入强制落盘；status() 低频落盘。日期判定只用注入
时钟（aware datetime 或 epoch 秒），不隐式采用本地时区。
能力边界（合同明示）：签名许可 + 本地最高时间不能提供绝对离线抗快照/管理
员删除全部状态保障；不宣传"防破解"。
"""

import base64
import binascii
import hmac
import json
import logging
import math
import os
import re
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.license_container import KIND_LICENSE, KIND_REQUEST, open_container, seal
from app.license_keys import TRUSTED_KEYS
from app.license_machine import machine_fingerprint
from app.license_state import StateStoreError, WindowsClockStateStore

_LOG = logging.getLogger(__name__)

LICENSE_FORMAT = "slt-license-v1"
CLIENT_FORMAT = "slt-client-v1"
PRODUCT_NAME = "LPDDR4x_SCADA"
REQUEST_FILENAME = "client_id"
LICENSE_FILENAME = "license.lic"
MAX_LICENSE_BYTES = 32768  # 与 POST /api/license/import 的 32KiB 限制一致
MAX_CUSTOMER_LEN = 128
FINGERPRINT_VERSION = "windows-machine-v1"
ROLLBACK_TOLERANCE_SECONDS = 300.0
DEFAULT_PERSIST_INTERVAL = 3600.0

STATE_VALID = "valid"
STATE_MISSING = "missing"
STATE_EXPIRED = "expired"
STATE_NOT_YET_VALID = "not_yet_valid"
STATE_INVALID = "invalid"
STATE_MACHINE_MISMATCH = "machine_mismatch"
STATE_CLOCK_ROLLBACK = "clock_rollback"
STATE_STORAGE_ERROR = "storage_error"
STATE_MACHINE_UNAVAILABLE = "machine_unavailable"

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

_MESSAGES = {
    STATE_VALID: "授权有效",
    STATE_MISSING: "未导入授权文件，请导出 client_id 并申请授权",
    STATE_INVALID: "授权文件无效（签名、格式或内容校验失败）",
    STATE_EXPIRED: "授权已到期，禁止新测试",
    STATE_NOT_YET_VALID: "授权尚未生效",
    STATE_MACHINE_MISMATCH: "授权文件与本机指纹不匹配",
    STATE_CLOCK_ROLLBACK: "检测到系统时间异常回拨，禁止起测",
    STATE_STORAGE_ERROR: "授权时间状态存储异常，禁止起测",
    STATE_MACHINE_UNAVAILABLE: "无法读取本机机器标识，禁止起测",
}


class LicenseError(Exception):
    """授权核心异常基类。"""


class LicenseDenied(LicenseError):
    """未授权起测：携带 status() 同款字典（含 state/message）。"""

    def __init__(self, status):
        self.status = status
        super().__init__(status.get("message", "license denied"))


def _canonical_json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _utc_z(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc_time(value) -> float:
    """仅接受带时区且偏移为 0（UTC）的时间字符串，返回 epoch 秒。"""
    if not isinstance(value, str):
        raise ValueError("时间必须是字符串")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("时间格式非法") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("时间必须带时区")
    if dt.utcoffset().total_seconds() != 0:
        raise ValueError("时间必须为 UTC")
    return dt.timestamp()


def _loads_strict(text: str):
    """拒绝重复键、浮点数、Infinity/NaN 常量的 JSON 解析。"""

    def _no_dup(pairs):
        obj = {}
        for key, val in pairs:
            if key in obj:
                raise ValueError(f"重复键: {key}")
            obj[key] = val
        return obj

    def _bad_number(_):
        raise ValueError("不允许浮点数/非常量")

    return json.loads(text, object_pairs_hook=_no_dup,
                      parse_float=_bad_number, parse_constant=_bad_number)


class _LicenseFormatError(ValueError):
    """许可/申请格式校验失败。"""


def _validate_uuid(value, field: str) -> str:
    if not isinstance(value, str) or len(value) > 64:
        raise _LicenseFormatError(f"{field} 非法")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise _LicenseFormatError(f"{field} 非法") from exc


def _verify_envelope(data: bytes, trusted_keys) -> dict:
    """严格解析并验签 license envelope；任何失败抛 _LicenseFormatError。

    2026-10-28 起仅接受 SLT2 装甲格式（v2-only，明文 v1 信封一律拒绝）；
    装甲内层仍是既有的 canonical JSON envelope，签名语义不变。"""
    if len(data) > MAX_LICENSE_BYTES:
        raise _LicenseFormatError("许可文件超长")
    try:
        inner = open_container(KIND_LICENSE, data, list(trusted_keys.values()))
    except ValueError as exc:
        raise _LicenseFormatError("许可必须为 SLT2 装甲格式") from exc
    try:
        env = _loads_strict(inner.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise _LicenseFormatError("许可不是 UTF-8") from exc
    except ValueError as exc:
        raise _LicenseFormatError(f"许可 JSON 非法: {exc}") from exc
    if not isinstance(env, dict) or set(env) != {"format", "keyId", "payload", "signature"}:
        raise _LicenseFormatError("许可 envelope 字段不精确匹配")
    if env["format"] != LICENSE_FORMAT or not isinstance(env["keyId"], str):
        raise _LicenseFormatError("许可 format/keyId 非法")
    sig_text = env["signature"]
    try:
        if not isinstance(sig_text, str):
            raise ValueError("签名必须是 base64 字符串")
        signature = base64.b64decode(sig_text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _LicenseFormatError(f"签名 base64 非法: {exc}") from exc
    if len(signature) != 64:
        raise _LicenseFormatError("签名必须是 64 字节")
    key_b64 = trusted_keys.get(env["keyId"])
    if not isinstance(key_b64, str):
        raise _LicenseFormatError("未知 keyId")
    try:
        raw_key = base64.b64decode(key_b64, validate=True)
        public_key = Ed25519PublicKey.from_public_bytes(raw_key)
    except (binascii.Error, ValueError) as exc:
        raise _LicenseFormatError("信任公钥非法") from exc
    signed = _canonical_json({"format": env["format"], "keyId": env["keyId"],
                              "payload": env["payload"]})
    try:
        public_key.verify(signature, signed)
    except InvalidSignature as exc:
        raise _LicenseFormatError("签名校验失败") from exc
    except Exception as exc:  # 验签库异常：fail closed
        raise _LicenseFormatError("验签库异常") from exc
    if not isinstance(env["payload"], dict):
        raise _LicenseFormatError("payload 必须是对象")
    return env["payload"]


_PAYLOAD_FIELDS = ("version", "product", "licenseId", "clientId", "issuedAt",
                   "notBefore", "expiresAt", "customer", "requestId")


def _validate_payload(payload: dict) -> dict:
    """校验 payload 固定字段与时间关系，返回归一化结果（epoch 秒）。"""
    if set(payload) != set(_PAYLOAD_FIELDS):
        raise _LicenseFormatError("payload 字段不精确匹配")
    version = payload["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise _LicenseFormatError("version 必须为整数 1")
    if payload["product"] != PRODUCT_NAME:
        raise _LicenseFormatError("product 不匹配")
    client_id = payload["clientId"]
    if not isinstance(client_id, str) or not _HEX64_RE.fullmatch(client_id):
        raise _LicenseFormatError("clientId 非法")
    customer = payload["customer"]
    if not isinstance(customer, str) or len(customer) > MAX_CUSTOMER_LEN:
        raise _LicenseFormatError("customer 缺失或超长")
    issued_at = _parse_utc_time(payload["issuedAt"])
    not_before = _parse_utc_time(payload["notBefore"])
    expires_at = _parse_utc_time(payload["expiresAt"])
    if not not_before < expires_at:
        raise _LicenseFormatError("notBefore 必须早于 expiresAt")
    if issued_at > expires_at:
        raise _LicenseFormatError("issuedAt 必须不晚于 expiresAt")
    return {"version": 1, "product": PRODUCT_NAME,
            "licenseId": _validate_uuid(payload["licenseId"], "licenseId"),
            "clientId": client_id, "customer": customer,
            "requestId": _validate_uuid(payload["requestId"], "requestId"),
            "issuedAt": issued_at, "notBefore": not_before, "expiresAt": expires_at}


class LicenseService:
    """授权核心服务；线程锁串行导入与时间状态。日期判定只用注入时钟。"""

    def __init__(self, license_dir, *, machine_provider=None, state_store=None,
                 trusted_keys=None, now=None, monotonic=None,
                 persist_interval: float = DEFAULT_PERSIST_INTERVAL):
        self._dir = os.fspath(license_dir)
        self._file = os.path.join(self._dir, LICENSE_FILENAME)
        self._machine = machine_provider or machine_fingerprint
        self._store = state_store
        self._trusted = TRUSTED_KEYS if trusted_keys is None else trusted_keys
        self._now = now or time.time
        self._mono = monotonic or time.monotonic
        self._persist_interval = float(persist_interval)
        self._lock = threading.Lock()
        self._wall0 = self._wall_ts()
        self._mono0 = float(self._mono())
        self._fingerprint = None
        self._last_persisted = None

    def _wall_ts(self) -> float:
        value = self._now()
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Injected datetime must include a timezone")
            return value.timestamp()
        result = float(value)
        if not math.isfinite(result) or result < 0:
            raise ValueError("Invalid clock")
        return result

    def _fingerprint_cached(self) -> str:
        if self._fingerprint is None:
            fp = self._machine()
            if not isinstance(fp, str) or not _HEX64_RE.fullmatch(fp):
                raise LicenseError("机器指纹非法")
            self._fingerprint = fp
        return self._fingerprint

    def _read_license(self):
        try:
            with open(self._file, "rb") as fh:
                return fh.read(MAX_LICENSE_BYTES + 1)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise StateStoreError("授权文件读取失败") from exc

    def _evaluate(self, candidate=None) -> dict:
        """时间基线 + 许可内容评估，不做任何写操作。"""
        try:
            fp = self._fingerprint_cached()
        except Exception:
            return {"error": STATE_MACHINE_UNAVAILABLE}
        try:
            if self._store is None:
                self._store = WindowsClockStateStore(fp)
            wall = self._wall_ts()
            mono_floor = self._wall0 + (float(self._mono()) - self._mono0)
            stored = self._store.read() if self._store is not None else None
        except Exception:
            _LOG.warning("时间状态存储读取失败", exc_info=True)
            return {"error": STATE_STORAGE_ERROR}
        candidates = [wall, mono_floor]
        if stored is not None:
            candidates.append(float(stored))
        high = max(candidates)
        result = {"error": None, "wall": wall, "high": high,
                  "rollback": wall < high - ROLLBACK_TOLERANCE_SECONDS}
        if result["rollback"]:
            result["error"] = STATE_CLOCK_ROLLBACK
            return result
        try:
            raw = self._read_license() if candidate is None else candidate
        except StateStoreError:
            result["error"] = STATE_STORAGE_ERROR
            return result
        if raw is None:
            result["error"] = STATE_MISSING
            return result
        try:
            payload = _validate_payload(_verify_envelope(raw, self._trusted))
        except Exception:
            _LOG.warning("许可验签/解析失败", exc_info=True)
            result["error"] = STATE_INVALID
            return result
        result["payload"] = payload
        try:
            fp = self._fingerprint_cached()
        except Exception:
            _LOG.warning("机器指纹不可用", exc_info=True)
            result["error"] = STATE_MACHINE_UNAVAILABLE
            return result
        if not hmac.compare_digest(fp, payload["clientId"]):
            result["error"] = STATE_MACHINE_MISMATCH
            return result
        if high < payload["notBefore"]:
            result["error"] = STATE_NOT_YET_VALID
        elif high >= payload["expiresAt"]:
            result["error"] = STATE_EXPIRED
        return result

    def _status_from(self, ev: dict) -> dict:
        state = ev["error"] or STATE_VALID
        payload = ev.get("payload") or {}
        high = ev.get("high")
        expires_at = payload.get("expiresAt")
        days = (math.ceil((expires_at - high) / 86400.0)
                if expires_at is not None and high is not None else None)
        client_id = None
        if state != STATE_STORAGE_ERROR:
            try:
                client_id = self._fingerprint_cached()
            except Exception:
                client_id = None
        return {"state": state, "allowedToStart": state == STATE_VALID,
                "clientId": client_id,
                "expiresAt": _utc_z(expires_at) if expires_at is not None else None,
                "daysRemaining": days, "customer": payload.get("customer"),
                "licenseId": payload.get("licenseId"), "message": _MESSAGES[state]}

    def _persist(self, ev: dict, force: bool) -> None:
        """按策略落盘已观察最大时间；失败抛 StateStoreError（fail closed）。"""
        if self._store is None or ev.get("error") not in (None, STATE_EXPIRED, STATE_NOT_YET_VALID):
            return
        high = ev["high"]
        if not force and self._last_persisted is not None and \
                high - self._last_persisted < self._persist_interval:
            return
        if not force and high <= (self._last_persisted or 0):
            return
        self._store.write(high)
        self._last_persisted = high

    def status(self) -> dict:
        with self._lock:
            ev = self._evaluate()
            if ev.get("error") in (None, STATE_EXPIRED, STATE_NOT_YET_VALID):
                try:
                    crossed_expiry = (ev.get("error") == STATE_EXPIRED and
                                      (self._last_persisted is None or
                                       self._last_persisted < ev["payload"]["expiresAt"]))
                    self._persist(ev, force=crossed_expiry)
                except Exception:
                    _LOG.warning("时间状态落盘失败", exc_info=True)
                    return self._status_from({"error": STATE_STORAGE_ERROR})
            return self._status_from(ev)

    def require_valid(self) -> None:
        with self._lock:
            ev = self._evaluate()
            if ev.get("error"):
                if ev["error"] == STATE_EXPIRED:
                    try:
                        self._persist(ev, force=True)
                    except Exception:
                        ev["error"] = STATE_STORAGE_ERROR
                raise LicenseDenied(self._status_from(ev))
            try:
                self._persist(ev, force=True)
            except Exception:
                _LOG.warning("起测前强制落盘失败", exc_info=True)
                raise LicenseDenied(self._status_from(
                    {"error": STATE_STORAGE_ERROR})) from None

    def export_request(self) -> bytes:
        """导出申请：SLT2 装甲（客户不可读）；内层仍是 canonical JSON。"""
        with self._lock:
            try:
                request = {"format": CLIENT_FORMAT, "product": PRODUCT_NAME,
                           "clientId": self._fingerprint_cached(),
                           "requestId": str(uuid.uuid4()),
                           "requestedAt": _utc_z(self._wall_ts()),
                           "fingerprintVersion": FINGERPRINT_VERSION}
            except Exception as exc:
                raise LicenseError("无法读取机器标识或时间") from exc
        wrap_key = next(iter(self._trusted.values()), None)
        if not isinstance(wrap_key, str):
            raise LicenseError("缺少信任公钥，无法封装申请")
        try:
            return seal(KIND_REQUEST, _canonical_json(request), wrap_key)
        except ValueError as exc:
            raise LicenseError("申请封装失败") from exc

    def import_license(self, data) -> dict:
        if isinstance(data, str):
            data = data.encode("utf-8")
        blob = bytes(data)
        with self._lock:
            try:
                payload = _validate_payload(_verify_envelope(blob, self._trusted))
            except Exception:
                _LOG.warning("许可导入校验失败", exc_info=True)
                return self._status_from({"error": STATE_INVALID})
            try:
                fp = self._fingerprint_cached()
            except Exception:
                _LOG.warning("许可导入时机器指纹不可用", exc_info=True)
                return self._status_from({"error": STATE_MACHINE_UNAVAILABLE})
            if not hmac.compare_digest(fp, payload["clientId"]):
                return self._status_from({"error": STATE_MACHINE_MISMATCH,
                                          "payload": payload})
            ev = self._evaluate(candidate=blob)
            if ev.get("error"):
                return self._status_from(ev)
            try:
                self._persist(ev, force=True)
                self._atomic_write(blob)
            except Exception:
                _LOG.warning("许可落盘失败", exc_info=True)
                return self._status_from({"error": STATE_STORAGE_ERROR})
            return self._status_from(ev)

    def _atomic_write(self, data: bytes) -> None:
        os.makedirs(self._dir, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".license_", dir=self._dir)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, self._file)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
