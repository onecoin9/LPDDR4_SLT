"""Host-side run guards. Limits are monotonic and frozen when a run is admitted."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StageLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_default=True)
    PL: float = Field(0, ge=0, le=86400, allow_inf_nan=False)
    LK: float = Field(0, ge=0, le=86400, allow_inf_nan=False)
    APK: float = Field(0, ge=0, le=86400, allow_inf_nan=False)


class RunPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_default=True)
    cfgAckTimeoutSec: float = Field(0, ge=0, le=3600, allow_inf_nan=False)
    cfgRetryIntervalSec: float = Field(0, ge=0, le=600, allow_inf_nan=False)
    stageTimeoutSec: StageLimits = Field(default_factory=StageLimits)
    checkReadyVersion: bool = False
    expectedReadyVersion: str = Field("", max_length=64)

    @field_validator("expectedReadyVersion")
    @classmethod
    def version_text(cls, value):
        value = value.strip()
        if any(ord(c) < 32 or ord(c) > 126 for c in value):
            raise ValueError("READY version must contain printable ASCII characters")
        return value

    @model_validator(mode="after")
    def required_version(self):
        if self.checkReadyVersion and not self.expectedReadyVersion:
            raise ValueError("Expected READY version is required when checking is enabled")
        return self

    def version_failure(self, actual):
        actual = str(actual or "").replace("\x00", "").strip()
        if self.checkReadyVersion and actual != self.expectedReadyVersion:
            return f"version_mismatch:expected={self.expectedReadyVersion}:actual={actual or 'missing'}"
        return None

    @property
    def revision(self):
        value = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(value.encode()).hexdigest()


class PolicyUnavailable(ValueError):
    pass


class PolicyConflict(ValueError):
    pass


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".run-", suffix=".tmp", delete=False) as f:
            temporary = f.name
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                pass


class PolicyStore:
    def __init__(self, path):
        self.path = Path(path)
        self.policy = RunPolicy()
        self.error = None
        if self.path.exists():
            try:
                self.policy = RunPolicy.model_validate_json(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                self.error = str(exc)

    def status(self):
        return {"valid": self.error is None, "error": self.error,
                "policy": self.policy.model_dump(), "revision": self.policy.revision}

    def snapshot(self):
        if self.error:
            raise PolicyUnavailable("运行保护配置损坏，请重新保存 / Invalid run policy; save a valid policy")
        return self.policy.model_copy(deep=True)

    def save(self, policy, expected_revision=None):
        if expected_revision is not None and expected_revision != self.policy.revision:
            raise PolicyConflict("运行保护已被其他窗口修改，请重新读取 / Policy changed; reload before saving")
        atomic_json(self.path, policy.model_dump())
        self.policy, self.error = policy.model_copy(deep=True), None
        return self.status()


class RunGuard:
    """Only explicit forward stage reports start a stage budget; duplicates never renew it."""
    def __init__(self, policy, stages, sent_at):
        self.policy = policy.model_copy(deep=True)
        self.stages = list(stages)
        self.sent_at = sent_at
        self.cfg_sent_at = sent_at
        self.acked = False
        self.stage = None
        self.entered_at = None
        self.observations = []

    def ack(self):
        self.acked = True

    def restart_cfg(self, now):
        self.cfg_sent_at, self.acked = now, False

    def observe(self, stage, now):
        if stage not in self.stages:
            return False
        if self.stage is not None and self.stages.index(stage) <= self.stages.index(self.stage):
            return False
        self.stage, self.entered_at = stage, now
        self.observations.append({"stage": stage, "elapsedSec": round(now - self.sent_at, 3)})
        return True

    def deadlines(self):
        values = []
        if not self.acked and self.policy.cfgAckTimeoutSec > 0:
            values.append((self.cfg_sent_at + self.policy.cfgAckTimeoutSec, "cfg_ack_timeout"))
        if self.stage is not None:
            limit = getattr(self.policy.stageTimeoutSec, self.stage)
            if limit > 0:
                values.append((self.entered_at + limit, f"stage_timeout:{self.stage}"))
        return sorted(values)

    def remaining(self, now):
        deadlines = self.deadlines()
        return max(0, deadlines[0][0] - now) if deadlines else None

    def expired(self, now):
        deadlines = self.deadlines()
        return deadlines[0][1] if deadlines and now >= deadlines[0][0] else None
