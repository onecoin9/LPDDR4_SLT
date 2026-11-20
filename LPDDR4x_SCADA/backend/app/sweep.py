"""时序/参数扫描引擎（Phase 2；TytanSLT shmoo 的对应实现）。

数据来源：ProductProfile params 行的 start/step/end 三列（前端已渲染并持久化，
此前无消费者）。一次扫描取一个主轴 = 三列均非空且勾选的那一行；
多于一行报错（多轴扫描属后续扩展）。

每个扫描点：
  全部点深拷贝 profile → 主轴行 value=当前点 → 严格预检查和编译 →
  （quick=True 默认：AgingTime/MemTester/DvfsTest 置 0 → 仅 PL+LK 快测，
   快测覆盖与完整老化不同；完整配置扫描传 quick=False）→
  预约引擎 → seq.start(cfg_text=点位配置) → 等全部通道完成 → 从本次作业收结果。
  生产 cfg 保持原值；计划通道缺失结果时记 NOT_STARTED，不能判作全 PASS。

产物：内存 status（/api/sweep/status 轮询）；
  records/sweeps/<时间戳>_<轴名净化>.csv（逐点逐通道明细，点内批次
  <batch>-SW<idx> 可在 /api/records 下钻）+ .summary.json（边界区间等）。
安全：轴名经白名单净化后才进文件名；每次落盘前做显式 ../ 与目录边界校验；
  单次扫描 ≤ SWEEP_MAX_POINTS（64）点。
"""

import asyncio
import copy
import csv
import io
import json
import math
import os
import re
import time
from typing import Dict, List, Optional, Tuple

from .profileplan import require_profile, ProfileError
from .runtimepolicy import RunPolicy

Key = Tuple[int, int]

SWEEP_MAX_POINTS = 64

_SAFE_FNAME = re.compile(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+")


class SweepError(Exception):
    """扫描请求非法（HTTP 400 语义）"""


def _fmt(v: float) -> str:
    """点值字符串：整数语义出整数（'40' 而非 '40.0'），小数用 %g"""
    return str(int(round(v))) if abs(v - round(v)) < 1e-9 else f"{v:g}"


def _guard_path(root: str, path: str) -> str:
    """落盘前守卫：拒绝任何含 .. 的路径，且必须位于 root 目录内。"""
    parts = path.replace("/", os.sep).split(os.sep)
    if ".." in parts:
        raise SweepError(f"落盘路径含非法相对段: {path}")
    norm = os.path.abspath(path)
    if os.path.commonpath([root, norm]) != root:
        raise SweepError(f"落盘路径越界: {path}")
    return norm


def build_points(start: str, step: str, end: str) -> List[float]:
    try:
        s, d, e = float(start), float(step), float(end)
    except (TypeError, ValueError) as exc:
        raise SweepError(f"扫描范围非法：起始/步进/结束须为数值（{exc}）") from exc
    if not all(math.isfinite(v) for v in (s, d, e)):
        raise SweepError("扫描范围必须是有限数值，不能使用 NaN 或 Inf")
    if d == 0:
        raise SweepError("扫描步进不能为 0")
    if (e - s) * d < 0:
        raise SweepError(f"扫描方向矛盾：起始 {start} → 结束 {end} 与步进 {step} 不匹配")
    span = (e - s) / d
    if not math.isfinite(span):
        raise SweepError("扫描范围过大")
    n = int(math.floor(span + 1e-9)) + 1
    if n < 1:
        raise SweepError("扫描点数为 0（检查起始/步进/结束）")
    if n > SWEEP_MAX_POINTS:
        raise SweepError(f"扫描点数 {n} 超过上限 {SWEEP_MAX_POINTS}（缩小范围或加大步进）")
    return [round(s + i * d, 9) for i in range(n)]


def find_axis(profile: dict) -> dict:
    """定位扫描主轴行：start/step/end 三列均非空且 checked。"""
    rows = [p for p in (profile.get("params") or [])
            if isinstance(p, dict)
            and str(p.get("start", "") or "").strip()
            and str(p.get("step", "") or "").strip()
            and str(p.get("end", "") or "").strip()]
    if not rows:
        raise SweepError("没有参数行填写扫描范围（起始/步进/结束三列）")
    if len(rows) > 1:
        names = "、".join(str(r.get("name")) for r in rows)
        raise SweepError(f"扫描主轴只能有一个，当前 {len(rows)} 行填了范围：{names}")
    row = rows[0]
    if not row.get("checked"):
        raise SweepError(f"扫描主轴 {row.get('name')} 未勾选启用")
    return row


def compile_point(profile: dict, axis_name: str, value: float,
                  base: Dict[str, int], quick: bool) -> Tuple[str, List[str]]:
    if not profile.get("pl1Enabled"):
        raise SweepError("扫描主轴的参数覆盖未启用")
    prof = copy.deepcopy(profile)
    for p in prof.get("params") or []:
        if isinstance(p, dict) and p.get("name") == axis_name:
            p["value"] = _fmt(value)
            p["checked"] = True
    try:
        plan = require_profile(prof, base, quick=quick)
    except ProfileError as exc:
        raise SweepError("；".join(e["field"] + "：" + e["messageZh"] for e in exc.preview["errors"])) from exc
    if any(r.get('field')==axis_name for r in plan.get('rejectedParameters',[])):
        raise SweepError('扫描轴未应用，不能按默认配置执行扫描点')
    return plan["cfgText"], [w["messageZh"] for w in plan["warnings"]]


class SweepEngine:
    """单实例扫描控制器（与 Sequencer 同生命周期）。"""

    def __init__(self, seq, hub, records_root: str):
        self.seq = seq
        self.hub = hub
        self.records_root = records_root
        self._task: Optional[asyncio.Task] = None
        self._cancel = False
        self._owner = object()
        self._targets = []
        self.status: dict = {"running": False}

    # ---------------- 对外状态 ----------------

    def snapshot(self) -> dict:
        st = dict(self.status)
        st["points"] = list(st.get("points", []))
        st["results"] = [dict(r, per_key=dict(r.get("per_key", {})))
                         for r in st.get("results", [])]
        return st

    # ---------------- 启停 ----------------

    async def start(self, profile: dict, targets: List[Key], base: Dict[str, int],
                    quick: bool = True, stop_on_fail: bool = False,
                    batch_prefix: str = "") -> dict:
        if self.status.get("running"):
            raise SweepError("扫描已在进行（先停止当前扫描）")
        if not targets:
            raise SweepError("没有可启动的通道（需在线且空闲）")
        axis = find_axis(profile)
        name = str(axis["name"])
        pts = build_points(axis["start"], axis["step"], axis["end"])
        prepared = [compile_point(profile, name, v, base, quick) for v in pts]
        hashes = [text for text, _ in prepared]
        if len(set(hashes)) != len(hashes):
            raise SweepError("多个扫描点量化后配置相同，请调整步进或单位")
        owner = object()
        policy = getattr(self.seq, "policy_provider", RunPolicy)().model_copy(deep=True)
        self.seq.reserve(owner)
        self._owner = owner
        self._targets = list(dict.fromkeys(targets))
        self.status = {
            "running": True,
            "axis": name,
            "quick": quick,
            "stop_on_fail": stop_on_fail,
            "points": pts,
            "current_index": None,
            "started_at": time.time(),
            "results": [],
            "csv_path": None,
            "error": None,
        }
        self._cancel = False
        self._task = asyncio.create_task(
            self._run(profile, name, pts, self._targets, base, quick, stop_on_fail, batch_prefix, prepared, policy))
        self._task.add_done_callback(lambda task: self._on_done(task, owner))
        return self.snapshot()

    async def stop(self) -> bool:
        if not self.status.get("running") or self._task is None:
            return False
        self._cancel = True
        task, owner = self._task, self._owner
        try:
            await self.seq.stop(self._targets)         # 只停止本扫描的通道
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            # stop 的返回就是预约释放完成；不依赖下一轮事件循环的 done callback。
            self.seq.release(owner)
            if self._task is task:
                self.status["running"] = False
                if task.cancelled():
                    self.status["aborted"] = "手动停止"
        return True

    def _on_done(self, task: asyncio.Task, owner) -> None:
        self.seq.release(owner)
        if self._task is not task:
            return
        self.status["running"] = False
        if task.cancelled():
            self.status["aborted"] = "手动停止"
        if not task.cancelled() and task.exception() is not None:
            self.status["running"] = False
            self.status["error"] = repr(task.exception())
            self.hub.syslog("ERROR", f"扫描任务异常退出: {task.exception()!r}")

    # ---------------- 主循环 ----------------

    async def _run(self, profile, axis_name, pts, targets, base, quick,
                   stop_on_fail, batch_prefix, prepared, policy) -> None:
        root = os.path.abspath(os.path.join(self.records_root, "sweeps"))
        os.makedirs(root, exist_ok=True)
        safe_axis = (_SAFE_FNAME.sub("_", axis_name)[:48] or "axis")
        stem = time.strftime("%Y%m%d_%H%M%S") + "_" + safe_axis
        csv_path = _guard_path(root, os.path.join(root, stem + ".csv"))
        summary_path = _guard_path(root, os.path.join(root, stem + ".summary.json"))
        self.status["csv_path"] = csv_path
        summary = {"axis": axis_name, "quick": quick, "points": len(pts),
                   "targets": len(targets), "started_at": self.status["started_at"]}
        aborted = None
        try:
            f = io.open(csv_path, "w", newline="", encoding="utf-8-sig")
            with f:
                w = csv.writer(f)
                w.writerow(["point_idx", "value", "site", "slot", "result",
                            "failItem", "durationSec", "batch"])
                for i, v in enumerate(pts):
                    if self._cancel:
                        aborted = "手动停止"
                        break
                    self.status["current_index"] = i
                    try:
                        text, warns = prepared[i]
                    except Exception as exc:
                        aborted = f"点 {v} 编译失败: {exc}"
                        break
                    for wn in warns:
                        self.hub.syslog("WARN", f"[扫描 {axis_name}={_fmt(v)}] {wn}")
                    batch = f"{batch_prefix}-SW{i + 1:02d}"
                    self.hub.syslog("INFO",
                                    f"[扫描 {i + 1}/{len(pts)}] {axis_name}={_fmt(v)}"
                                    f"（{'快测' if quick else '完整配置'}，批次 {batch}）")
                    outcomes = {}
                    started = await self.seq.start(list(targets), batch, cfg_text=text,
                                                   owner=self._owner, outcomes=outcomes, run_policy=policy)
                    if not started:
                        aborted = f"点 {v} 无通道可启动（通道离线或忙碌）"
                    tasks = [self.seq.tasks[k] for k in targets if k in self.seq.tasks]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    per_key: Dict[str, dict] = {}
                    for (site, slot) in targets:
                        st = outcomes.get((site, slot), {"result": "CANCEL" if self._cancel else "NOT_STARTED",
                                                        "failItem": "missing_result", "durationSec": 0})
                        per_key[f"S{site:02d}CH{slot:02d}"] = {
                            "result": st.get("result") or ("CANCEL" if self._cancel else "UNKNOWN"),
                            "failItem": st.get("failItem") or "",
                        }
                        w.writerow([i + 1, _fmt(v), site, slot,
                                    per_key[f"S{site:02d}CH{slot:02d}"]["result"],
                                    per_key[f"S{site:02d}CH{slot:02d}"]["failItem"],
                                    round(st.get("durationSec") or 0.0, 1), batch])
                    f.flush()
                    rec = {"index": i + 1, "value": _fmt(v), "batch": batch,
                           "per_key": per_key,
                           "pass": sum(1 for r in per_key.values() if r["result"] == "PASS"),
                           "total": len(targets), "started": len(started)}
                    self.status["results"].append(rec)
                    if not started:
                        break
                    if stop_on_fail and rec["pass"] < rec["total"] and not self._cancel:
                        aborted = f"stop_on_fail：点 {v} 出现 FAIL"
                        break
                    if self._cancel:
                        aborted = "手动停止"
                        break
        except asyncio.CancelledError:
            aborted = "手动停止"
            raise
        except Exception as exc:
            aborted = f"扫描异常：{exc}"
            raise
        finally:
            summary["aborted"] = aborted
            summary["finished_at"] = time.time()
            summary["pass_boundary"] = self._boundary(self.status["results"])
            self.status.update({"running": False, "current_index": None,
                                "summary": summary, "aborted": aborted})
            try:
                fs = io.open(summary_path, "w", encoding="utf-8")
                with fs:
                    json.dump({"summary": summary, "results": self.status["results"]},
                              fs, ensure_ascii=False, indent=2)
            except OSError as exc:
                self.hub.syslog("ERROR", f"扫描 summary 落盘失败: {exc}")
            self.hub.syslog("INFO" if aborted is None else "WARN",
                            f"[扫描结束] {axis_name}：{len(self.status['results'])}/{len(pts)} 点完成"
                            + (f"，{aborted}" if aborted else "")
                            + f"，明细 {csv_path}")

    @staticmethod
    def _boundary(results: List[dict]) -> Optional[dict]:
        """通过边界（最长连续全 PASS 区间）；点不足 2 个或全过/全挂时返回 None。"""
        if len(results) < 2:
            return None
        vals = [r["value"] for r in results]
        ok = [r["pass"] == r["total"] for r in results]
        if all(ok) or not any(ok):
            return None
        best = cur = None
        for i, o in enumerate(ok):
            if o:
                cur = [i, i] if cur is None else [cur[0], i]
                if best is None or (cur[1] - cur[0]) > (best[1] - best[0]):
                    best = list(cur)
            else:
                cur = None
        if best is None:
            return None
        return {"from": vals[best[0]], "to": vals[best[1]],
                "points": best[1] - best[0] + 1}
