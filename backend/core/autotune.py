import copy
import json
import math
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


MODE_LIMITS = {
    "conservative": 5.0,
    "balanced": 10.0,
    "aggressive": 20.0,
}


TABLE_LIMITS = {
    "veTable1": (0.0, 255.0),
    "ignitionTable1": (-10.0, 60.0),
    "boostTable1": (0.0, 300.0),
    "lambdaTable1": (0.6, 1.4),
}


class AutoTuneEngine:
    """
    Classic non-AI auto-tune engine.
    Supports VE Analyze, Ignition Tune, WUE Analyze, and Trim Table workflows.
    """

    def __init__(self, client: Any, db_path: str, max_workers: int = 4) -> None:
        self.client = client
        self.db_path = db_path
        self.max_workers = max(1, int(max_workers))
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS autotune_runs (
                    run_id TEXT PRIMARY KEY,
                    tool_name TEXT,
                    started_at REAL,
                    completed_at REAL,
                    mode TEXT,
                    dry_run INTEGER,
                    status TEXT,
                    summary_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS autotune_adjustments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    table_name TEXT,
                    row_idx INTEGER,
                    col_idx INTEGER,
                    before_value REAL,
                    after_value REAL,
                    delta_value REAL,
                    delta_pct REAL,
                    reason TEXT,
                    vetoed INTEGER DEFAULT 0,
                    created_at REAL,
                    FOREIGN KEY(run_id) REFERENCES autotune_runs(run_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_autotune_adjustments_run ON autotune_adjustments(run_id)")
            conn.commit()
        finally:
            conn.close()

    def run(self, tool_name: str, params: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
        tool = (tool_name or "ve").strip().lower()
        mode = str(params.get("mode", "balanced")).lower()
        if mode not in MODE_LIMITS:
            mode = "balanced"

        run_id = f"autotune_{int(time.time() * 1000)}"
        progress: List[str] = []

        self._log_run_start(run_id, tool, mode, dry_run)
        try:
            if tool in ("ve", "ve analyze", "ve_analyze"):
                result = self._run_ve_analyze(run_id, params, mode, dry_run, progress)
            elif tool in ("ignition", "ignition tune", "ignition_autotune"):
                result = self._run_ignition_tune(run_id, params, mode, dry_run, progress)
            elif tool in ("wue", "wue analyze", "wue_analyze"):
                result = self._run_wue_analyze(run_id, params, mode, dry_run, progress)
            else:
                result = self._run_trim_table(run_id, params, mode, dry_run, progress)

            result["run_id"] = run_id
            result["tool_name"] = tool
            result["mode"] = mode
            result["dry_run"] = dry_run
            result["progress"] = progress
            self._log_run_end(run_id, "ok", result)
            return result
        except Exception as e:
            err = {
                "run_id": run_id,
                "tool_name": tool,
                "mode": mode,
                "dry_run": dry_run,
                "status": "error",
                "error": str(e),
                "progress": progress,
                "changes": [],
            }
            self._log_run_end(run_id, "error", err)
            return err

    def _run_ve_analyze(self, run_id: str, params: Dict[str, Any], mode: str, dry_run: bool, progress: List[str]) -> Dict[str, Any]:
        table_name = str(params.get("table_name", "veTable1"))
        table = self._load_table_matrix(table_name, params)
        rpm_axis = self._resolve_axis(params.get("rpm_axis"), len(table[0]) if table else 16, start=500.0, step=500.0)
        map_axis = self._resolve_axis(params.get("map_axis"), len(table), start=30.0, step=15.0)
        samples = self._resolve_samples(params)

        filters = {
            "min_samples": int(params.get("min_samples", 50)),
            "ignore_transient": bool(params.get("ignore_transient", True)),
            "tps_transient_delta": float(params.get("tps_transient_delta", 5.0)),
            "steady_state_only": bool(params.get("steady_state_only", True)),
            "rpm_variance": float(params.get("rpm_variance", 100.0)),
            "duty_limit": float(params.get("duty_limit", 85.0)),
            "knock_abort": float(params.get("knock_abort_count", 5.0)),
        }

        max_pct = float(params.get("max_change_pct", MODE_LIMITS.get(mode, 10.0)))
        max_pct = min(max_pct, MODE_LIMITS.get(mode, 10.0))

        stats, global_stats = self._build_cell_stats(samples, rpm_axis, map_axis, filters)
        progress.append(f"Collected {len(samples)} samples -> {len(stats)} populated cells")

        if global_stats["knock_events"] >= filters["knock_abort"]:
            progress.append("High knock detected, auto-tune aborted")
            return {
                "status": "aborted",
                "table_name": table_name,
                "changes": [],
                "warnings": ["High knock count detected. VE auto-tune aborted."],
                "summary": {"cells_tuned": 0, "avg_correction_pct": 0.0},
            }

        rows = len(table)
        cols = len(table[0]) if rows else 0
        changes: List[Dict[str, Any]] = []

        def evaluate_cell(item: Tuple[Tuple[int, int], Dict[str, float]]) -> Optional[Dict[str, Any]]:
            (r, c), cell = item
            if cell["samples"] < filters["min_samples"]:
                return None
            target = float(cell["target_afr_avg"])
            measured = float(cell["afr_avg"])
            if target <= 0.0:
                return None
            afr_error = (measured - target) / max(0.001, target)
            delta_pct = -afr_error * 100.0
            delta_pct = max(-max_pct, min(max_pct, delta_pct))

            before = float(table[r][c])
            after = before * (1.0 + (delta_pct / 100.0))
            lo, hi = TABLE_LIMITS.get(table_name, (0.0, 255.0))
            after = max(lo, min(hi, after))

            veto_reason = ""
            vetoed = False
            if delta_pct > 0.0 and cell["duty_avg"] > filters["duty_limit"]:
                vetoed = True
                veto_reason = f"Duty {cell['duty_avg']:.1f}% exceeds {filters['duty_limit']:.1f}%"
                after = before
                delta_pct = 0.0

            return {
                "row": r,
                "col": c,
                "before": round(before, 4),
                "after": round(after, 4),
                "delta": round(after - before, 4),
                "delta_pct": round(delta_pct, 3),
                "samples": int(cell["samples"]),
                "target_afr": round(target, 4),
                "measured_afr": round(measured, 4),
                "reason": "VE Analyze",
                "vetoed": vetoed,
                "veto_reason": veto_reason,
            }

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            for out in ex.map(evaluate_cell, list(stats.items())):
                if out:
                    changes.append(out)

        changes.sort(key=lambda x: (x["row"], x["col"]))

        missing = self._find_missing_cells(rows, cols, stats, filters["min_samples"])
        interpolated = self._interpolate_missing_cells(table, changes, missing, max_pct)
        changes.extend(interpolated)

        warnings: List[str] = []
        low_sample_cells = sum(1 for v in stats.values() if v["samples"] < filters["min_samples"])
        if low_sample_cells > 0:
            warnings.append(f"Skipped {low_sample_cells} low-sample cells")

        avg_corr = self._avg_abs_pct(changes)
        progress.append(f"Computed {len(changes)} candidate cell changes")

        if not dry_run:
            table = self._apply_changes_to_table(table, changes)

        self._log_adjustments(run_id, table_name, changes)

        return {
            "status": "ok",
            "table_name": table_name,
            "base_table": table,
            "rpm_axis": rpm_axis,
            "map_axis": map_axis,
            "changes": changes,
            "warnings": warnings,
            "global_stats": global_stats,
            "summary": {
                "cells_tuned": len(changes),
                "avg_correction_pct": round(avg_corr, 3),
                "vetoed": sum(1 for c in changes if c.get("vetoed")),
            },
        }

    def _run_ignition_tune(self, run_id: str, params: Dict[str, Any], mode: str, dry_run: bool, progress: List[str]) -> Dict[str, Any]:
        table_name = "ignitionTable1"
        table = self._load_table_matrix(table_name, params)
        rpm_axis = self._resolve_axis(params.get("rpm_axis"), len(table[0]) if table else 16, start=500.0, step=500.0)
        map_axis = self._resolve_axis(params.get("map_axis"), len(table), start=30.0, step=15.0)
        samples = self._resolve_samples(params)

        require_ramp = bool(params.get("require_safe_ramp", True))
        ramp_passed = bool(params.get("safe_ramp_passed", False))
        if require_ramp and not ramp_passed:
            return {
                "status": "blocked",
                "table_name": table_name,
                "changes": [],
                "warnings": ["Safe power-ramp test is required before ignition auto-tune."],
                "summary": {"cells_tuned": 0, "avg_correction_deg": 0.0},
                "requires_confirmation": True,
            }

        max_adv = float(params.get("max_advance_deg", 1.0))
        max_adv = min(1.0, max(0.1, max_adv))
        max_ret = float(params.get("max_retard_deg", 3.0))

        stats, global_stats = self._build_cell_stats(
            samples,
            rpm_axis,
            map_axis,
            {
                "min_samples": int(params.get("min_samples", 30)),
                "ignore_transient": True,
                "tps_transient_delta": float(params.get("tps_transient_delta", 5.0)),
                "steady_state_only": bool(params.get("steady_state_only", True)),
                "rpm_variance": float(params.get("rpm_variance", 100.0)),
                "duty_limit": 100.0,
                "knock_abort": float(params.get("knock_abort_count", 8.0)),
            },
        )

        if global_stats["knock_events"] >= float(params.get("knock_abort_count", 8.0)):
            progress.append("Ignition tune aborted due to high knock")
            return {
                "status": "aborted",
                "table_name": table_name,
                "changes": [],
                "warnings": ["High knock count detected. Ignition auto-tune aborted."],
                "summary": {"cells_tuned": 0, "avg_correction_deg": 0.0},
                "requires_confirmation": True,
            }

        changes: List[Dict[str, Any]] = []
        for (r, c), cell in stats.items():
            if cell["samples"] < int(params.get("min_samples", 30)):
                continue
            before = float(table[r][c])
            knock_rate = cell["knock_sum"] / max(1.0, cell["samples"])

            if knock_rate > 0.05:
                delta_deg = -min(max_ret, 1.0 + knock_rate * 3.0)
                reason = "Knock detected, retarding timing"
            else:
                delta_deg = min(max_adv, 0.25 + (0.02 * min(10.0, cell["samples"] / 10.0)))
                reason = "No knock in steady-state samples, slow MBT approach"

            after = before + delta_deg
            lo, hi = TABLE_LIMITS[table_name]
            after = max(lo, min(hi, after))

            changes.append(
                {
                    "row": r,
                    "col": c,
                    "before": round(before, 4),
                    "after": round(after, 4),
                    "delta": round(after - before, 4),
                    "delta_deg": round(after - before, 4),
                    "samples": int(cell["samples"]),
                    "reason": reason,
                    "vetoed": False,
                    "veto_reason": "",
                }
            )

        self._log_adjustments(run_id, table_name, changes)

        if not dry_run:
            table = self._apply_changes_to_table(table, changes)

        avg_deg = 0.0
        if changes:
            avg_deg = sum(abs(float(c.get("delta_deg", 0.0))) for c in changes) / len(changes)

        return {
            "status": "ok",
            "table_name": table_name,
            "base_table": table,
            "rpm_axis": rpm_axis,
            "map_axis": map_axis,
            "changes": changes,
            "warnings": [],
            "global_stats": global_stats,
            "summary": {
                "cells_tuned": len(changes),
                "avg_correction_deg": round(avg_deg, 4),
            },
            "requires_confirmation": True,
        }

    def _run_wue_analyze(self, run_id: str, params: Dict[str, Any], mode: str, dry_run: bool, progress: List[str]) -> Dict[str, Any]:
        samples = self._resolve_samples(params)
        warm_ect = float(params.get("warmup_ect_threshold", 70.0))
        target_afr = float(params.get("warmup_target_afr", 13.5))
        max_pct = min(float(params.get("max_change_pct", MODE_LIMITS.get(mode, 10.0))), MODE_LIMITS.get(mode, 10.0))

        ect_bins: Dict[int, List[float]] = {}
        for row in samples:
            ect = float(row.get("ECT_C", row.get("CLT", 90.0)) or 90.0)
            if ect >= warm_ect:
                continue
            afr = float(row.get("AFR", row.get("Lambda", target_afr)) or target_afr)
            bin_key = int((ect // 5) * 5)
            ect_bins.setdefault(bin_key, []).append(afr)

        changes = []
        for ect_bin, afrs in sorted(ect_bins.items()):
            if not afrs:
                continue
            measured = sum(afrs) / len(afrs)
            err = (measured - target_afr) / max(0.001, target_afr)
            delta_pct = max(-max_pct, min(max_pct, -err * 100.0))
            changes.append(
                {
                    "axis": "ECT_C",
                    "bin": ect_bin,
                    "before": 100.0,
                    "after": round(100.0 * (1.0 + delta_pct / 100.0), 3),
                    "delta_pct": round(delta_pct, 3),
                    "samples": len(afrs),
                    "reason": "WUE warmup correction",
                    "vetoed": False,
                }
            )

        self._log_adjustments(run_id, "WUE", changes)

        return {
            "status": "ok",
            "table_name": "WUE",
            "changes": changes,
            "warnings": [] if changes else ["No warmup data detected in selected samples."],
            "summary": {
                "cells_tuned": len(changes),
                "avg_correction_pct": round(self._avg_abs_pct(changes), 3),
            },
        }

    def _run_trim_table(self, run_id: str, params: Dict[str, Any], mode: str, dry_run: bool, progress: List[str]) -> Dict[str, Any]:
        samples = self._resolve_samples(params)
        target_afr_default = float(params.get("target_afr", 14.0))
        max_pct = min(float(params.get("max_change_pct", MODE_LIMITS.get(mode, 10.0))), MODE_LIMITS.get(mode, 10.0))

        iat_buckets: Dict[int, List[float]] = {}
        baro_buckets: Dict[int, List[float]] = {}

        for row in samples:
            afr = float(row.get("AFR", target_afr_default) or target_afr_default)
            target = float(row.get("TargetAFR", target_afr_default) or target_afr_default)
            err_pct = ((afr - target) / max(0.001, target)) * 100.0

            iat = int((float(row.get("IAT_C", 20.0) or 20.0) // 5) * 5)
            baro = int((float(row.get("Baro_kPa", row.get("MAP_kPa", 100.0)) or 100.0) // 5) * 5)
            iat_buckets.setdefault(iat, []).append(err_pct)
            baro_buckets.setdefault(baro, []).append(err_pct)

        changes = []
        for src, name in ((iat_buckets, "IAT_C"), (baro_buckets, "Baro_kPa")):
            for key, vals in sorted(src.items()):
                avg = sum(vals) / max(1, len(vals))
                delta_pct = max(-max_pct, min(max_pct, -avg))
                changes.append(
                    {
                        "axis": name,
                        "bin": key,
                        "before": 100.0,
                        "after": round(100.0 * (1.0 + delta_pct / 100.0), 3),
                        "delta_pct": round(delta_pct, 3),
                        "samples": len(vals),
                        "reason": "Trim table correction",
                        "vetoed": False,
                    }
                )

        self._log_adjustments(run_id, "TRIM", changes)
        return {
            "status": "ok",
            "table_name": "TRIM",
            "changes": changes,
            "warnings": [] if changes else ["No valid samples for trim table."],
            "summary": {
                "cells_tuned": len(changes),
                "avg_correction_pct": round(self._avg_abs_pct(changes), 3),
            },
        }

    def _load_table_matrix(self, table_name: str, params: Dict[str, Any]) -> List[List[float]]:
        table = params.get("base_table")
        if isinstance(table, list) and table and isinstance(table[0], list):
            return [[float(v) for v in row] for row in table]

        if hasattr(self.client, "is_connected") and self.client.is_connected() and hasattr(self.client, "read_table"):
            raw = self.client.read_table(table_name)
            if raw:
                side = int(math.sqrt(len(raw)))
                if side * side == len(raw):
                    matrix = []
                    for r in range(side):
                        row = [float(raw[r * side + c]) for c in range(side)]
                        matrix.append(row)
                    return matrix

        default_rows = int(params.get("rows", 16))
        default_cols = int(params.get("cols", 16))
        return [[100.0 for _ in range(default_cols)] for _ in range(default_rows)]

    def _resolve_axis(self, axis: Any, size: int, start: float, step: float) -> List[float]:
        if isinstance(axis, list) and len(axis) == size:
            return [float(v) for v in axis]
        return [float(start + i * step) for i in range(size)]

    def _resolve_samples(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = params.get("samples")
        if isinstance(rows, list) and rows:
            return [r for r in rows if isinstance(r, dict)]

        # Fallback to synthetic data when ECU/log is unavailable.
        out: List[Dict[str, Any]] = []
        ts = time.time()
        for i in range(2000):
            rpm = 1200.0 + (i % 120) * 45.0
            map_kpa = 35.0 + (i % 16) * 10.0
            target = 14.7 if map_kpa < 85 else 12.4
            afr = target + (math.sin(i / 37.0) * 0.25)
            out.append(
                {
                    "timestamp": ts + (i * 0.05),
                    "RPM": rpm,
                    "MAP_kPa": map_kpa,
                    "AFR": afr,
                    "TargetAFR": target,
                    "TPS": float((i * 3) % 100),
                    "KnockCount": 0.0 if i % 250 else 1.0,
                    "InjectorDuty_pct": 50.0 + ((map_kpa - 30.0) / 2.0),
                    "IgnitionTiming": 14.0 + (rpm / 1800.0),
                    "ECT_C": 65.0 + ((i % 300) / 12.0),
                    "IAT_C": 25.0 + ((i % 200) / 15.0),
                }
            )
        return out

    def _build_cell_stats(
        self,
        samples: List[Dict[str, Any]],
        rpm_axis: List[float],
        map_axis: List[float],
        filters: Dict[str, Any],
    ) -> Tuple[Dict[Tuple[int, int], Dict[str, float]], Dict[str, float]]:
        stats: Dict[Tuple[int, int], Dict[str, float]] = {}
        prev: Optional[Dict[str, float]] = None
        knock_events = 0.0

        for row in samples:
            rpm = float(row.get("RPM", 0.0) or 0.0)
            map_kpa = float(row.get("MAP_kPa", 0.0) or 0.0)
            afr = float(row.get("AFR", row.get("Lambda", 0.0)) or 0.0)
            target = float(row.get("TargetAFR", 14.7 if map_kpa < 85 else 12.4) or 14.7)
            tps = float(row.get("TPS", 0.0) or 0.0)
            knock = float(row.get("KnockCount", 0.0) or 0.0)
            duty = float(row.get("InjectorDuty_pct", 0.0) or 0.0)
            ign = float(row.get("IgnitionTiming", 0.0) or 0.0)

            if prev is not None:
                if filters.get("ignore_transient") and abs(tps - prev["tps"]) > float(filters.get("tps_transient_delta", 5.0)):
                    prev = {"rpm": rpm, "tps": tps}
                    continue
                if filters.get("steady_state_only") and abs(rpm - prev["rpm"]) > float(filters.get("rpm_variance", 100.0)):
                    prev = {"rpm": rpm, "tps": tps}
                    continue

            prev = {"rpm": rpm, "tps": tps}
            if knock > 0:
                knock_events += knock

            r = self._nearest_idx(rpm_axis, rpm)
            c = self._nearest_idx(map_axis, map_kpa)
            key = (c, r)  # row=MAP, col=RPM

            cur = stats.get(
                key,
                {
                    "samples": 0.0,
                    "afr_sum": 0.0,
                    "target_sum": 0.0,
                    "duty_sum": 0.0,
                    "knock_sum": 0.0,
                    "ign_sum": 0.0,
                },
            )
            cur["samples"] += 1.0
            cur["afr_sum"] += afr
            cur["target_sum"] += target
            cur["duty_sum"] += duty
            cur["knock_sum"] += knock
            cur["ign_sum"] += ign
            stats[key] = cur

        out: Dict[Tuple[int, int], Dict[str, float]] = {}
        for key, v in stats.items():
            s = max(1.0, v["samples"])
            out[key] = {
                "samples": v["samples"],
                "afr_avg": v["afr_sum"] / s,
                "target_afr_avg": v["target_sum"] / s,
                "duty_avg": v["duty_sum"] / s,
                "knock_sum": v["knock_sum"],
                "ign_avg": v["ign_sum"] / s,
            }

        global_stats = {
            "total_samples": float(len(samples)),
            "knock_events": knock_events,
            "cells": float(len(out)),
        }
        return out, global_stats

    def _nearest_idx(self, axis: List[float], value: float) -> int:
        if not axis:
            return 0
        return min(range(len(axis)), key=lambda i: abs(float(axis[i]) - float(value)))

    def _find_missing_cells(self, rows: int, cols: int, stats: Dict[Tuple[int, int], Dict[str, float]], min_samples: int) -> List[Tuple[int, int]]:
        missing = []
        for r in range(rows):
            for c in range(cols):
                entry = stats.get((r, c))
                if not entry or int(entry.get("samples", 0)) < min_samples:
                    missing.append((r, c))
        return missing

    def _interpolate_missing_cells(
        self,
        table: List[List[float]],
        changes: List[Dict[str, Any]],
        missing: List[Tuple[int, int]],
        max_pct: float,
    ) -> List[Dict[str, Any]]:
        if not table or not missing:
            return []

        by_cell = {(int(c["row"]), int(c["col"])): float(c.get("delta_pct", 0.0)) for c in changes}
        rows = len(table)
        cols = len(table[0]) if rows else 0
        out = []

        for r, c in missing:
            nbr = []
            for rr in range(max(0, r - 1), min(rows, r + 2)):
                for cc in range(max(0, c - 1), min(cols, c + 2)):
                    if (rr, cc) in by_cell:
                        nbr.append(by_cell[(rr, cc)])
            if not nbr:
                continue
            delta_pct = sum(nbr) / len(nbr)
            delta_pct = max(-max_pct, min(max_pct, delta_pct))
            before = float(table[r][c])
            after = before * (1.0 + delta_pct / 100.0)
            out.append(
                {
                    "row": r,
                    "col": c,
                    "before": round(before, 4),
                    "after": round(after, 4),
                    "delta": round(after - before, 4),
                    "delta_pct": round(delta_pct, 3),
                    "samples": 0,
                    "reason": "Interpolated from neighbors",
                    "vetoed": False,
                    "veto_reason": "",
                }
            )

        return out

    def _apply_changes_to_table(self, table: List[List[float]], changes: List[Dict[str, Any]]) -> List[List[float]]:
        out = copy.deepcopy(table)
        for ch in changes:
            r = int(ch.get("row", -1))
            c = int(ch.get("col", -1))
            if r < 0 or c < 0 or r >= len(out) or c >= len(out[r]):
                continue
            if ch.get("vetoed"):
                continue
            out[r][c] = float(ch.get("after", out[r][c]))
        return out

    def _avg_abs_pct(self, changes: List[Dict[str, Any]]) -> float:
        vals = [abs(float(c.get("delta_pct", 0.0) or 0.0)) for c in changes if "delta_pct" in c]
        if not vals:
            return 0.0
        return sum(vals) / len(vals)

    def _log_run_start(self, run_id: str, tool_name: str, mode: str, dry_run: bool) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO autotune_runs(run_id, tool_name, started_at, mode, dry_run, status, summary_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, tool_name, time.time(), mode, 1 if dry_run else 0, "running", "{}"),
            )
            conn.commit()
        finally:
            conn.close()

    def _log_adjustments(self, run_id: str, table_name: str, changes: List[Dict[str, Any]]) -> None:
        if not changes:
            return
        conn = self._connect()
        now = time.time()
        try:
            rows = []
            for c in changes:
                rows.append(
                    (
                        run_id,
                        table_name,
                        int(c.get("row", c.get("bin", -1))),
                        int(c.get("col", -1)),
                        float(c.get("before", 0.0) or 0.0),
                        float(c.get("after", 0.0) or 0.0),
                        float(c.get("delta", 0.0) or 0.0),
                        float(c.get("delta_pct", c.get("delta_deg", 0.0)) or 0.0),
                        str(c.get("reason", ""))[:240],
                        1 if c.get("vetoed") else 0,
                        now,
                    )
                )
            conn.executemany(
                """
                INSERT INTO autotune_adjustments(
                    run_id, table_name, row_idx, col_idx, before_value, after_value,
                    delta_value, delta_pct, reason, vetoed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
        finally:
            conn.close()

    def _log_run_end(self, run_id: str, status: str, summary: Dict[str, Any]) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE autotune_runs
                SET completed_at = ?, status = ?, summary_json = ?
                WHERE run_id = ?
                """,
                (time.time(), status, json.dumps(summary), run_id),
            )
            conn.commit()
        finally:
            conn.close()
