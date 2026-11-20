"""抗回拨时间状态存储。

契约 = docs/LICENSE_DESIGN.md「Windows10/11机器与时间」：
- ClockStateStore 接口：read() -> float|None / write(timestamp) -> None，
  测试注入内存实现。
- WindowsClockStateStore(clientId)：LOCALAPPDATA/Acroview/LPDDR4x_SCADA 下
  DPAPI 保护文件 + HKCU/Software/Acroview/LPDDR4x_SCADA 的 REG_BINARY，
  两处保存相同 {product, clientId, lastSeen} 记录；读时取有效副本最大
  lastSeen；存在但损坏的全部副本 → 失败；只有一份有效 → 修复另一份；
  写失败抛异常。
- DPAPI：CryptProtectData/CryptUnprotectData，CRYPTPROTECT_UI_FORBIDDEN，
  不弹窗、不要求管理员；LocalFree 释放；ctypes 签名/指针在 64 位正确。
- 文件原子写入（临时文件 + os.replace）。

能力边界（合同明示）：DPAPI 只挡同机非授权用户拷贝，挡不住管理员与整机
快照回滚；不宣传"防破解"。
"""

import ctypes
import json
import math
import os
import re
import tempfile
import threading
from typing import Optional, Tuple

try:
    import winreg
except ImportError:  # 非 Windows 平台可导入，实例化使用时显式失败
    winreg = None

if os.name == "nt":
    from ctypes import wintypes

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32
    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), wintypes.LPCWSTR,
        ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptProtectData.restype = wintypes.BOOL
    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p,
        ctypes.POINTER(_DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    _kernel32.LocalFree.restype = wintypes.HLOCAL
else:
    _DATA_BLOB = None
    _crypt32 = None
    _kernel32 = None

# CRYPTPROTECT_UI_FORBIDDEN：禁止任何弹窗。
_UI_FORBIDDEN = 0x1

PRODUCT = "LPDDR4x_SCADA"
_REG_DIR = os.path.join("Acroview", "LPDDR4x_SCADA")
_REG_KEY = r"Software\Acroview\LPDDR4x_SCADA"
_REG_VALUE = "clock_state"
_FILE_NAME = "clock_state.bin"
_REG_BINARY_TYPE = getattr(winreg, "REG_BINARY", 3)


class StateStoreError(Exception):
    """时间状态存储失败（读取/写入/全部副本损坏）：调用方禁止起测。"""


class ClockStateStore:
    """接口约定：read() -> float|None；write(timestamp: float) -> None。"""

    def read(self) -> Optional[float]:
        raise NotImplementedError

    def write(self, timestamp: float) -> None:
        raise NotImplementedError


def _dpapi_protect(data: bytes) -> bytes:
    if _crypt32 is None:
        raise StateStoreError("DPAPI 不可用（非 Windows）")
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DATA_BLOB()
    ok = _crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, _UI_FORBIDDEN,
        ctypes.byref(blob_out),
    )
    if not ok:
        raise StateStoreError(f"CryptProtectData 失败（{ctypes.GetLastError()}）")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        _kernel32.LocalFree(blob_out.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    if _crypt32 is None:
        raise StateStoreError("DPAPI 不可用（非 Windows）")
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DATA_BLOB()
    ok = _crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, _UI_FORBIDDEN,
        ctypes.byref(blob_out),
    )
    if not ok:
        raise StateStoreError(f"CryptUnprotectData 失败（{ctypes.GetLastError()}）")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        _kernel32.LocalFree(blob_out.pbData)


def _encode_record(record: dict) -> bytes:
    return json.dumps(record, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _validate_record(obj, client_id: str) -> Optional[dict]:
    """记录结构校验；不属于本机身份/非法结构返回 None（视为损坏副本）。"""
    if not isinstance(obj, dict):
        return None
    if obj.get("product") != PRODUCT or obj.get("clientId") != client_id:
        return None
    last_seen = obj.get("lastSeen")
    if isinstance(last_seen, bool) or not isinstance(last_seen, (int, float)):
        return None
    if not math.isfinite(last_seen) or last_seen < 0:
        return None
    return {"product": PRODUCT, "clientId": client_id, "lastSeen": float(last_seen)}


def _atomic_write_file(path: str, data: bytes) -> None:
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".clock_state_", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _reg_read_raw(path: str, name: str):
    """返回 (data, type)；键/值不存在返回 None；访问错误抛 StateStoreError。"""
    if winreg is None:
        raise StateStoreError("winreg 不可用（非 Windows）")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise StateStoreError("注册表读取失败") from exc


def _reg_write_raw(path: str, name: str, data: bytes) -> None:
    if winreg is None:
        raise StateStoreError("winreg 不可用（非 Windows）")
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_BINARY, data)
    except OSError as exc:
        raise StateStoreError("注册表写入失败") from exc


class WindowsClockStateStore(ClockStateStore):
    """文件 + 注册表双副本，相同 DPAPI 保护记录；线程安全。"""

    def __init__(self, client_id: str):
        text = client_id if isinstance(client_id, str) else ""
        if not re.fullmatch(r"[0-9a-f]{64}", text):
            raise StateStoreError("clientId 非法，拒绝创建状态存储")
        self._client_id = text
        base = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local"
        )
        self._dir = os.path.join(base, _REG_DIR, text)
        self._reg_key = _REG_KEY + "\\" + text
        self._file = os.path.join(self._dir, _FILE_NAME)
        self._lock = threading.RLock()

    def _seal(self, record: dict) -> bytes:
        return _dpapi_protect(_encode_record(record))

    def _open(self, blob: bytes) -> Optional[dict]:
        try:
            plain = _dpapi_unprotect(blob)
        except StateStoreError:
            return None
        try:
            obj = json.loads(plain.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        return _validate_record(obj, self._client_id)

    def _read_file_copy(self) -> Tuple[Optional[dict], bool]:
        """-> (有效记录|None, 是否损坏存在)。"""
        try:
            with open(self._file, "rb") as fh:
                blob = fh.read()
        except FileNotFoundError:
            return None, False
        except OSError as exc:
            raise StateStoreError("时间状态文件读取失败") from exc
        record = self._open(blob)
        return record, record is None

    def _read_reg_copy(self) -> Tuple[Optional[dict], bool]:
        raw = _reg_read_raw(self._reg_key, _REG_VALUE)
        if raw is None:
            return None, False
        data, typ = raw
        if typ != _REG_BINARY_TYPE or not isinstance(data, (bytes, bytearray)):
            return None, True
        record = self._open(bytes(data))
        return record, record is None

    def read(self) -> Optional[float]:
        with self._lock:
            file_rec, file_bad = self._read_file_copy()
            reg_rec, reg_bad = self._read_reg_copy()
            valids = [r for r in (file_rec, reg_rec) if r is not None]
            if not valids:
                if file_bad or reg_bad:
                    raise StateStoreError("时间状态副本存在但全部损坏")
                return None
            best = max(valids, key=lambda r: r["lastSeen"])
            # 只有一份有效，或两份 lastSeen 不一致 → 用最佳副本修复两处。
            need_repair = (
                file_rec is None
                or reg_rec is None
                or file_rec["lastSeen"] != reg_rec["lastSeen"]
            )
            if need_repair:
                try:
                    self._write_locked(best["lastSeen"])
                except StateStoreError:
                    pass  # 修复失败不掩盖有效副本
            return float(best["lastSeen"])

    def _write_locked(self, timestamp: float) -> None:
        value = float(timestamp)
        if not math.isfinite(value) or value < 0:
            raise StateStoreError("lastSeen 非法，拒绝写入")
        record = {"product": PRODUCT, "clientId": self._client_id,
                  "lastSeen": value}
        blob = self._seal(record)
        os.makedirs(self._dir, exist_ok=True)
        _atomic_write_file(self._file, blob)
        _reg_write_raw(self._reg_key, _REG_VALUE, blob)

    def write(self, timestamp: float) -> None:
        with self._lock:
            value = float(timestamp)
            if not math.isfinite(value) or value < 0:
                raise StateStoreError("lastSeen 非法")
            previous = self.read()
            self._write_locked(max(value, previous or 0))
