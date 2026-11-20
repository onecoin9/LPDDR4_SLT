"""Capture frozen startup errors before importing application code."""
from pathlib import Path
import os
import sys
import time
import traceback


def show_failure(message):
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'LPDDR4x SLT 上位机', 0x10)


def run_with_diagnostics(start, directory, *, show_dialog=True):
    destinations = [Path(directory)]
    local = os.environ.get('LOCALAPPDATA')
    if local:
        destinations.append(Path(local) / 'LPDDR4x_SCADA')
    log = None
    path = None
    for base in destinations:
        try:
            folder = base / 'startup_logs'
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"startup_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}.log"
            log = path.open('w', encoding='utf-8', buffering=1)
            break
        except OSError:
            path = None
    before = sys.stdout, sys.stderr
    if log is not None and getattr(sys, 'frozen', False):
        sys.stdout = sys.stderr = log
    try:
        return start()
    except Exception as error:
        detail = traceback.format_exc()
        if log is not None:
            log.write(detail)
            log.flush()
            detail = path.read_text(encoding='utf-8', errors='replace')
        else:
            print(detail, file=sys.stderr)
        if '10048' in detail or 'Address already in use' in detail:
            message = '通讯端口已被占用。请关闭重复运行的上位机或源码后端，再重新打开。'
        elif isinstance(error, FileNotFoundError) and 'config.yaml' in str(error):
            message = '找不到运行配置。请保留完整运行文件夹，并检查 config.yaml。'
        else:
            message = '软件启动失败。请查看启动日志，或将日志交给维护人员。'
        if path is not None:
            message += f'\n\n启动日志：{path}'
        if show_dialog:
            show_failure(message)
        return 1
    finally:
        sys.stdout, sys.stderr = before
        if log is not None:
            log.close()
