"""CSV + log 落盘（无数据库，SSOT §3 决策）。

目录结构：records/<YYYY-MM-DD>/<批次号>/summary.csv
          records/<YYYY-MM-DD>/<批次号>/site01_slot07_174512.log
summary.csv 列：timestamp,batch,slot,result,fail_item,duration_sec,site
（前 6 列与任务书约定一致，末列 site 为多 site 扩展，单 site 恒为 1）
"""

import csv
import os
import re
import uuid
from datetime import datetime
from typing import List, Optional
from .runtimepolicy import atomic_json


class RunWriter:
    """单颗 DUT 单次测试的 log 文件句柄。"""

    def __init__(self, path: str, site: int, slot: int, batch: str):
        self.path = path
        self._closed = False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._f = open(path, "a", encoding="utf-8")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._f.write(f"==== LPDDR4x SLT run  site={site:02d} slot={slot:02d} "
                      f"batch={batch} start={ts} ====\n")
        self._f.flush()

    def write_log(self, level: str, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._f.write(f"{ts} [{level}] {msg}\n")
        self._f.flush()

    def close(self, note: str = "") -> None:
        if self._closed:
            return
        if note:
            self.write_log("INFO", note)
        self._f.write(f"==== end {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====\n")
        self._f.close()
        self._closed = True


class Recorder:
    def __init__(self, root: str):
        self.root = root
        os.makedirs(self.root, exist_ok=True)

    def _batch_dir(self, batch: str) -> str:
        day = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.root, day, batch)

    def start_run(self, site: int, slot: int, batch: str) -> RunWriter:
        ts = datetime.now().strftime("%H%M%S_%f") + "_" + uuid.uuid4().hex[:8]
        path = os.path.join(self._batch_dir(batch),
                            f"site{site:02d}_slot{slot:02d}_{ts}.log")
        return RunWriter(path, site, slot, batch)

    def write_run_record(self, record: dict) -> str:
        """One immutable identity per admission, atomically updated through terminal state."""
        run_id = record["runId"]
        if not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise ValueError("Invalid run ID")
        day = datetime.fromtimestamp(record["startedAt"]).strftime("%Y-%m-%d")
        path = os.path.join(self.root, "run_metadata", day,
                            run_id + ".run.json")
        atomic_json(path, record)
        return path

    def append_result(self, batch: str, site: int, slot: int, result: str,
                      fail_item: str, duration_sec: float) -> str:
        d = self._batch_dir(batch)
        os.makedirs(d, exist_ok=True)
        csv_path = os.path.join(d, "summary.csv")
        new = not os.path.exists(csv_path)
        with open(csv_path, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "batch", "slot", "result",
                            "fail_item", "duration_sec", "site"])
            w.writerow([datetime.now().isoformat(timespec="seconds"),
                        batch, f"{slot:02d}", result, fail_item,
                        f"{duration_sec:.1f}", site])
        return csv_path

    def query(self, date: Optional[str] = None, batch: Optional[str] = None) -> dict:
        """查询记录：date/batch 缺省时列出可用的日期与批次，都给定时返回 summary.csv 行。"""
        root = self.root
        if not date:
            return {"type": "dates",
                    "dates": sorted(d for d in os.listdir(root)
                                    if d != "run_metadata" and os.path.isdir(os.path.join(root, d)))}
        day_dir = os.path.join(root, date)
        if not os.path.isdir(day_dir):
            return {"type": "batches", "date": date, "batches": []}
        batches = sorted(b for b in os.listdir(day_dir)
                         if os.path.isdir(os.path.join(day_dir, b)))
        if not batch:
            return {"type": "batches", "date": date, "batches": batches}
        csv_path = os.path.join(day_dir, batch, "summary.csv")
        rows: List[dict] = []
        if os.path.exists(csv_path):
            with open(csv_path, encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
        return {"type": "records", "date": date, "batch": batch, "rows": rows}
