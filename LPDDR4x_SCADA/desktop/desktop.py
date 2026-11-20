r"""LPDDR4x SLT 上位机 —— 桌面版（统一界面：现有 React 前端 + FastAPI 后端内嵌）。

一个进程 = uvicorn 后端（本机回环，随机空闲端口）+ pywebview 窗口加载前端。
前端产物不改一行（agent.md §3 交付形态决策的落地）；与 DUT 的通讯由后端
config.yaml 决定（sites.mode=serial → 串口直连真实 DUT；mock → 联调）。

运行（开发）：cd desktop && python desktop.py
打包：build_desktop.bat → dist\LPDDR4x_SCADA_Desktop\LPDDR4x上位机.exe
"""

import os
import argparse
import socket
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):        # PyInstaller：资源随 exe 目录
    HERE = os.path.dirname(sys.executable)
ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

from launch_paths import configure_paths
from startup_diagnostics import run_with_diagnostics

APP_TITLE = "LPDDR4x SLT 上位机"
VERSION = "1.0.0"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_backend(server, thread, timeout=15.0):
    deadline = time.monotonic() + timeout
    while not server.started:
        if not thread.is_alive():
            raise RuntimeError('后端启动失败，请查看启动日志')
        if time.monotonic() >= deadline:
            raise RuntimeError('后端启动超时，请查看启动日志')
        time.sleep(0.1)


def start(data_dir=None) -> int:
    # Resolve data and capture import/config errors before creating the window.
    configure_paths(HERE, BACKEND, data_dir)
    import uvicorn
    import webview
    from app.main import app as backend_app

    port = free_port()
    config = uvicorn.Config(backend_app, host="127.0.0.1", port=port,
                            log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="uvicorn")
    thread.start()
    try:
        wait_for_backend(server, thread)
        # 授权页"导出申请"是 <a download>；pywebview 默认 ALLOW_DOWNLOADS=False
        # 会把 WebView2 下载静默取消（表现为点击无反应，2026-10-28 现场发现）。
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.create_window(
            f"{APP_TITLE} v{VERSION}", f"http://127.0.0.1:{port}",
            width=1440, height=900, min_size=(1100, 700))
        webview.start()
    finally:
        server.should_exit = True
        thread.join(timeout=3)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir")
    parser.add_argument("--no-startup-dialog", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args()
    directory = options.data_dir or os.environ.get("SLT_DATA_DIR") or HERE
    return run_with_diagnostics(lambda: start(options.data_dir), directory,
                                show_dialog=not options.no_startup_dialog)


if __name__ == "__main__":
    sys.exit(main())
