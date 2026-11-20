"""手动版调试（debug/manual-4dut 分支）：1 块原版通讯板 + N 块测试主板。

硬件形态（2026-09-17 用户定案）：
  - 通讯板是**未修改的原版固件**（TXP03 / GD32F407），不可改 → 控制面用既有
    协议；DUT 日志走既有 logchannel（[DUTx] 前缀，UDP 63001）。
  - DUT i（1..N）= 板上线号 dut_lines[i-1]（默认 0..3，PWR_EN 组）
    + 透传通道 i（板侧端口 2000+i，对应 SITE 1 / slot i）。

电源控制 = **直控寄存器**（DriverSwitch.c sSwitchReg，2026-09-17 真机验证）：
  - 单路：FC06 写 0x83/0x87/0x8B/0x8F…（线号 → 寄存器映射见 commboard.PWR_LINE_REG）
  - 整组：FC06 写 0xA2 位掩码（bit i = 线 i）
  写立即驱动 GPIO 并**硬件锁存**——无防重放序列号、无定时器、无 65s 回翻。
  （cmd7 的三连坑：serial 恒 1 被静默丢弃 / durationMsec 0xFFFF≈65.5s 回翻 /
  duration=0 语义反直觉——已全部绕开；cmd7 仅保留给错峰按键等定时场景。）
  注意：寄存器读回走固件缓存（vSwitchSetGpioStatus 不更新缓存）→ 读回不可信，
  电源状态由本类记忆（后端重启后归 0，以板为准时点一次开关即可）。

本模块只做电源开关 + 状态跟踪 + 设置持久化，不 import fastapi（本地单测可直接跑）；
main.py 做薄路由包装，阻塞 socket 调用一律 asyncio.to_thread。
「完整运行」的 READY→cfg→ACK 编排见 manualrun.py（asyncio）。
"""
from __future__ import annotations

import json
import os
import re
import socket
import time
import tempfile
from typing import Dict, List, Optional
import yaml

from . import commboard
from .cfg import build_cfg
from .strategy import list_strategies, load_strategy_text

# 运行模式：power_only=只开机（上电即完）/ full_run=完整运行（READY→cfg→ACK）
RUN_MODES = ("power_only", "full_run")

# DUT 路数上限：界面「+」卡片逐路添加，默认 4 路（配置决定）、最多 8 路
# （电源线号池 0..7；透传通道池 1..12）
MAX_DUTS = 8


class ManualDebugError(Exception):
    """status: 503=未启用 / 404=无此 DUT / 400=设置非法 / 502=通讯板通讯失败"""

    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


def _valid_ip(ip: str, label: str) -> str:
    try:
        socket.inet_aton(ip)
    except OSError:
        raise ManualDebugError(400, f"{label}非法: {ip!r}")
    if ip.count(".") != 3:
        raise ManualDebugError(400, f"{label}非法: {ip!r}")
    return ip


def _yaml_scalar(v) -> str:
    """标量/简单列表 → YAML 行内文本（列表形如 [4, 5, 6, 7, 0]，与现有
    config.yaml 风格一致；含 : # 等字符的字符串加引号）。"""
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_yaml_scalar(x) for x in v) + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "":
        return '""'
    if s != s.strip() or re.search(r'[:#\[\]{},&*!|>\'"%@`]', s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def update_manual_debug_yaml(path: str, values: Dict[str, object]) -> None:
    """文本级更新 config.yaml 的 manual_debug: 节（保留注释与其它节不动）。

    已存在的键原位替换值（保留行尾注释），缺失的键追加到节尾。
    values 接受标量（str/int/float/bool）与简单列表（[4, 5, 6, 7, 0] 形态）。
    """
    with open(path, encoding="utf-8") as f:
        original = f.read()
    try:
        tree = yaml.compose(original)
    except yaml.YAMLError as error:
        raise ManualDebugError(500, f"config.yaml 格式错误，未修改文件：{error}") from error
    lines = original.splitlines()
    start = None
    for i, l in enumerate(lines):
        if re.match(r"^manual_debug\s*:", l):
            start = i
            break
    if start is None:
        raise ManualDebugError(500, "config.yaml 缺少 manual_debug 节")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        l = lines[i]
        if l.strip() and not l.startswith((" ", "\t", "#")):
            end = i
            break
    if not isinstance(tree, yaml.MappingNode):
        raise ManualDebugError(500, "config.yaml 顶层须为映射，未修改文件")
    sections = [node for key, node in tree.value if key.value == "manual_debug"]
    if len(sections) != 1 or not isinstance(sections[0], yaml.MappingNode):
        raise ManualDebugError(500, "manual_debug 须为单一映射，未修改文件")
    entries = sections[0].value
    if len({key.value for key, _ in entries}) != len(entries):
        raise ManualDebugError(500, "manual_debug 存在重复键，未修改文件")
    remaining = dict(values)
    changes = []
    for position, (key, node) in enumerate(entries):
        if key.value not in remaining:
            continue
        i = key.start_mark.line
        stop = entries[position + 1][0].start_mark.line if position + 1 < len(entries) else end
        m = re.match(r"^(\s+)([A-Za-z_][\w]*)\s*:(.*)$", lines[i])
        if not m:
            raise ManualDebugError(500, "manual_debug 仅支持普通键，未修改文件")
        # Node marks distinguish a real trailing comment from # inside a quoted
        # value. Replace the complete entry, including any block-list elements.
        tail = lines[i][node.end_mark.column:] if node.end_mark.line == i else m.group(3)
        cm = re.search(r"\s+#", tail)
        comment = tail[cm.start():] if cm else ""
        kept = [line for line in lines[i + 1:stop]
                if not line.strip() or line.lstrip().startswith("#")]
        replacement = [f"{m.group(1)}{key.value}: {_yaml_scalar(remaining.pop(key.value))}{comment}", *kept]
        changes.append((i, stop, replacement))
    if remaining:
        block = [f"  {k}: {_yaml_scalar(v)}" for k, v in remaining.items()]
        changes.append((end, end, block))
    for begin, stop, replacement in sorted(changes, reverse=True):
        lines[begin:stop] = replacement
    text = "\n".join(lines) + "\n"
    try:
        parsed = yaml.safe_load(text)
        if any(parsed["manual_debug"].get(k) != (list(v) if isinstance(v, tuple) else v)
               for k, v in values.items()):
            raise ValueError("保存后的值与请求不一致")
    except (yaml.YAMLError, ValueError, TypeError, KeyError) as error:
        raise ManualDebugError(500, f"配置校验失败，未修改文件：{error}") from error
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=os.path.dirname(os.path.abspath(path)),
                                         prefix="config_", suffix=".tmp", delete=False) as f:
            temporary = f.name
            f.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


class ManualDebug:
    """手动调试控制面。配置见 config.yaml 的 manual_debug: 节。"""

    def __init__(self, cfg: dict, data_dir: str = "."):
        self._cfg = cfg
        self.data_dir = data_dir
        md = cfg.get("manual_debug") or {}
        self.enabled = bool(md.get("enabled"))
        self.board_host = str(md.get("board_host", "192.168.50.100"))
        self.mb_port = int(md.get("mb_port", 501))
        lines = md.get("dut_lines")
        n = int(md.get("dut_count", 4))
        self.dut_lines: List[int] = ([int(x) for x in lines]
                                     if lines else list(range(n)))
        # ---- 设置区（/manual「设置」面板，运行时可改并持久化） ----
        self.local_ip = str(md.get("local_ip", "192.168.50.10"))
        self.log_dir = str(md.get("log_dir", "") or "")
        self.cfg_file = str(md.get("cfg_file", "manual_debug.cfg"))
        # [测试方案 2026-09-24 用户定案] 方案 = strategies/<名>.cfg 一份文本；
        # config.yaml 的 scheme 指定当前用哪套，不填 = 维持 cfg_file 行为
        self.scheme = str(md.get("scheme", "") or "").strip()
        self.run_mode = str(md.get("run_mode", "power_only"))
        if self.run_mode not in RUN_MODES:
            self.run_mode = "power_only"
        self.ready_timeout_sec = int(md.get("ready_timeout_sec", 180))
        self.passthrough_base = int(md.get("passthrough_base", 2001))
        # 透传通道表（2026-09-18 现场实证：DUT 接在通讯板 CH5-8，不是 CH1-4；
        # UDP 端口 = 2000 + 通道号。缺省回退 passthrough_base + dut - 1）
        chans = md.get("dut_channels")
        self.dut_channels: List[int] = ([int(x) for x in chans]
                                        if chans else
                                        list(range(1, len(self.dut_lines) + 1)))
        # 按键线表（0x13 开机键预约用；MCU_PWR 组线号需现场实证，空=只记录不执行）
        keys = md.get("dut_key_lines")
        self.dut_key_lines: List[int] = [int(x) for x in keys] if keys else []
        # 运行总超时（秒）：0=自适应（AgingTime×60+300 启动+900 轮末收尾）；>0 用户值优先
        self.test_timeout_sec = int(md.get("test_timeout_sec", 0))
        # 判 FAIL 自动下电（2026-10-10）：true=终态 fail/timeout 时 runner
        # 自动断开该路 PWR_EN；false=保持上电人工处置
        self.power_off_on_fail = bool(md.get("power_off_on_fail", True))
        # PASS 也自动下电（2026-10-10 用户拍板）：true=终态 pass 收尾后
        # 自动断电换料；false=PASS 保持上电人工处置
        self.power_off_on_pass = bool(md.get("power_off_on_pass", True))
        # 会话覆盖（2026-10-10 用户指令「配置存 json，下次打开可改变」）：
        # config.yaml 是基础配置来源，session_settings.json 是运行期保存的
        # 覆盖层——启动时读回，逐键校验后生效（坏文件/非法键安全忽略）
        self._load_session_overrides()
        # 电源状态跟踪：寄存器读回不可信（见模块 docstring），记忆最后成功下发值
        self._power: Dict[int, bool] = {i + 1: False
                                        for i in range(len(self.dut_lines))}

    # ---------------- 会话覆盖（session_settings.json 加载/保存） ----------------

    def _session_path(self) -> str:
        return os.path.join(self.data_dir, "session_settings.json")

    def _load_session_overrides(self) -> None:
        """启动时加载 session_settings.json 覆盖内存配置。

        文件缺失/坏 json/非 dict → 整体忽略；设置区标量键逐键校验（口径与
        apply_settings 一致），非法键值只跳过该键；dut_lines/dut_channels
        校验通过才**同时**采用（防错位配对），dut_count 忽略（以 dut_lines
        长度为准）。"""
        try:
            with open(self._session_path(), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        if "board_host" in data:
            try:
                self.board_host = _valid_ip(
                    str(data["board_host"]).strip(), "通讯板 IP")
            except ManualDebugError:
                pass
        if "local_ip" in data:
            try:
                self.local_ip = _valid_ip(
                    str(data["local_ip"]).strip(), "本机日志接收 IP")
            except ManualDebugError:
                pass
        if "log_dir" in data:
            self.log_dir = str(data["log_dir"] or "")
        if "cfg_file" in data and str(data["cfg_file"]).strip():
            self.cfg_file = str(data["cfg_file"]).strip()
        if "run_mode" in data and str(data["run_mode"]) in RUN_MODES:
            self.run_mode = str(data["run_mode"])
        try:
            v = int(data["ready_timeout_sec"])
            if 5 <= v <= 3600:
                self.ready_timeout_sec = v
        except (KeyError, TypeError, ValueError):
            pass
        try:
            v = int(data["test_timeout_sec"])
            if 0 <= v <= 86400:
                self.test_timeout_sec = v
        except (KeyError, TypeError, ValueError):
            pass
        if "power_off_on_fail" in data and isinstance(
                data["power_off_on_fail"], bool):
            self.power_off_on_fail = data["power_off_on_fail"]
        if "power_off_on_pass" in data and isinstance(
                data["power_off_on_pass"], bool):
            self.power_off_on_pass = data["power_off_on_pass"]
        # DUT 表：两张表校验通过才同时采用（任何一张非法 → 整组弃用）
        lines, chans = data.get("dut_lines"), data.get("dut_channels")
        if not (isinstance(lines, list) and isinstance(chans, list)):
            return
        try:
            lines = [int(x) for x in lines]
            chans = [int(x) for x in chans]
        except (TypeError, ValueError):
            return
        if (1 <= len(lines) <= MAX_DUTS and len(lines) == len(chans)
                and len(set(lines)) == len(lines)
                and all(0 <= l <= 7 for l in lines)
                and len(set(chans)) == len(chans)
                and all(1 <= c <= 12 for c in chans)):
            self.dut_lines = lines
            self.dut_channels = chans

    def _persist_session(self, updates: Dict[str, object]) -> None:
        """session_settings.json 读改写（运行期覆盖层；启动时由
        _load_session_overrides 读回）。部分保存只更新对应键，不清空其它键。"""
        sf = self._session_path()
        existing = {}
        if os.path.isfile(sf):
            try:
                with open(sf, encoding="utf-8") as f:
                    existing = json.load(f)
            except (ValueError, OSError):
                pass
        if not isinstance(existing, dict):
            existing = {}
        existing.update(updates)
        with open(sf, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def dut_port(self, dut: int) -> int:
        """DUT 号 → 通讯板透传 UDP 端口。"""
        if 1 <= dut <= len(self.dut_channels):
            return 2000 + self.dut_channels[dut - 1]
        return self.passthrough_base + dut - 1

    def ch(self, dut: int) -> int:
        """DUT 序号 → 真实通道号（2026-09-23 用户指令「界面 DUT 改真实值」）。

        通道号是板子的本源身份：63001 日志前缀 [DUTx] 的 x、界面 DUT 卡片/
        日志页签、落盘文件名、完整运行状态展示统一用它（现场 [5,6,7,8] →
        DUT05-08）。越界/未配置回退序号本身（单测夹具与 mock 兼容）。
        """
        if 1 <= dut <= len(self.dut_channels):
            return self.dut_channels[dut - 1]
        return dut

    def _require(self) -> None:
        if not self.enabled:
            raise ManualDebugError(
                503, "手动调试未启用（config.yaml manual_debug.enabled）")

    def add_dut(self, cfg_path: str) -> dict:
        """界面「+」卡片新增一路 DUT（路数由 dut_lines 决定，最多 MAX_DUTS=8）。

        新电源线号 = 0..7 中最小未占用值；新透传通道 = 1..12 中最小未占用值
        （如现有 [5,6,7,8] → 新通道取 1，透传端口 2001）。内存生效并持久化
        dut_count/dut_lines/dut_channels 回 config.yaml；完整运行的透传端口
        绑定由 main.py 路由随后调 runner.sync_duts() 同步（添加后无需重启）。
        返回最新 info()。"""
        self._require()
        if len(self.dut_lines) >= MAX_DUTS:
            raise ManualDebugError(
                400, f"已达最大 {MAX_DUTS} 路 DUT，无法继续添加")
        line = next(l for l in range(MAX_DUTS) if l not in self.dut_lines)
        chan = next(c for c in range(1, 13) if c not in self.dut_channels)
        self.dut_lines.append(line)
        self.dut_channels.append(chan)
        self._power[len(self.dut_lines)] = False
        keys = {"dut_count": len(self.dut_lines),
                "dut_lines": list(self.dut_lines),
                "dut_channels": list(self.dut_channels)}
        update_manual_debug_yaml(cfg_path, keys)
        self._persist_session(keys)      # 双写会话覆盖层（重启后仍生效）
        return self.info()

    def remove_dut(self, dut: int, cfg_path: str, is_active=None) -> dict:
        """界面卡片「−」移除一路 DUT。dut = dut_lines 列表序号（身份标识，
        非显示下标）。

        安全约束：序号不存在 → 400；该路电源开着 → 400（先下电，防止线号
        仍供电却失去控制入口）；is_active(dut) 为真（完整运行活动态：非
        idle/终态）→ 400。is_active 由 main.py 注入 runner 状态查询，本类
        不依赖 manualrun（单测可传桩/缺省不查）。

        移除 = dut_lines/dut_channels/_power 按位置成对剔除，其余 DUT 的
        线号↔通道↔端口配对完全不变；写回 config.yaml 三键。注意：列表收缩
        后其后的 DUT 序号位移——允许的内部行为（runner 侧 drop_dut 按位置
        平移状态/端口绑定）。返回最新 info()。"""
        self._require()
        if not 1 <= dut <= len(self.dut_lines):
            raise ManualDebugError(
                400, f"无此 DUT: {dut}（共 {len(self.dut_lines)} 路）")
        if self._power.get(dut):
            raise ManualDebugError(
                400, f"DUT{dut} 电源仍开着，请先下电再移除")
        if is_active is not None and is_active(dut):
            raise ManualDebugError(
                400, f"DUT{dut} 完整运行进行中，请等待结束再移除")
        del self.dut_lines[dut - 1]
        del self.dut_channels[dut - 1]
        old = self._power
        self._power = {i: old[i] for i in range(1, dut)}
        for i in range(dut, len(self.dut_lines) + 1):
            self._power[i] = old[i + 1]
        keys = {"dut_count": len(self.dut_lines),
                "dut_lines": list(self.dut_lines),
                "dut_channels": list(self.dut_channels)}
        update_manual_debug_yaml(cfg_path, keys)
        self._persist_session(keys)      # 双写会话覆盖层（重启后仍生效）
        return self.info()

    def _client(self) -> commboard.CommBoard:
        return commboard.CommBoard(self.board_host, mb_port=self.mb_port)

    def info(self) -> dict:
        duts = [{"dut": i + 1, "line": ln, "powerOn": self._power[i + 1],
                 "channel": self.dut_channels[i],
                 "port": self.dut_port(i + 1)}
                for i, ln in enumerate(self.dut_lines)]
        # 显示顺序统一按通道号升序（2026-10-10 用户指令：add 取最小未占用通道
        # 后追加在列表末尾，不排序界面会显示 05 06 07 08 01）。排序只影响返回
        # 顺序——dut 序号 = dut_lines 列表位置，是电源/端口 API 的身份标识，
        # 前端一律用 d.dut 调接口，与显示下标无关
        duts.sort(key=lambda d: d["channel"])
        return {
            "enabled": self.enabled,
            "boardHost": self.board_host,
            "mbPort": self.mb_port,
            "runMode": self.run_mode,
            "duts": duts,
        }

    # ---------------- 设置区（IP / 日志路径 / cfg / 运行模式） ----------------

    def _abs(self, p: str) -> str:
        return p if os.path.isabs(p) else os.path.join(self.data_dir, p)

    def log_dir_abs(self) -> str:
        """日志落盘目录（绝对路径；空 = 不落盘）。"""
        return self._abs(self.log_dir) if self.log_dir else ""

    def cfg_file_abs(self) -> str:
        return self._abs(self.cfg_file)

    def get_cfg_text(self) -> str:
        """Application runs use the active shared product, without file fallback.

        Standalone callers without a provider retain scheme/file/baseline loading.
        """
        shared = self.get_product_plan()
        if shared is not None:
            return shared['cfgText']
        if self.scheme:
            text = load_strategy_text(self.data_dir, self.scheme)
            if text is not None:
                return text
        try:
            with open(self.cfg_file_abs(), encoding="utf-8") as f:
                text = f.read()
            if text.strip():
                return text
        except OSError:
            pass
        return build_cfg(self._cfg)

    def get_product_plan(self):
        """The application injects the same product compiler used by production.

        No fallback is allowed when that compiler rejects the current product.
        Standalone diagnostic users without a provider retain file loading.
        """
        provider = getattr(self, 'product_plan_provider', None)
        return provider() if provider is not None else None

    def save_cfg_file(self, path: str, text: str) -> str:
        """Save the shared product's compiled CFG to the selected user file."""
        if not isinstance(path, str) or not path.strip() or not path.lower().endswith('.cfg'):
            raise ManualDebugError(400, '请选择 CFG 文件 / Select a CFG file')
        chosen = os.path.abspath(self._abs(path.strip()))
        if not os.path.isdir(os.path.dirname(chosen)) or os.path.isdir(chosen):
            raise ManualDebugError(400, '文件目录不存在，请重新选择 / Choose an existing directory')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                             dir=os.path.dirname(chosen), suffix='.tmp', delete=False) as output:
                temporary = output.name
                output.write(text)
            os.replace(temporary, chosen)
            temporary = None
            self._persist_session({'cfg_file': chosen})
            self.cfg_file = chosen
        except OSError as error:
            raise ManualDebugError(400, 'CFG 文件无法保存，请检查路径或文件占用 / Check the CFG path and file access') from error
        finally:
            if temporary is not None:
                os.unlink(temporary)
        return chosen

    def list_schemes(self) -> List[str]:
        """可用方案名列表（strategies/ 目录内 *.cfg）。"""
        return list_strategies(self.data_dir)

    def active_scheme(self) -> Dict[str, object]:
        """当前方案状态（供代码/诊断查看）：名字 + 是否实际生效。"""
        names = self.list_schemes()
        loaded = bool(self.scheme and self.scheme in names
                      and load_strategy_text(self.data_dir, self.scheme))
        return {"scheme": self.scheme, "available": names, "loaded": loaded}

    def settings(self) -> dict:
        # logDir 始终返回原始配置值(不因目录不存在而变空 → 防静默清空链);
        # latestRunDir 为展示层补全(最新时间戳子目录),不参与回传
        latest = ""
        if self.log_dir:
            d = self._abs(self.log_dir)
            if os.path.isdir(d):
                ts = sorted(f for f in os.listdir(d)
                            if os.path.isdir(os.path.join(d, f)))
                latest = os.path.join(d, ts[-1]) if ts else d
        shared = self.get_product_plan()
        cfg_info = ({'cfgSource': 'product', 'cfgProduct': shared['product'],
                     'cfgSha256': shared['cfgSha256'], 'cfgContent': shared['cfgText'],
                     'settingsRevision': shared['settingsRevision']}
                    if shared is not None else {'cfgSource': 'file', 'cfgContent': self.get_cfg_text()})
        return {
            "boardHost": self.board_host,
            "localIp": self.local_ip,
            "logDir": self.log_dir,
            "latestRunDir": latest,
            "cfgFile": self._abs(self.cfg_file),
            # [测试方案 2026-09-24] 当前方案名 + 可用方案列表 + 是否实际加载
            **self.active_scheme(),
            "settingsFile": os.path.join(self.data_dir, "session_settings.json"),
            **cfg_info,
            "runMode": self.run_mode,
            "readyTimeoutSec": self.ready_timeout_sec,
            "dutChannels": self.dut_channels,
            "testTimeoutSec": self.test_timeout_sec,
            "powerOffOnFail": self.power_off_on_fail,
            "powerOffOnPass": self.power_off_on_pass,
        }

    def browse_dir(self, path: str = "", show_files: str = "") -> dict:
        """目录浏览(设置区路径选择器):path 空/无效 → 驱动器列表;有效 → 子目录。
        show_files='cfg' 时同时列出 .cfg 文件(供 cfg 文件路径选择)。"""
        import string
        import glob as _glob
        if path and not os.path.isabs(path):
            path = os.path.join(self.data_dir, path)
        if not path or not os.path.isdir(path):
            drives = [f"{d}:\\" for d in string.ascii_uppercase
                      if os.path.exists(f"{d}:\\")]
            return {"path": "", "parent": "", "dirs": [], "files": [], "drives": drives}
        norm = os.path.normpath(path)
        parent = os.path.dirname(norm) or ""
        try:
            dirs = sorted(d for d in os.listdir(norm)
                          if os.path.isdir(os.path.join(norm, d)))
        except OSError:
            dirs = []
        files = []
        if show_files in ("cfg", "json"):
            ext = "." + show_files
            try:
                files = sorted(f for f in os.listdir(norm) if f.lower().endswith(ext))
            except OSError:
                pass
        return {"path": norm, "parent": parent, "dirs": dirs[:500],
                "files": files, "drives": []}

    def apply_settings(self, updates: dict, cfg_path: str) -> dict:
        """校验并应用设置：内存生效 + 持久化（config.yaml 文本级更新 /
        cfg 内容写 cfg_file）。返回最新 settings()。"""
        self._require()
        # 别名映射（2026-10-10）：「读取设置」导入 session json 时键是
        # snake_case（dut_lines/board_host/…），统一映射为对外 camelCase；
        # dut_count 由 dutLines 推导，导入文件里出现时静默跳过不报错
        aliases = {"board_host": "boardHost", "local_ip": "localIp",
                   "log_dir": "logDir", "cfg_file": "cfgFile",
                   "run_mode": "runMode", "ready_timeout_sec": "readyTimeoutSec",
                   "test_timeout_sec": "testTimeoutSec",
                   "power_off_on_fail": "powerOffOnFail",
                   "power_off_on_pass": "powerOffOnPass",
                   "dut_channels": "dutChannels", "dut_lines": "dutLines"}
        updates = {aliases.get(k, k): v for k, v in updates.items()
                   if k not in ("dut_count", "dutCount")}
        if getattr(self, 'product_plan_provider', None) is not None and set(updates) & {'cfgFile', 'cfgContent'}:
            raise ManualDebugError(400, 'CFG 由产品设置统一管理，请使用“应用到产品设置” / Import CFG through product settings')
        allowed = {"boardHost", "localIp", "logDir", "cfgContent", "cfgFile",
                   "dutChannels", "dutLines", "testTimeoutSec",
                   "powerOffOnFail", "powerOffOnPass",
                   "runMode", "readyTimeoutSec"}
        unknown = sorted(set(updates) - allowed)
        if unknown:
            raise ManualDebugError(400, f"未知设置项: {unknown}")
        yaml_updates: Dict[str, object] = {}
        if "boardHost" in updates:
            v = _valid_ip(str(updates["boardHost"]).strip(), "通讯板 IP")
            self.board_host = v
            yaml_updates["board_host"] = v
        if "localIp" in updates:
            v = _valid_ip(str(updates["localIp"]).strip(), "本机日志接收 IP")
            self.local_ip = v
            yaml_updates["local_ip"] = v
        if "logDir" in updates:
            v = str(updates["logDir"]).strip()
            # 显示补全到具体文件（.../<ts>/dutN.log）；保存取根目录
            # （截掉时间戳文件夹和文件名两层）
            if v:
                parts = v.replace("/", "\\").rstrip("\\").split("\\")
                # 从后往前去掉文件名(.log)和时间戳文件夹(纯数字+下划线)
                while len(parts) > 1:
                    last = parts[-1]
                    if last.endswith(".log"):
                        parts.pop()
                    elif parts[-1] and all(c.isdigit() or c == "_" for c in parts[-1]):
                        parts.pop()
                    else:
                        break
                v = "\\".join(parts)
            self.log_dir = v
            yaml_updates["log_dir"] = v
        if "cfgFile" in updates:
            # cfg 文件路径(相对 data_dir 或绝对);保存到 session
            v = str(updates["cfgFile"]).strip()
            self.cfg_file = v
            yaml_updates["cfg_file"] = v
        if "runMode" in updates:
            v = str(updates["runMode"]).strip()
            if v not in RUN_MODES:
                raise ManualDebugError(
                    400, f"运行模式非法: {v!r}（可选 {list(RUN_MODES)}）")
            self.run_mode = v
            yaml_updates["run_mode"] = v
        if "readyTimeoutSec" in updates:
            try:
                v = int(updates["readyTimeoutSec"])
            except (TypeError, ValueError):
                raise ManualDebugError(
                    400, f"READY 超时非法: {updates['readyTimeoutSec']!r}")
            if not 5 <= v <= 3600:
                raise ManualDebugError(400, f"READY 超时须在 5..3600 秒: {v}")
            self.ready_timeout_sec = v
            yaml_updates["ready_timeout_sec"] = v
        if "testTimeoutSec" in updates:
            # 运行总超时：>0 用用户值（秒）；0 = 自适应（AgingTime×60+1200）
            try:
                v = int(updates["testTimeoutSec"])
            except (TypeError, ValueError):
                raise ManualDebugError(
                    400, f"测试超时非法: {updates['testTimeoutSec']!r}")
            if not 0 <= v <= 86400:
                raise ManualDebugError(400, f"测试超时须在 0..86400 秒(0=自适应): {v}")
            self.test_timeout_sec = v
            yaml_updates["test_timeout_sec"] = v
        if "powerOffOnFail" in updates:
            # 判 FAIL 自动下电开关（2026-10-10）
            raw = updates["powerOffOnFail"]
            if not isinstance(raw, bool):
                raise ManualDebugError(
                    400, f"powerOffOnFail 须为布尔值: {raw!r}")
            self.power_off_on_fail = raw
            yaml_updates["power_off_on_fail"] = raw
        if "powerOffOnPass" in updates:
            # PASS 自动下电开关（2026-10-10 用户拍板 PASS 也断电）
            raw = updates["powerOffOnPass"]
            if not isinstance(raw, bool):
                raise ManualDebugError(
                    400, f"powerOffOnPass 须为布尔值: {raw!r}")
            self.power_off_on_pass = raw
            yaml_updates["power_off_on_pass"] = raw
        if "dutLines" in updates:
            # 线表整体替换（「读取设置」导入恢复 DUT 配置，2026-10-10）：
            # 任何一路电源开着 → 400（防改线表后线号仍供电却失去控制入口）；
            # 通道表同给时由下方 dutChannels 分支校验长度一致并替换，
            # 未同给则截齐/按最小未占用补全到新长度。_power 重建（全 False），
            # runner 的状态机/端口由 main.py 路由随后 resync 全量对齐
            raw = updates["dutLines"]
            try:
                v = [int(x) for x in raw] if isinstance(raw, list) else None
            except (TypeError, ValueError):
                v = None
            if (v is None or not 1 <= len(v) <= MAX_DUTS
                    or len(set(v)) != len(v)
                    or any(not 0 <= l <= 7 for l in v)):
                raise ManualDebugError(
                    400, f"dutLines 须为 1..{MAX_DUTS} 个 0..7 不重复线号的列表")
            if any(self._power.values()):
                raise ManualDebugError(
                    400, "有 DUT 电源开着，请先全部下电再改 DUT 线表")
            self.dut_lines = v
            if "dutChannels" not in updates:
                chans = self.dut_channels[:len(v)]
                c = 1
                while len(chans) < len(v):
                    if c not in chans:
                        chans.append(c)
                    c += 1
                self.dut_channels = chans
                yaml_updates["dut_channels"] = list(chans)
            self._power = {i + 1: False for i in range(len(v))}
            yaml_updates["dut_lines"] = v
            yaml_updates["dut_count"] = len(v)
        if "dutChannels" in updates:
            # 通道表按 DUT 顺序给出（灯序从左往右 = [5,6,7,8]，反着数 = [8,7,6,5]）；
            # 改后需重启后端让完整运行重新绑定透传端口
            raw = updates["dutChannels"]
            if not isinstance(raw, list) or len(raw) != len(self.dut_lines):
                raise ManualDebugError(
                    400, f"dutChannels 须为 {len(self.dut_lines)} 个通道号的列表")
            try:
                v = [int(x) for x in raw]
            except (TypeError, ValueError):
                raise ManualDebugError(400, f"dutChannels 非法: {raw!r}")
            if any(not 1 <= c <= 8 for c in v):
                raise ManualDebugError(400, "通道号须在 1..8（通讯板共 8 通道）")
            self.dut_channels = v
            yaml_updates["dut_channels"] = v
        if "cfgContent" in updates:
            with open(self.cfg_file_abs(), "w", encoding="utf-8",
                      newline="\n") as f:
                f.write(str(updates["cfgContent"]))
        # 会话配置（2026-09-21）：保存到 session_settings.json，不写 config.yaml。
        # read-modify-write:部分保存(如切运行模式)只更新对应键,不清空其他键。
        if yaml_updates:
            self._persist_session(yaml_updates)
        return self.settings()

    def sync_server_ip(self, timeout: float = 2.0) -> dict:
        """绑定本机 IP 发定向广播，把板子 server_ip 同步为本机地址。

        现场实证坑（2026-09-17）：板子的 server_ip（日志/透传回包目标）学自
        "最后收到的广播包源 IP"；Windows 多网卡下直接发 255.255.255.255 会从
        主网卡发出，50 网段的板子收不到。必须 bind(local_ip) 后向网段定向
        广播地址（x.y.z.255:60000）发，板子 ACK 即同步成功。
        """
        self._require()
        bcast = self.local_ip.rsplit(".", 1)[0] + ".255"
        try:
            found = commboard.discover(timeout=timeout,
                                       broadcast_addrs=[bcast],
                                       bind_ip=self.local_ip)
        except OSError as e:
            raise ManualDebugError(
                502, f"绑定 {self.local_ip} 发广播失败（网卡/IP 不对？）：{e}")
        return {"ok": True, "broadcast": bcast, "found": found,
                "boardSeen": any(b.get("addr") == self.board_host
                                 for b in found)}

    def board_state(self) -> dict:
        """读 0xF001 动作状态（兼作 Modbus 链路心跳：能读到 = 板在线）。"""
        self._require()
        try:
            st = self._client().action_state()
        except commboard.ModbusError as e:
            raise ManualDebugError(
                502, f"通讯板 {self.board_host}:{self.mb_port} 无应答：{e}")
        return {"ok": True, "state": st}

    def set_power(self, dut: int, on: bool) -> dict:
        """单路电源开关：FC06 写 PWR_EN 单路寄存器，立即生效、硬件锁存。"""
        self._require()
        if not 1 <= dut <= len(self.dut_lines):
            raise ManualDebugError(
                404, f"无此 DUT: {dut}（共 {len(self.dut_lines)} 路）")
        line = self.dut_lines[dut - 1]
        try:
            self._client().set_power_line(line, on)
        except commboard.ModbusError as e:
            raise ManualDebugError(
                502, f"通讯板 {self.board_host}:{self.mb_port} 无应答：{e}")
        self._power[dut] = on
        return {"ok": True, "dut": dut, "line": line, "powerOn": on}

    def set_power_all(self, on: bool) -> dict:
        """整组电源开关：FC06 写 0xA2 位掩码（dut_lines 对应位置 1）。"""
        self._require()
        mask = 0
        if on:
            for ln in self.dut_lines:
                mask |= 1 << ln
        try:
            self._client().set_power_group(mask)
        except commboard.ModbusError as e:
            raise ManualDebugError(
                502, f"通讯板 {self.board_host}:{self.mb_port} 无应答：{e}")
        for i in range(len(self.dut_lines)):
            self._power[i + 1] = on
        return {"ok": True, "mask": mask, "powerOn": on}

    def sync_board_time(self, timestamp: Optional[int] = None) -> dict:
        """给通讯板对时（固件 MB_CMD_TEST_REST，2026-09-18 加入启动流程）。

        固件里「对时」和「复位测试」是同一个命令：除设置板卡时钟外，还会
        RemoteIoCtrReset() + ResetMultiIO()，即清空 IO 定时队列并把 GPIO 恢复
        默认（PWR_EN 默认 RESET）。也就是说**对时必然附带一次下电**——板卡轨迹
        日志的时间戳从此不再是 1970，代价是 DUT 回到断电态。
        """
        self._require()
        ts = int(time.time()) if timestamp is None else int(timestamp)
        try:
            self._client().test_reset(ts)
        except commboard.ModbusError as e:
            raise ManualDebugError(
                502, f"通讯板 {self.board_host}:{self.mb_port} 无应答：{e}")
        for i in range(len(self.dut_lines)):
            self._power[i + 1] = False
        return {"ok": True, "timestamp": ts, "ioReset": True}
