"""Validate and copy private runtime data; only path fields may change."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.manual import ManualDebug
from app.cfg import base_cfg
from app.models import MachineConfig
from app.profileplan import require_profile
from app.settingsstore import configured_path, read_document, legacy_document


def _active_product_cfg(directory: Path, settings, cfg: dict) -> tuple[str, str]:
    """Match main.py's startup product selection without importing its device services."""
    try:
        value = json.loads((directory / "machine_settings.json").read_text(encoding="utf-8"))
        if isinstance(value, dict):
            value = {key: item for key, item in value.items() if key != "profile"}
        machine = MachineConfig(**value)
    except (OSError, ValueError, TypeError):
        machine = MachineConfig()
    selected = machine.product
    if selected not in settings.products:
        selected = next(iter(settings.products), "")
    profile = settings.products.get(selected)
    if profile is None:
        raise ValueError("Field full-run package requires a valid selected product in settings")
    # Invalid profiles fail closed. A legacy cfg or scheme is never a fallback.
    return selected, require_profile(profile, base_cfg(cfg))["cfgText"]


def stage_payload(source: Path, package: Path, front: Path, mode: str) -> dict:
    source, package = source.resolve(), package.resolve()
    cfg = yaml.safe_load((source / "config.yaml").read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError("config.yaml must be a mapping")
    if mode == "mock":
        for name in ("manual_debug", "commboard", "tempctrl", "handler"):
            if (cfg.get(name) or {}).get("enabled"):
                raise ValueError(f"Mock package requires {name}.enabled=false")
        if not isinstance(cfg.get("sites"), list) or any(
            slot["ip"] != "127.0.0.1" for site in cfg["sites"] for slot in site["slots"]):
            raise ValueError("Mock package requires explicit loopback-only sites")
    md = ManualDebug(cfg, str(source))  # Configuration parsing only; no I/O to devices.
    session_path = source / "session_settings.json"
    session = json.loads(session_path.read_text(encoding="utf-8")) if session_path.exists() else None
    if session is not None and not isinstance(session, dict):
        raise ValueError("session_settings.json must be a mapping")
    if mode == "field" and md.enabled and session is None:
        raise FileNotFoundError("Field manual configuration requires session_settings.json")
    active_settings = configured_path(source)
    settings = (read_document(active_settings) if active_settings.exists()
                else legacy_document(source, cfg))
    if active_settings != source / "settings.json" and not active_settings.exists():
        raise FileNotFoundError("Selected settings file missing")
    effective = None
    active_product = None
    if mode == "field" and md.enabled and md.run_mode == "full_run":
        active_product, effective = _active_product_cfg(source, settings, cfg)
    package.mkdir(parents=True, exist_ok=True)
    # The selected settings travel as one portable file, never an external path.
    (package / "settings.json").write_text(json.dumps(settings.model_dump(), ensure_ascii=False,
                                                    indent=2, allow_nan=False), encoding="utf-8")
    for name in ("manual_debug.cfg", "machine_settings.json", "runtime_policy.json"):
        if (source / name).is_file():
            shutil.copy2(source / name, package / name)
    for name in ("products", "strategies"):
        if (source / name).is_dir():
            shutil.copytree(source / name, package / name, dirs_exist_ok=True)
    license_file = source / "license/license.lic"
    if license_file.is_file():
        (package / "license").mkdir(exist_ok=True)
        shutil.copy2(license_file, package / "license/license.lic")
    changes = []

    def portable_cfg(value):
        original = Path(value)
        path = original if original.is_absolute() else source / original
        if not path.is_file():
            # Inactive legacy references must not control product-based startup.
            # Preserve the user's path and data; copy existing files when possible.
            return value
        relative = original if not original.is_absolute() and ".." not in original.parts else Path("strategies") / path.name
        dest = package / relative
        if dest.exists() and dest.read_bytes() != path.read_bytes():
            raise ValueError(f"Conflicting cfg filename: {relative}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        return relative.as_posix()

    raw_md = cfg.get("manual_debug") or {}
    if raw_md.get("cfg_file"):
        value = portable_cfg(raw_md["cfg_file"])
        if value != raw_md["cfg_file"]:
            changes.append("config.manual_debug.cfg_file")
        raw_md["cfg_file"] = value
    if session and session.get("cfg_file"):
        value = portable_cfg(session["cfg_file"])
        if value != session["cfg_file"]:
            changes.append("session.cfg_file")
        session["cfg_file"] = value
    for obj, label in ((raw_md, "config.manual_debug"), (session, "session")):
        if obj and obj.get("log_dir"):
            if obj["log_dir"] != "manual_logs":
                changes.append(label + ".log_dir")
            obj["log_dir"] = "manual_logs"
    if Path(str(cfg.get("records_dir", "records"))).is_absolute():
        cfg["records_dir"] = "records"
        changes.append("config.records_dir")
    (package / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if session is not None:
        (package / "session_settings.json").write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    packed_md = ManualDebug(cfg, str(package))
    if effective is not None:
        packed_product, packed_effective = _active_product_cfg(
            package, read_document(package / "settings.json"), cfg)
        if packed_product != active_product or packed_effective != effective:
            raise AssertionError("Packaged product cfg differs from original effective cfg")
    shutil.copytree(front, package / "frontend_dist", dirs_exist_ok=True)
    return {"path_fields_changed": changes,
            "active_cfg_sha256": hashlib.sha256(effective.encode("utf-8")).hexdigest() if effective else None,
            "active_cfg_source": "product" if effective is not None else None,
            "active_product": active_product,
            "manual_mode": packed_md.run_mode, "mode": mode}
