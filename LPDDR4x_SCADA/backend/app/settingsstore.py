"""One atomic JSON document for the settings window; manual debug is separate."""
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import IoControlConfig
from .runtimepolicy import RunPolicy, PolicyConflict, PolicyUnavailable, atomic_json


class BasicSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    language: Literal["zh", "en"] = "zh"
    theme: Literal["dark", "light", "industrial", "gundam", "cyberpunk", "meadow", "nord", "solarized"] = "dark"
    logPath: str = Field("records", max_length=4096)

    @field_validator("logPath")
    @classmethod
    def path_text(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Log path is required")
        return value


class HandlerSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    rx_port: int = Field(7000, ge=1, le=65535)
    tx_host: str = Field("", max_length=253)
    tx_port: int = Field(64100, ge=1, le=65535)

    @field_validator("tx_host")
    @classmethod
    def host_text(cls, value):
        value = value.strip()
        if value and not all(c.isascii() and (c.isalnum() or c in ".-_:") for c in value):
            raise ValueError("Invalid IP address or hostname")
        return value


class SettingsIO(IoControlConfig):
    model_config = ConfigDict(extra="forbid", strict=True)


class SettingsDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schemaVersion: Literal[1] = 1
    basic: BasicSettings = Field(default_factory=BasicSettings)
    ioControl: SettingsIO = Field(default_factory=SettingsIO)
    handler: HandlerSettings = Field(default_factory=HandlerSettings)
    runtimePolicy: RunPolicy = Field(default_factory=RunPolicy)
    products: dict[str, dict] = Field(default_factory=dict)
    browserMigrationPending: list[Literal["basic", "ioControl", "products"]] = Field(default_factory=list)

    @model_validator(mode="after")
    def product_names(self):
        self.products = {name: {k: v for k, v in profile.items() if k != "timingContext"}
                         for name, profile in self.products.items()}
        for name, profile in self.products.items():
            if not name.strip() or profile.get("name") != name:
                raise ValueError("Product key must equal the profile name")
        return self


def revision(document):
    data = json.dumps(document.model_dump(), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def read_document(path):
    path = Path(path)
    if path.suffix.lower() != ".json":
        raise ValueError("Settings file must be JSON / 设置文件必须为 JSON")
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Settings file exceeds 16 MiB")
    text = path.read_text(encoding="utf-8-sig")
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    value = json.loads(text, object_pairs_hook=no_duplicates)
    if not isinstance(value, dict) or type(value.get("schemaVersion")) is not int or value["schemaVersion"] != 1 or "basic" not in value:
        raise ValueError("Not a settings document / 不是上位机设置文件")
    return SettingsDocument.model_validate(value)


def legacy_document(directory, config):
    """Strict migration of backend legacy settings; never delete the old files."""
    directory = Path(directory)
    def load(name, fallback):
        path = directory / name
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else fallback
    handler = {k: v for k, v in (config.get("handler") or {}).items()
               if k in HandlerSettings.model_fields}
    handler.update({k: v for k, v in load("handler_settings.json", {}).items()
                    if k in HandlerSettings.model_fields})
    profiles = {}
    for path in sorted((directory / "products").glob("*.json")):
        profile = json.loads(path.read_text(encoding="utf-8-sig"))
        name = profile.get("name", path.stem)
        profile["name"] = name
        profiles[name] = profile
    machine = load("machine_settings.json", {})
    io = machine.get("ioControl")
    return SettingsDocument(basic={"logPath": config.get("records_dir", "records")},
                            handler=handler, ioControl=io or {}, products=profiles,
                            runtimePolicy=load("runtime_policy.json", {}),
                            browserMigrationPending=["basic", "ioControl", "products"])


def configured_path(directory):
    directory = Path(directory).resolve()
    pointer = directory / ".settings.active"
    if pointer.exists():
        value = json.loads(pointer.read_text(encoding="utf-8"))
        if not isinstance(value, str) or not value:
            raise ValueError("Invalid active settings path")
        path = Path(value)
        return (path if path.is_absolute() else directory / path).resolve()
    return directory / "settings.json"


class SettingsStore:
    def __init__(self, directory, config):
        self.directory = Path(directory).resolve()
        self.path = self.directory / "settings.json"
        self.document = SettingsDocument()
        self.error = None
        self.disk_hash = None
        try:
            self.path = configured_path(self.directory)
            if self.path.exists():
                self.document = read_document(self.path)
            elif self.path == self.directory / "settings.json":
                self.document = legacy_document(self.directory, config)
                atomic_json(self.path, self.document.model_dump())
            else:
                raise FileNotFoundError("Selected settings file is missing")
            self.disk_hash = self._hash()
        except (OSError, ValueError) as exc:
            self.error = str(exc)

    def _hash(self):
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def status(self):
        return {"valid": self.error is None, "error": self.error,
                "path": str(self.path), "revision": revision(self.document),
                "settings": self.document.model_dump()}

    def snapshot(self):
        if self.error:
            raise PolicyUnavailable("设置文件不可用，请重新选择有效的 JSON / Select a valid settings file")
        return self.document.model_copy(deep=True)

    def candidate(self, updates, expected_revision):
        current = self.snapshot()
        if expected_revision != revision(current) or self._hash() != self.disk_hash:
            raise PolicyConflict("设置已被修改，请重新读取 / Settings changed; reload before saving")
        if not updates or set(updates) - set(SettingsDocument.model_fields) or "schemaVersion" in updates:
            raise ValueError("Invalid settings update")
        value = current.model_dump()
        for key, update in updates.items():
            if key in ("basic", "handler", "ioControl") and isinstance(update, dict):
                value[key].update(update)
            else:
                value[key] = update
        return SettingsDocument.model_validate(value)

    def save(self, document):
        # Runtime is updated by the caller only after this succeeds.
        if self.disk_hash is not None and self._hash() != self.disk_hash:
            raise PolicyConflict("设置文件已在外部修改 / Settings file changed externally")
        atomic_json(self.path, document.model_dump())
        self.document, self.error, self.disk_hash = document.model_copy(deep=True), None, self._hash()
        return self.status()

    def select(self, path, document):
        path = Path(path).resolve()
        # Detect an external edit between validation and activation.
        if revision(read_document(path)) != revision(document):
            raise PolicyConflict("Selected file changed; select it again")
        try:
            value = str(path.relative_to(self.directory))
        except ValueError:
            value = str(path)
        atomic_json(self.directory / ".settings.active", value)
        self.path, self.document, self.error = path, document.model_copy(deep=True), None
        self.disk_hash = self._hash()
        return self.status()


class SettingsPolicyStore:
    """Preserve the run-policy API and per-run snapshots using the unified file."""
    def __init__(self, settings):
        self.settings = settings

    def status(self):
        policy = self.settings.document.runtimePolicy
        return {"valid": self.settings.error is None, "error": self.settings.error,
                "policy": policy.model_dump(), "revision": policy.revision}

    def snapshot(self):
        return self.settings.snapshot().runtimePolicy
