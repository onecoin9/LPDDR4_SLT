"""开发用 mock：模拟 DUT（mt6785 主控板）+ 通讯板透传行为，说**真实 hsg 0xAF 协议**。

用法（backend/ 目录下）：
  python mock_dut.py                      # site 1-50 全部（端口 40001-44924）
  python mock_dut.py --sites 1 --slots 1-12
  python mock_dut.py --sites 1,2

行为（对齐 mt6785 真实链路）：
  1. 启动即发 0x10 READY（16B 版本帧）。真实 DUT 只在上电时发一次，
     mock 额外每 3s 重发一次模拟保活（真实协议无心跳命令）。
  2. 收到 0x15（.cfg 文本）→ 回 ACK → 上报 0x11 DRAM 信息（按 cfg 推导）→
     发 0x12 请求老化时间（后端应答 AgingTimeAck）。
  3. 按 cfg 键推导三级链并"执行"：PL（容量校验+分块写读）→ LK（pattern，
     PatternTest/MemTester=1 时）→ APK（memtester 老化+DVFS，MemTester/
     DvfsTest/AgingTime 时）。进度经 0x18（instanceId=1 JSON）每 0.5s 上报；
     运行日志发往 UDP 63001（[S01DUT01] 前缀，模拟通讯板日志转发）。
  4. 阶段按模拟失败率随机失败 → 0x16；全部通过 → 0x17。

端口约定与 config.yaml 一致：40000 + (site-1)*100 + slot。
"""

import argparse
import asyncio
import json
import os
import random
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.cfg import parse_cfg, stages_from_map          # noqa: E402
from app.protocol import (ROLE_SERVER, ROLE_SLAVE, build_frame,  # noqa: E402
                          parse_frame, CMD_AGING_REQ, CMD_DONE, CMD_DRAM_INFO,
                          CMD_FAIL, CMD_READY, CMD_RECORD, CMD_START_TEST,
                          DT_STRING)

TICK = 0.5
LOG_PORT = 63001
READY_PAYLOAD = struct.pack("<HHHH", 0x0001, 0x0002, 0x0100, 0x0101) + b"M80-" + b"V1.1"

# 演示场景覆盖成功率/失败率（--pass-rate / --fail-rate；None = 用各阶段默认失败率）
# [2026-09-28 用户澄清] 演示口径是**成功率**：--pass-rate 0.75 = 约 75% 通道 PASS。
FAIL_RATE_OVERRIDE = None          # 整轮通道失败概率（由 pass-rate 折算或直接给定）

# [2026-09-28 用户指令] 测试盒成功率（测试盒 = SITE = 2 通讯板 × 12 DUT，agent.md §15）：
# --box-pass-rate 0.75 = 约 3/4 的**整站**全 PASS、1/4 的整站全 FAIL（站内 24 路
# 同批不良——模拟坏盒/坏通讯板/接触不良这类整站性缺陷，不是单颗芯片随机）。
# 每轮（75s 窗口）每站掷一次骰子，站内 24 路共享结果（单进程单事件循环，无竞态）。
BOX_PASS_RATE = None
_BOX_DECISION_WINDOW = 75.0
_box_state = {}                    # site -> (decided_at, is_bad)


def _box_is_bad(site: int) -> bool:
    now = time.monotonic()
    st = _box_state.get(site)
    if st is None or now - st[0] > _BOX_DECISION_WINDOW:
        _box_state[site] = (now, random.random() >= BOX_PASS_RATE)
    return _box_state[site][1]

# [2026-09-28 用户指令] 每轮测试恰好一路报"通讯板错误"：
# 0xFB commboard_timeout = 旧上位机 SCODE_TB_COMMUNICATE_ERROR，后端 STATUS_TEXT
# 已映射；落点随机——本轮**第一个失败**的通道认领，其余失败仍报 signal_fail。
# 窗口 75s 覆盖一轮完整时长（阶段边界 6/36/68s）：一轮内不会出现第二条，
# 快速重跑（间隔 >75s）重新认领。
COMMBOARD_FAIL_CODE = 0xFB
_COMMBOARD_CLAIM_WINDOW = 75.0
_last_commboard_claim = 0.0


def _claim_commboard_error() -> bool:
    """本通道是否认领"通讯板错误"（单进程单事件循环，无竞态）。"""
    global _last_commboard_claim
    now = time.monotonic()
    if now - _last_commboard_claim > _COMMBOARD_CLAIM_WINDOW:
        _last_commboard_claim = now
        return True
    return False

# 模拟参数：stage → (step 名, 时长 s, 失败率)。真实时长由下位机决定，这里压缩模拟。
STAGE_SIM = {
    "PL":  ("pl_check",     6,  0.005),
    "LK":  ("lk_pattern",  30,  0.060),
    "APK": ("apk_memtester", 32, 0.050),
}


class MockDut(asyncio.DatagramProtocol):
    def __init__(self, site: int, slot: int, log_sock, backend_port: int):
        self.site, self.slot = site, slot
        self.log_sock = log_sock            # 共享的 63001 发送 socket
        # 真实链路：DUT 上电主动向 PC 发 0x10（经通讯板到 server 的每 DUT 端口）。
        # mock 对端 = 后端该通道的本地端口 21000+(site-1)*100+slot
        self.server_addr = ("127.0.0.1", backend_port)
        self.transport = None
        self.job: asyncio.Task | None = None
        self.keepalive: asyncio.Task | None = None
        self.quiet_until = 0.0     # 任务结束后静默到该时刻（见 _run 尾部注释）
        self._ever_ran = False     # 是否跑过测试（决定是否需要补发保活）
        self._log_n = 0
        self.log_level = 2      # [HSG-LOG] cfg 到达前默认全量（与固件缺省一致）

    # ---------------- UDP / 组帧 ----------------

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr):
        parsed = parse_frame(data)
        if parsed is None:
            return
        cmd, payload = parsed
        if data[3] != ROLE_SERVER:          # 只接受上位机帧
            return
        if cmd == CMD_START_TEST:
            # 收到 0x15 瞬间即静默（job 建立前的窗口保护，双保险）
            self.quiet_until = time.monotonic() + 3600.0
            if self.job:
                self.job.cancel()
            self.job = asyncio.get_running_loop().create_task(
                self._run(payload.decode("utf-8", "replace")))

    def _send_frame(self, cmd: int, payload: bytes):
        if self.transport:
            self.transport.sendto(build_frame(ROLE_SLAVE, cmd, payload), self.server_addr)

    def _send_log(self, msg: str, cls: str = "TST"):
        """运行日志走 63001 通道（模拟通讯板转发），[S01DUT01] 前缀。

        [HSG-LOG 2026-09-16] 与固件同契约：行首 [SYS]/[TST]/[ERR] 标签 +
        LogLevel 档位源头拦截（0=只ERR 1=+TST 2=全量；cfg 无键默认 2 全量）。
        """
        if cls == "SYS" and self.log_level < 2:
            return
        if cls == "TST" and self.log_level < 1:
            return
        self.log_sock.sendto(
            f"[S{self.site:02d}DUT{self.slot:02d}] [{cls}] {msg}".encode("utf-8"),
            ("127.0.0.1", LOG_PORT))

    # ---------------- 上电：0x10 READY + 保活 ----------------

    async def keepalive_loop(self):
        """0x10 保活（mock 维持后端 connected 用）。

        [FIX 2026-09-28 两轮实证] 周期性保活与后端「TESTING 收 0x10=dut_reboot」
        存在结构性竞态：后端置 TESTING（发 0x15 前后）与结果消化窗口都是 mock
        看不见的，3s 一跳的 READY 必然偶尔（这次实证是每路必中）落进窗口。
        真实 DUT 本来就**只在上电发一次 READY**——mock 改成同语义：上线后只发
        一次；测试期间由 0x18 进度帧维持会话活性；测试结束（+5s 静默）后补发
        一次让后端保持在线显示。彻底消除竞态，也更贴近真机行为。
        """
        self._send_frame(CMD_READY, READY_PAYLOAD)      # 上电：立即一次
        while True:
            # 未跑过测试：每 30s 补发（后端重启会丢在线态，需低频保活重建）；
            # 跑过测试：结束静默后补发一次（重新闭嘴）。30s 低频 + 后端 2s
            # 宽限双保护，落入 TESTING 窗口的概率可忽略。
            if time.monotonic() >= self.quiet_until:
                if not self._ever_ran:
                    self._send_frame(CMD_READY, READY_PAYLOAD)
                elif self.job and self.job.done():
                    self._send_frame(CMD_READY, READY_PAYLOAD)
                    self._ever_ran = False              # 补发一次后重新闭嘴
            await asyncio.sleep(30)

    # ---------------- 模拟三级链执行 ----------------

    async def _run(self, cfg_text: str):
        loop = asyncio.get_running_loop()
        # 结束静默窗口：覆盖后端结果处理（见 keepalive 注释）
        self.quiet_until = time.monotonic() + 3600.0
        self._ever_ran = True
        try:
            await self._run_inner(cfg_text)
        finally:
            self.quiet_until = time.monotonic() + 5.0

    async def _run_inner(self, cfg_text: str):
        loop = asyncio.get_running_loop()
        # ACK（对齐 receive_config_with_ack：len=2 data=[0,0] 校验 0x55）
        self._send_frame(CMD_START_TEST, b"\x00\x00")
        await asyncio.sleep(0.3)

        m = parse_cfg(cfg_text)
        self.log_level = m.get("LOGLEVEL", 2)   # [HSG-LOG] cfg 无键 = 全量（旧行为）
        stages = stages_from_map(m)
        # DRAM 信息（0x11）：按 cfg 推导
        r0 = m.get("CHANNELA_RANK0_SIZE", 8)
        r1 = m.get("CHANNELA_RANK1_SIZE", 0)
        r0e, r1e = m.get("CHANNELA_RANK0_ENABLE", 1), m.get("CHANNELA_RANK1_ENABLE", 0)
        info = bytes([m.get("DENSITY", 16),
                      r0 if r0e else 0, m.get("DIENUM", 2) // 2 if r0e else 0,
                      r1 if r1e else 0, m.get("DIENUM", 2) // 2 if r1e else 0])
        self._send_frame(CMD_DRAM_INFO, info)
        self._send_frame(CMD_AGING_REQ, b"")          # 请求老化时间
        self._send_log(f"cfg 下发完成：Density={m.get('DENSITY', 16)}Gb "
                       f"stages={stages} AgingTime={m.get('AGINGTIME', 0)}min "
                       f"VDD1={m.get('VDD1', 0)}mV LogLevel={self.log_level}",
                       cls="SYS")

        sim = [STAGE_SIM[s] for s in stages]
        box_bad = False
        if BOX_PASS_RATE is not None:
            # 测试盒模式（演示口径）：整站共享一次成败，站内不再有单颗随机；
            # 坏盒 → 本路在首阶段末 FAIL（整站同批不良）。
            box_bad = _box_is_bad(self.site)
            sim = [(step, dur, 0.0) for step, dur, _ in sim]
        elif FAIL_RATE_OVERRIDE is not None:
            # [2026-09-28] 覆盖值 = **整轮通道失败概率**（非每阶段）：一个通道要连过
            # N 个阶段才算 PASS，故按阶段数折算每阶段概率 p_stage = 1-(1-p)^(1/N)。
            # 成功率口径由 --pass-rate 折算（pass 0.75 → p=0.25）。
            n = max(len(stages), 1)
            p_stage = 1.0 - (1.0 - FAIL_RATE_OVERRIDE) ** (1.0 / n)
            sim = [(step, dur, p_stage) for step, dur, _ in sim]
        total = sum(d for _, d, _ in sim) or 1.0
        t0 = time.monotonic()
        try:
            for si, (stage, (step, dur, fail_rate)) in enumerate(zip(stages, sim)):
                step_t0 = time.monotonic()
                self._send_log(f"{step} 开始 (stage {si + 1}/{len(stages)})")
                while True:
                    await asyncio.sleep(TICK)
                    el = time.monotonic() - step_t0
                    if el >= dur:
                        break
                    frac = (si + el / dur) / len(stages)
                    el_total = time.monotonic() - t0
                    obj = {"step": step, "stage": stage,
                           "progress": round(frac * 100, 1),
                           "durationSec": round(el_total, 1),
                           "countdownSec": round(max(0.0, total - el_total), 1)}
                    self._send_frame(CMD_RECORD,
                                     bytes([1, DT_STRING]) + json.dumps(obj).encode())
                    self._maybe_log(step)
                # 坏盒 → 首阶段末尾即整站同批 FAIL；其余阶段不再随机判死
                if (box_bad and si == 0) or (not box_bad and random.random() < fail_rate):
                    if _claim_commboard_error():
                        # 本轮唯一一路"通讯板错误"（落点随机，演示用）
                        self._send_log("通讯板通讯超时 FAIL（commboard_timeout）",
                                       cls="ERR")
                        self._send_frame(CMD_FAIL,
                                         bytes([COMMBOARD_FAIL_CODE, 0x00]))
                    else:
                        self._send_log(f"{step} 数据比对失败 FAIL", cls="ERR")
                        self._send_frame(CMD_FAIL, bytes([0x02, 0x00]))   # signal_fail
                    return
            self._send_frame(CMD_DONE, bytes([0x00, 0x00]))
        except asyncio.CancelledError:
            return

    def _maybe_log(self, step: str):
        self._log_n += 1
        if self._log_n % 10 == 0:
            self._send_log(f"{step} pattern=0x78 校验通过 "
                           f"addr=0x{random.randint(0x100000, 0xFFFFFFF):X}")


def parse_slots(spec: str) -> list[int]:
    """'1-12,15,18' → [1..12,15,18]"""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


async def main():
    ap = argparse.ArgumentParser(description="LPDDR4x SLT mock DUT (hsg 0xAF 协议)")
    ap.add_argument("--sites", default="1-50",
                    help="site 列表，如 1 / 1-10 / 1,2（默认 1-50，与 config.yaml 一致）")
    ap.add_argument("--slots", default="1-24", help="通道子集，如 1-12 或 3,5")
    ap.add_argument("--port-base", type=int, default=40000,
                    help="端口基址（默认 40000，与 config.yaml 对应；须避开后端本地端口 21000-25924）")
    ap.add_argument("--box-pass-rate", type=float, default=None,
                    help="演示用（推荐）：**测试盒（=SITE 整站）成功率** 0.0-1.0。"
                         "0.75=约四分之三的站整站 PASS、四分之一整站 FAIL（站内 24 路同批）")
    ap.add_argument("--pass-rate", type=float, default=None,
                    help="演示用：**单通道**成功率 0.0-1.0（每颗独立随机；与 --box-pass-rate 二选一）")
    ap.add_argument("--fail-rate", type=float, default=None,
                    help="演示用：整轮通道失败率 0.0-1.0（--pass-rate 的互补参数）。"
                         "两者都不给 = 内置分阶段随机(PL 0.5%%/LK 6%%/APK 5%%)")
    args = ap.parse_args()

    global FAIL_RATE_OVERRIDE, BOX_PASS_RATE
    # 口径优先级：测试盒成功率（演示口径）> 单通道成功率/失败率
    BOX_PASS_RATE = args.box_pass_rate
    # 成功率口径：pass-rate 0.75 → 通道失败概率 0.25
    if args.pass_rate is not None:
        FAIL_RATE_OVERRIDE = 1.0 - args.pass_rate
    else:
        FAIL_RATE_OVERRIDE = args.fail_rate

    sites = parse_slots(args.sites)
    slots = parse_slots(args.slots)
    log_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    loop = asyncio.get_running_loop()
    made = 0
    for site in sites:
        for slot in slots:
            port = args.port_base + (site - 1) * 100 + slot
            backend_port = 21000 + (site - 1) * 100 + slot
            _, proto = await loop.create_datagram_endpoint(
                lambda s=site, c=slot, bp=backend_port: MockDut(s, c, log_sock, bp),
                local_addr=("127.0.0.1", port))
            proto.keepalive = loop.create_task(proto.keepalive_loop())
            made += 1
    rate_info = (f"，测试盒(SITE)成功率 {BOX_PASS_RATE:.0%}（整站同批）+ 每轮一路通讯板错误"
                 if BOX_PASS_RATE is not None
                 else f"，整轮通道成功率 {1.0 - FAIL_RATE_OVERRIDE:.0%}（按阶段折算）+ 每轮一路通讯板错误"
                 if FAIL_RATE_OVERRIDE is not None
                 else "，成功率=内置分阶段随机(PL 0.5%/LK 6%/APK 5% 失败)+ 每轮一路通讯板错误")
    print(f"[mock_dut] 已启动 {made} 路 mock DUT（hsg 0xAF 协议，日志→UDP {LOG_PORT}）："
          f"sites={sites} slots={slots[0]}-{slots[-1]}"
          f"（端口 {args.port_base + (sites[0] - 1) * 100 + slots[0]}.."
          f"{args.port_base + (sites[-1] - 1) * 100 + slots[-1]}）{rate_info}，等待后端 0x15...",
          flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[mock_dut] 退出", flush=True)
