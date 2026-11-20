"""Initialize mock-only local data; real machine configuration is never versioned."""
import json
import os
from pathlib import Path
import yaml
from .cfg import base_cfg, cfg_text


def backend_data_dir(backend_dir: str) -> str:
    explicit = os.environ.get("SLT_DATA_DIR")
    if explicit:
        return str(Path(explicit).resolve())
    local = Path(backend_dir).parent / "local_data"
    return str(local if (local / "config.yaml").is_file() else Path(backend_dir))


def mock_config(site: int = 1, mock_port: int = 40101, log_port: int = 63001) -> dict:
    return {
        "server": {"host": "127.0.0.1", "port": 8000},
        "records_dir": "records", "dut_log_port": log_port,
        "dut": {"heartbeat_interval_sec": 2, "heartbeat_timeout_sec": 12,
                "test_timeout_sec": 120, "cfg_resend_sec": 3, "log_drain_sec": 0.3},
        "cfg_defaults": {"LOG_TO_UART1": 1, "PatternTest": 1, "MemTester": 1,
                         "DvfsTest": 0, "AgingTime": 1, "Density": 16},
        "sites": [{"id": site, "name": "Mock", "slots": [
            {"slot": 1, "board": "A", "ip": "127.0.0.1", "port": mock_port}]}],
        "commboard": {"enabled": False, "boards": [
            {"site": site, "board": "A", "host": "127.0.0.1", "port": 501}]},
        "tempctrl": {"enabled": False, "host": "127.0.0.1"},
        "handler": {"enabled": False},
        "manual_debug": {"enabled": False, "board_host": "127.0.0.1",
                         "local_ip": "127.0.0.1", "log_dir": "manual_logs",
                         "cfg_file": "manual_debug.cfg", "scheme": "standard"},
    }


def init_mock_data(directory: str, **options) -> Path:
    dest = Path(directory).resolve()
    if (dest / "config.yaml").exists():
        raise FileExistsError(f"Refusing to overwrite local config: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    cfg = mock_config(**options)
    (dest / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    for name in ("strategies", "products", "records", "manual_logs"):
        (dest / name).mkdir(exist_ok=True)
    text = cfg_text(base_cfg(cfg))
    (dest / "manual_debug.cfg").write_text(text, encoding="utf-8")
    (dest / "strategies/standard.cfg").write_text(text, encoding="utf-8")
    return dest


_HANDLER_KEYS = ("enabled", "rx_port", "tx_host", "tx_port")


def load_handler_overrides(directory: str) -> dict:
    """handler_settings.json → 有效键字典（设置页保存的运行时配置覆盖层）。

    坏文件/缺键安全忽略：返回空 dict，config.yaml 的 handler 节继续生效。
    """
    path = Path(directory) / "handler_settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: data[k] for k in _HANDLER_KEYS if k in data}


def save_handler_overrides(directory: str, data: dict) -> None:
    """仅落 _HANDLER_KEYS 四键；失败静默（内存配置仍生效，下次启动回落 yaml）。"""
    path = Path(directory) / "handler_settings.json"
    payload = {k: data.get(k) for k in _HANDLER_KEYS}
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    except OSError:
        pass
