"""机器指纹：HKLM MachineGuid(64位注册表视图) + SMBIOS UUID → SHA256 clientId。

契约 = docs/LICENSE_DESIGN.md「Windows10/11机器与时间」：
- clientId = 64 位小写十六进制 SHA256，由规范化 MachineGuid 与 SMBIOS UUID
  组成；不绑定 MAC/USB 网卡/系统版本号/用户名/工作目录。
- SMBIOS UUID 用固定 PowerShell 命令 Get-CimInstance 读取：无插值、无 WMIC、
  子进程隐藏、有限超时。全零/全 F/非法 UUID 用固定占位串。
- CIM 执行异常或 MachineGuid 缺失显式失败（抛 MachineFingerprintError），
  绝不随机生成或静默改变指纹。
- 任何原始硬件 ID 不打印、不进日志。申请工具与客户端调用完全相同的
  machine_fingerprint()。

测试通过 mock _read_machine_guid/_read_smbios_uuid/subprocess 注入系统接口。
"""

import hashlib
import re
import subprocess

try:
    import winreg
except ImportError:  # 非 Windows 平台可导入，运行时显式失败
    winreg = None

# 64 位注册表视图读取 MachineGuid（防 32 位进程看到 SysWOW64 重定向副本）。
_REG_PATH = r"SOFTWARE\Microsoft\Cryptography"
_REG_NAME = "MachineGuid"

# 固定命令：无插值、无 WMIC。
_POWERSHELL_COMMAND = (
    "Get-CimInstance Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID"
)
_CIM_TIMEOUT_SECONDS = 15
_CREATE_NO_WINDOW = 0x08000000  # Windows 隐藏子进程窗口

_GUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_HEX32_RE = re.compile(r"^[0-9a-f]{32}$")

# 全零/全 F/非法 UUID 的固定占位串（固定 = 不随机、不静默变化）。
PLACEHOLDER_UUID = "00000000-0000-0000-0000-000000000000"


class MachineFingerprintError(Exception):
    """机器标识无法可靠取得：调用方必须显式失败（fail closed）。"""


def _read_machine_guid() -> str:
    """HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid（64 位视图）。"""
    if winreg is None:
        raise MachineFingerprintError("winreg 不可用，无法读取 MachineGuid")
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, _REG_PATH, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        ) as key:
            value, _ = winreg.QueryValueEx(key, _REG_NAME)
    except OSError as exc:
        raise MachineFingerprintError("MachineGuid 读取失败") from exc
    if not isinstance(value, str) or not value.strip():
        raise MachineFingerprintError("MachineGuid 缺失或为空")
    return value.strip()


def _read_smbios_uuid() -> str:
    """Win32_ComputerSystemProduct.UUID：固定命令 + 隐藏窗口 + 有限超时。"""
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL_COMMAND],
            capture_output=True,
            timeout=_CIM_TIMEOUT_SECONDS,
            creationflags=_CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MachineFingerprintError("SMBIOS UUID 读取失败（CIM 执行异常）") from exc
    if proc.returncode != 0:
        raise MachineFingerprintError("SMBIOS UUID 读取失败（PowerShell 非零退出）")
    return proc.stdout.decode("utf-8", "replace").strip()


def _normalize_machine_guid(value: str) -> str:
    """MachineGuid 规范化：去花括号、小写；非法格式显式失败（主键不容占位）。"""
    text = value.strip().strip("{}").lower()
    if not _GUID_RE.fullmatch(text):
        raise MachineFingerprintError("MachineGuid 格式非法")
    return text


def _normalize_smbios_uuid(value: str) -> str:
    """SMBIOS UUID 规范化；全零/全 F/非法 → 固定占位串。"""
    text = value.strip().strip("{}").lower()
    if _GUID_RE.fullmatch(text):
        digits = text.replace("-", "")
    elif _HEX32_RE.fullmatch(text):
        digits = text
    else:
        return PLACEHOLDER_UUID
    if set(digits) == {"0"} or set(digits) == {"f"}:
        return PLACEHOLDER_UUID
    if _HEX32_RE.fullmatch(text):  # 无连字符形式 → 规范化为带连字符
        text = (
            f"{text[0:8]}-{text[8:12]}-{text[12:16]}-{text[16:20]}-{text[20:32]}"
        )
    return text


def machine_fingerprint() -> str:
    """返回申请 clientId：SHA256(规范化MachineGuid + "\\n" + 规范化UUID)。"""
    machine_guid = _normalize_machine_guid(_read_machine_guid())
    smbios_uuid = _normalize_smbios_uuid(_read_smbios_uuid())
    material = f"{machine_guid}\n{smbios_uuid}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()
