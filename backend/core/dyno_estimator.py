import math
import time
from typing import Any, Dict, List, Tuple


class DynoEstimator:
    """
    Estimate power/torque curves from datalog rows using conservative physics-inspired heuristics.
    Includes correction factors, smoothing, mode handling, and safety warning logic.
    """

    def __init__(self) -> None:
        pass

    def estimate(self, rows: List[Dict[str, Any]], params: Dict[str, Any], mode: str = "ramp") -> Dict[str, Any]:
        mode = (mode or "ramp").strip().lower()
        units = (params.get("units") or "imperial").strip().lower()
        displacement_l = float(params.get("displacement_l", 2.0) or 2.0)
        drivetrain_loss = float(params.get("drivetrain_loss", 0.15) or 0.15)
        drivetrain_loss = max(0.0, min(0.3, drivetrain_loss))
        efficiency = float(params.get("efficiency", 0.88) or 0.88)
        efficiency = max(0.5, min(1.1, efficiency))
        smoothing_window = int(params.get("smoothing_window", 7) or 7)
        smoothing_window = max(1, min(31, smoothing_window))
        redline_rpm = float(params.get("redline_rpm", 8200) or 8200)
        fuel_type = (params.get("fuel_type") or "gas93").strip().lower()

        if not rows:
            return {
                "status": "empty",
                "mode": mode,
                "units": units,
                "curves": [],
                "warnings": ["No dyno input data available."],
                "peaks": {},
                "auc_power": 0.0,
            }

        # Downsample very large logs for graph responsiveness.
        if len(rows) > 15000:
            step = max(1, len(rows) // 15000)
            rows = rows[::step]

        warnings: List[str] = []
        unsafe = False
        missing_channels = self._detect_missing_channels(rows)
        if missing_channels:
            warnings.append(f"Missing channels for accurate estimate: {', '.join(missing_channels)}")

        points: List[Dict[str, float]] = []
        for row in rows:
            rpm = float(row.get("RPM", 0.0) or 0.0)
            map_kpa = float(row.get("MAP_kPa", row.get("MAP", 100.0)) or 100.0)
            afr = float(row.get("AFR", row.get("Lambda", 14.7)) or 14.7)
            iat_c = float(row.get("IAT_C", row.get("IAT", 30.0)) or 30.0)
            ect_c = float(row.get("ECT_C", row.get("CLT", 90.0)) or 90.0)
            ign = float(row.get("IgnitionTiming", row.get("advance", 12.0)) or 12.0)
            knock = float(row.get("KnockCount", 0.0) or 0.0)
            boost_kpa = max(0.0, map_kpa - 100.0)
            tps = float(row.get("TPS", 50.0) or 50.0)
            ve = float(row.get("VE", 85.0) or 85.0)
            baro_kpa = float(row.get("Baro_kPa", 99.0) or 99.0)

            if rpm <= 0.0:
                continue

            corr = self._sae_correction(iat_c, baro_kpa)
            temp_comp = self._thermal_comp(iat_c, ect_c)
            fuel_comp = self._fuel_comp(fuel_type, afr)
            ign_comp = 1.0 + max(-0.12, min(0.06, (ign - 12.0) * 0.004))

            # Base torque model: VE/load/displacement combined with calibrated factor.
            ve_frac = max(0.3, min(1.4, ve / 100.0))
            load_frac = max(0.15, min(2.2, map_kpa / 100.0))
            throttle_frac = max(0.1, min(1.0, tps / 100.0))
            torque_nm_engine = ve_frac * load_frac * displacement_l * 170.0 * efficiency * corr * temp_comp * fuel_comp * ign_comp * throttle_frac

            if mode == "coast":
                # Coast-down implies decel/no-throttle drag profile.
                torque_nm_engine *= 0.2
            elif mode == "steady":
                # Steady-state damping to reduce spikes.
                torque_nm_engine *= 0.92

            if knock > 0:
                torque_nm_engine *= max(0.7, 1.0 - min(0.25, knock * 0.04))
            if knock >= 4:
                unsafe = True

            torque_nm_wheel = torque_nm_engine * (1.0 - drivetrain_loss)
            hp = self._nm_to_ftlb(torque_nm_wheel) * rpm / 5252.0

            points.append(
                {
                    "rpm": rpm,
                    "torque_nm": torque_nm_wheel,
                    "torque_ftlb": self._nm_to_ftlb(torque_nm_wheel),
                    "hp": hp,
                    "kw": hp * 0.745699872,
                    "afr": afr,
                    "boost_kpa": boost_kpa,
                    "knock": knock,
                }
            )

            if rpm >= redline_rpm:
                warnings.append(f"Redline warning: data reached {rpm:.0f} RPM")
                break

        if not points:
            return {
                "status": "empty",
                "mode": mode,
                "units": units,
                "curves": [],
                "warnings": ["No valid RPM samples."],
                "peaks": {},
                "auc_power": 0.0,
            }

        points = self._sort_by_rpm(points)
        points = self._smooth_points(points, window=smoothing_window)
        points = self._collapse_duplicate_rpm(points)

        # Extrapolate incomplete runs.
        target_end = float(params.get("end_rpm", 0.0) or 0.0)
        if target_end > 0 and points[-1]["rpm"] < target_end * 0.95 and len(points) > 3:
            ext = self._extrapolate_tail(points, target_end)
            if ext:
                points.extend(ext)
                warnings.append("Run ended early; peak region partially extrapolated.")

        if unsafe:
            warnings.append("Unsafe dyno condition detected (high knock). Abort dyno test.")

        peaks = self._compute_peaks(points)
        auc_power = self._auc(points, y_key="hp")

        curves = []
        for p in points:
            if units == "metric":
                curves.append(
                    {
                        "rpm": p["rpm"],
                        "power": p["kw"],
                        "torque": p["torque_nm"],
                        "afr": p["afr"],
                        "boost_kpa": p["boost_kpa"],
                        "knock": p["knock"],
                    }
                )
            else:
                curves.append(
                    {
                        "rpm": p["rpm"],
                        "power": p["hp"],
                        "torque": p["torque_ftlb"],
                        "afr": p["afr"],
                        "boost_kpa": p["boost_kpa"],
                        "knock": p["knock"],
                    }
                )

        return {
            "status": "ok",
            "mode": mode,
            "units": units,
            "curves": curves,
            "warnings": list(dict.fromkeys(warnings))[:10],
            "peaks": peaks if units == "imperial" else self._metric_peaks(peaks),
            "auc_power": auc_power if units == "imperial" else auc_power * 0.745699872,
            "summary": {
                "samples": len(curves),
                "peak_power": peaks.get("peak_hp", 0.0) if units == "imperial" else peaks.get("peak_kw", 0.0),
                "peak_power_rpm": peaks.get("peak_hp_rpm", 0.0),
                "peak_torque": peaks.get("peak_torque_ftlb", 0.0) if units == "imperial" else peaks.get("peak_torque_nm", 0.0),
                "peak_torque_rpm": peaks.get("peak_torque_rpm", 0.0),
            },
        }

    def stream_ramp(self, client: Any, mode: str, params: Dict[str, Any]):
        start_rpm = float(params.get("start_rpm", 2000) or 2000)
        end_rpm = float(params.get("end_rpm", 8000) or 8000)
        ramp_sec = float(params.get("ramp_seconds", 10) or 10)
        ramp_sec = max(2.0, min(40.0, ramp_sec))
        steps = max(20, int(ramp_sec * 10))

        rows: List[Dict[str, Any]] = []
        t0 = time.time()
        for i in range(steps + 1):
            frac = i / float(steps)
            rpm_target = start_rpm + (end_rpm - start_rpm) * frac

            live: Dict[str, Any] = {}
            if hasattr(client, "is_connected") and client.is_connected() and hasattr(client, "get_live_data"):
                try:
                    live = client.get_live_data() or {}
                except Exception:
                    live = {}

            if live:
                rpm = float(live.get("RPM", rpm_target) or rpm_target)
                row = {
                    "timestamp": time.time(),
                    "RPM": rpm,
                    "MAP_kPa": float(live.get("MAP_kPa", 100 + 80 * frac) or (100 + 80 * frac)),
                    "AFR": float(live.get("AFR", 14.2 - (2.0 * frac)) or (14.2 - (2.0 * frac))),
                    "IAT_C": float(live.get("IAT_C", 30 + 10 * frac) or (30 + 10 * frac)),
                    "ECT_C": float(live.get("ECT_C", 85 + 5 * frac) or (85 + 5 * frac)),
                    "IgnitionTiming": float(live.get("IgnitionTiming", 14 + 3 * frac) or (14 + 3 * frac)),
                    "KnockCount": float(live.get("KnockCount", 0) or 0),
                    "InjectorDuty_pct": float(live.get("InjectorDuty_pct", 45 + 45 * frac) or (45 + 45 * frac)),
                    "TPS": 95.0,
                }
            else:
                row = {
                    "timestamp": time.time(),
                    "RPM": rpm_target,
                    "MAP_kPa": 95 + 90 * frac,
                    "AFR": 14.4 - (2.4 * frac),
                    "IAT_C": 28 + 9 * frac,
                    "ECT_C": 86 + 6 * frac,
                    "IgnitionTiming": 13 + 4 * frac,
                    "KnockCount": 0.0 if i % 40 else 1.0,
                    "InjectorDuty_pct": 40 + 50 * frac,
                    "TPS": 95.0,
                }

            rows.append(row)
            result = self.estimate(rows, params, mode=mode)
            curve = result.get("curves", [])
            latest = curve[-1] if curve else {}
            yield {
                "step": i,
                "steps": steps,
                "elapsed": time.time() - t0,
                "latest": latest,
                "warnings": result.get("warnings", []),
            }

            if latest.get("knock", 0) and latest.get("knock", 0) >= 4:
                break
            time.sleep(ramp_sec / steps)

    def _detect_missing_channels(self, rows: List[Dict[str, Any]]) -> List[str]:
        if not rows:
            return []
        need = ["RPM", "MAP_kPa", "AFR", "IAT_C", "ECT_C", "IgnitionTiming", "KnockCount", "TPS"]
        head = rows[0]
        missing = []
        for k in need:
            if k not in head:
                missing.append(k)
        return missing

    def _sae_correction(self, iat_c: float, baro_kpa: float) -> float:
        temp_k = max(240.0, iat_c + 273.15)
        baro = max(70.0, min(110.0, baro_kpa))
        return (99.0 / baro) * math.sqrt(298.0 / temp_k)

    def _thermal_comp(self, iat_c: float, ect_c: float) -> float:
        iat_pen = max(0.0, iat_c - 35.0) * 0.004
        ect_pen = max(0.0, ect_c - 95.0) * 0.003
        return max(0.75, 1.0 - iat_pen - ect_pen)

    def _fuel_comp(self, fuel_type: str, afr: float) -> float:
        if fuel_type.startswith("e85"):
            return 1.03 if afr < 12.0 else 0.99
        return 1.0 if afr < 14.8 else 0.97

    def _nm_to_ftlb(self, nm: float) -> float:
        return nm * 0.737562149

    def _sort_by_rpm(self, points: List[Dict[str, float]]) -> List[Dict[str, float]]:
        return sorted(points, key=lambda x: x.get("rpm", 0.0))

    def _smooth_points(self, points: List[Dict[str, float]], window: int) -> List[Dict[str, float]]:
        if window <= 1 or len(points) < 5:
            return points
        out = []
        half = window // 2
        for i in range(len(points)):
            lo = max(0, i - half)
            hi = min(len(points), i + half + 1)
            chunk = points[lo:hi]
            p = dict(points[i])
            for key in ("hp", "kw", "torque_nm", "torque_ftlb", "afr", "boost_kpa"):
                p[key] = sum(c[key] for c in chunk) / len(chunk)
            out.append(p)
        return out

    def _collapse_duplicate_rpm(self, points: List[Dict[str, float]]) -> List[Dict[str, float]]:
        buckets: Dict[int, List[Dict[str, float]]] = {}
        for p in points:
            k = int(round(p["rpm"]))
            buckets.setdefault(k, []).append(p)
        out = []
        for rpm in sorted(buckets.keys()):
            chunk = buckets[rpm]
            if len(chunk) == 1:
                out.append(chunk[0])
                continue
            avg = dict(chunk[0])
            for key in ("hp", "kw", "torque_nm", "torque_ftlb", "afr", "boost_kpa", "knock"):
                avg[key] = sum(c[key] for c in chunk) / len(chunk)
            avg["rpm"] = float(rpm)
            out.append(avg)
        return out

    def _extrapolate_tail(self, points: List[Dict[str, float]], target_end_rpm: float) -> List[Dict[str, float]]:
        if len(points) < 4:
            return []
        last = points[-1]
        prev = points[-4]
        dr = max(1.0, last["rpm"] - prev["rpm"])
        hp_slope = (last["hp"] - prev["hp"]) / dr
        tq_slope = (last["torque_ftlb"] - prev["torque_ftlb"]) / dr
        step = 150.0
        out = []
        rpm = last["rpm"] + step
        while rpm <= target_end_rpm and len(out) < 25:
            hp = max(0.0, last["hp"] + hp_slope * (rpm - last["rpm"]))
            tq = max(0.0, last["torque_ftlb"] + tq_slope * (rpm - last["rpm"]))
            out.append(
                {
                    "rpm": rpm,
                    "torque_nm": tq / 0.737562149,
                    "torque_ftlb": tq,
                    "hp": hp,
                    "kw": hp * 0.745699872,
                    "afr": last["afr"],
                    "boost_kpa": last["boost_kpa"],
                    "knock": last["knock"],
                }
            )
            rpm += step
        return out

    def _compute_peaks(self, points: List[Dict[str, float]]) -> Dict[str, float]:
        if not points:
            return {}
        p_hp = max(points, key=lambda x: x.get("hp", 0.0))
        p_tq = max(points, key=lambda x: x.get("torque_ftlb", 0.0))
        return {
            "peak_hp": round(p_hp["hp"], 3),
            "peak_hp_rpm": round(p_hp["rpm"], 1),
            "peak_kw": round(p_hp["kw"], 3),
            "peak_torque_ftlb": round(p_tq["torque_ftlb"], 3),
            "peak_torque_nm": round(p_tq["torque_nm"], 3),
            "peak_torque_rpm": round(p_tq["rpm"], 1),
        }

    def _metric_peaks(self, peaks: Dict[str, float]) -> Dict[str, float]:
        return {
            "peak_kw": peaks.get("peak_kw", 0.0),
            "peak_hp_rpm": peaks.get("peak_hp_rpm", 0.0),
            "peak_torque_nm": peaks.get("peak_torque_nm", 0.0),
            "peak_torque_rpm": peaks.get("peak_torque_rpm", 0.0),
        }

    def _auc(self, points: List[Dict[str, float]], y_key: str) -> float:
        if len(points) < 2:
            return 0.0
        area = 0.0
        for i in range(1, len(points)):
            x0 = points[i - 1]["rpm"]
            x1 = points[i]["rpm"]
            y0 = points[i - 1][y_key]
            y1 = points[i][y_key]
            area += (x1 - x0) * (y0 + y1) * 0.5
        return round(max(0.0, area), 3)
