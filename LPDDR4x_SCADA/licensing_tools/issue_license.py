"""Issuer-only signing, with an explicit expiry date and confirmation in the GUI."""
import base64
import datetime as dt
import json
import uuid
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from .client_request import PRODUCT, read_request, utc_text
from .license_container import KIND_LICENSE, seal
from .private_key import load_key

BEIJING_TIME = dt.timezone(dt.timedelta(hours=8))


def issue(request_file, key_file, customer, expires_on, output, starts_on=None, *, days=None):
    request = read_request(Path(request_file).read_bytes())
    if not isinstance(customer, str) or not 1 <= len(customer.strip()) <= 128:
        raise ValueError("Customer name is required (maximum 128 characters)")
    now = dt.datetime.now(dt.UTC)
    if days is not None:
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 3650:
            raise ValueError("Days must be an integer between 1 and 3650")
        if expires_on is not None:
            raise ValueError("Choose either days or an expiry date")
        end = now + dt.timedelta(days=days)
    else:
        expiry_date = dt.date.fromisoformat(expires_on)
        end = dt.datetime.combine(expiry_date + dt.timedelta(days=1), dt.time(), BEIJING_TIME).astimezone(dt.UTC)
    start = dt.datetime.combine(dt.date.fromisoformat(starts_on), dt.time(), BEIJING_TIME).astimezone(dt.UTC) if starts_on else now
    if end <= now or start >= end:
        raise ValueError("Expiry must be in the future and after the start")
    key_id, private = load_key(key_file)
    public_b64 = base64.b64encode(private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode("ascii")
    payload = {"version": 1, "product": PRODUCT, "licenseId": str(uuid.uuid4()),
               "clientId": request["clientId"], "requestId": request["requestId"],
               "customer": customer.strip(), "issuedAt": utc_text(now),
               "notBefore": utc_text(start), "expiresAt": utc_text(end)}
    signed = {"format": "slt-license-v1", "keyId": key_id, "payload": payload}
    canonical = json.dumps(signed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    envelope = {**signed, "signature": base64.b64encode(private.sign(canonical)).decode("ascii")}
    # SLT2 装甲：客户只能看到无意义字符串；内层签名字节与明文时代完全一致。
    inner = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    armored = seal(KIND_LICENSE, inner, public_b64)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse accidental overwrite; renewal should use a fresh destination or a conscious GUI choice.
    with output.open("x", encoding="utf-8") as out:
        out.write(armored.decode("ascii"))
    return {"licenseId": payload["licenseId"], "expiresAt": payload["expiresAt"], "keyId": key_id}
