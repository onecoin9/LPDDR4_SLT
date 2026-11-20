"""Issuer-only DPAPI key storage. This module must never enter a customer package."""
import base64
import ctypes as ct
from ctypes import wintypes as wt
import hashlib
import json
import os
from pathlib import Path
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ENTROPY = b"LPDDR4x_SCADA:ISSUER:v1"


class Blob(ct.Structure):
    _fields_ = [("size", wt.DWORD), ("data", ct.POINTER(ct.c_ubyte))]


def _blob(raw):
    buffer = (ct.c_ubyte * len(raw)).from_buffer_copy(raw)
    return Blob(len(raw), ct.cast(buffer, ct.POINTER(ct.c_ubyte))), buffer


def dpapi(raw, decrypt=False):
    if sys.platform != "win32":
        raise OSError("Issuer key storage requires Windows")
    crypt = ct.WinDLL("crypt32", use_last_error=True)
    kernel = ct.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ct.c_void_p]
    kernel.LocalFree.restype = ct.c_void_p
    source, source_buffer = _blob(raw)
    entropy, entropy_buffer = _blob(ENTROPY)
    output = Blob()
    if decrypt:
        fn = crypt.CryptUnprotectData
        fn.argtypes = [ct.POINTER(Blob), ct.POINTER(wt.LPWSTR), ct.POINTER(Blob), ct.c_void_p, ct.c_void_p, wt.DWORD, ct.POINTER(Blob)]
        params = (ct.byref(source), None, ct.byref(entropy), None, None, 1, ct.byref(output))
    else:
        fn = crypt.CryptProtectData
        fn.argtypes = [ct.POINTER(Blob), wt.LPCWSTR, ct.POINTER(Blob), ct.c_void_p, ct.c_void_p, wt.DWORD, ct.POINTER(Blob)]
        params = (ct.byref(source), "SCADA license issuer", ct.byref(entropy), None, None, 1, ct.byref(output))
    fn.restype = wt.BOOL
    if not fn(*params):
        raise ct.WinError(ct.get_last_error())
    try:
        return ct.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(ct.cast(output.data, ct.c_void_p))


def create_key(path, public_output):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes_raw()
    key_id = "slt-" + hashlib.sha256(public).hexdigest()[:16]
    record = {"format": "slt-issuer-key-v1", "keyId": key_id,
              "publicKey": base64.b64encode(public).decode("ascii"),
              "protectedPrivateKey": base64.b64encode(dpapi(private.private_bytes_raw())).decode("ascii")}
    # Exclusive create: key rotation is deliberate, never overwrite an existing private key.
    with path.open("x", encoding="utf-8") as out:
        json.dump(record, out, sort_keys=True)
    public_output = Path(public_output)
    public_output.parent.mkdir(parents=True, exist_ok=True)
    public_output.write_text(json.dumps({"keyId": key_id, "publicKey": record["publicKey"]}, indent=2), encoding="utf-8")
    return key_id


def load_key(path):
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if record.get("format") != "slt-issuer-key-v1":
        raise ValueError("Unsupported issuer key file")
    if set(record) != {"format", "keyId", "publicKey", "protectedPrivateKey"}:
        raise ValueError("Invalid issuer key metadata")
    private = Ed25519PrivateKey.from_private_bytes(dpapi(base64.b64decode(record["protectedPrivateKey"], validate=True), True))
    if base64.b64encode(private.public_key().public_bytes_raw()).decode("ascii") != record["publicKey"]:
        raise ValueError("Issuer key metadata was changed")
    if record["keyId"] != "slt-" + hashlib.sha256(private.public_key().public_bytes_raw()).hexdigest()[:16]:
        raise ValueError("Issuer key identity was changed")
    return record["keyId"], private
