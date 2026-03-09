import json
import os
from typing import List, Tuple, Optional
from ..schemas import AnalysisRequest, Recommendation

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def _load_json(rel_path: str) -> Optional[dict]:
    full = os.path.join(DATA_DIR, rel_path)
    if os.path.exists(full):
        with open(full, "r") as f:
            return json.load(f)
    return None


class GuardrailEngine:
    """
    Enhanced guardrail engine backed by curated safety datasets.
    Enforces knock limits, injector duty, VTEC transition safety,
    safe tuning ranges, and stoichiometric validation.
    """

    def __init__(self, request: AnalysisRequest):
        self.request = request
        self.profile = request.vehicle_profile
        self.opts = request.options

        # Load dataset-backed limits
        self.knock_data = _load_json("sensors/LSVTEC/knock_thresholds.json")
        self.safe_ranges = _load_json("historical/B18C_LSVTEC/safe_tuning_ranges.json")
        self.vtec_data = _load_json("historical/B18C_LSVTEC/vtec_transition.json")
        self.wideband_data = _load_json("sensors/LSVTEC/wideband_o2_calibration.json")
        self.short_pulse_data = _load_json("injectors/B18C/short_pulse_adder.json")

    def _get_datalog_cell(self, rpm_idx: int, map_idx: int):
        for cell in self.request.datalog_summary.cells:
            if cell.rpm_index == rpm_idx and cell.map_index == map_idx:
                return cell
        return None

    def _get_rpm_at_index(self, rpm_idx: int) -> float:
        axes = self.request.calibration.axes
        if "rpm" in axes and rpm_idx < len(axes["rpm"]):
            return axes["rpm"][rpm_idx]
        return 0.0

    def _get_map_at_index(self, map_idx: int) -> float:
        axes = self.request.calibration.axes
        if "map_kpa" in axes and map_idx < len(axes["map_kpa"]):
            return axes["map_kpa"][map_idx]
        return 0.0

    def _get_safe_range_key(self) -> str:
        is_turbo = self.profile.aspiration == "turbo"
        is_e85 = self.profile.fuel_type == "e85"
        if is_turbo and is_e85:
            return "turbo_e85"
        elif is_turbo:
            return "turbo_93oct"
        else:
            return "na_93oct"

    # ── RULE: Knock Threshold ────────────────────────────────
    def _check_knock_limit(self, rec: Recommendation, rpm: float) -> Tuple[bool, str]:
        if not self.knock_data or rec.delta_ign_deg <= 0:
            return True, ""

        fuel_key = "fuel_e85" if self.profile.fuel_type == "e85" else "fuel_93oct"
        fuel_data = self.knock_data.get(fuel_key, {})
        rpm_bins = fuel_data.get("rpm_bins", [])
        thresholds = fuel_data.get("knock_threshold_deg", [])

        if not rpm_bins:
            return True, ""

        # Find nearest RPM bin
        closest_idx = min(range(len(rpm_bins)), key=lambda i: abs(rpm_bins[i] - rpm))
        max_advance = thresholds[closest_idx]

        # Get current ignition value at this cell
        ign_table = self.request.calibration.ignition_table
        if rec.rpm_index < len(ign_table) and rec.map_index < len(ign_table[rec.rpm_index]):
            current_ign = ign_table[rec.rpm_index][rec.map_index]
            proposed_ign = current_ign + rec.delta_ign_deg

            if proposed_ign > max_advance:
                rec.delta_ign_deg = max(0.0, max_advance - current_ign)
                return False, f"Ignition clamped: {proposed_ign:.1f}° exceeds knock limit {max_advance}° at {rpm:.0f} RPM"

        return True, ""

    # ── RULE: Safe Tuning Ranges ──────────────────────────────
    def _check_safe_ranges(self, rec: Recommendation, rpm: float, map_kpa: float) -> Tuple[bool, str]:
        if not self.safe_ranges:
            return True, ""

        key = self._get_safe_range_key()
        ranges = self.safe_ranges.get(key, {})
        if not ranges:
            return True, ""

        # Check max ignition at WOT
        max_ign = ranges.get("max_ignition_wot_deg")
        if max_ign and map_kpa > 90:
            ign_table = self.request.calibration.ignition_table
            if rec.rpm_index < len(ign_table) and rec.map_index < len(ign_table[rec.rpm_index]):
                proposed = ign_table[rec.rpm_index][rec.map_index] + rec.delta_ign_deg
                if proposed > max_ign:
                    rec.delta_ign_deg = max(0.0, max_ign - ign_table[rec.rpm_index][rec.map_index])
                    return False, f"Ignition clamped to safe WOT max {max_ign}° for {key}"

        return True, ""

    # ── RULE: VTEC Transition Safety ──────────────────────────
    def _check_vtec_transition(self, rec: Recommendation, rpm: float) -> Tuple[bool, str]:
        if not self.vtec_data:
            return True, ""

        key = "ls_vtec_turbo_93oct" if self.profile.aspiration == "turbo" else "ls_vtec_na_93oct"
        vtec = self.vtec_data.get(key, {})
        engage_rpm = vtec.get("vtec_engagement_rpm", 5800)
        hysteresis = vtec.get("hysteresis_rpm", 400)

        # If this cell is in the VTEC transition window
        if abs(rpm - engage_rpm) <= hysteresis / 2:
            ign_corr = vtec.get("ignition_correction", {})
            max_retard = ign_corr.get("transient_retard_deg", 2.0)

            if rec.delta_ign_deg > 0:
                rec.delta_ign_deg = 0.0
                return False, f"Ignition advance blocked in VTEC transition zone ({engage_rpm}±{hysteresis//2} RPM)"

        return True, ""

    # ── RULE: Stoichiometric Validation ───────────────────────
    def _check_stoich(self, rec: Recommendation) -> Tuple[bool, str]:
        if not self.wideband_data:
            return True, ""

        stoich = self.wideband_data.get("stoichiometric_ratios", {})
        if self.profile.fuel_type == "e85":
            expected_stoich = stoich.get("e85", {}).get("stoich_afr", 9.76)
        else:
            expected_stoich = stoich.get("gasoline_pump", {}).get("stoich_afr", 14.7)

        # If fuel correction would push AFR dangerously lean at WOT
        cell_data = self._get_datalog_cell(rec.rpm_index, rec.map_index)
        if cell_data and cell_data.measured_afr:
            map_kpa = self._get_map_at_index(rec.map_index)
            if map_kpa > 90:  # WOT zone
                projected_afr = cell_data.measured_afr * (1 + rec.delta_fuel_pct / 100.0)
                # Lean limit: stoich - safety margin
                lean_limit = expected_stoich * 0.92 if self.profile.aspiration == "turbo" else expected_stoich * 0.95
                if projected_afr > lean_limit and rec.delta_fuel_pct > 0:
                    return False, f"Fuel reduction would push AFR to {projected_afr:.1f}, exceeding lean safety limit {lean_limit:.1f}"

        return True, ""

    # ── Core validation (original rules + new rules) ──────────
    def validate_recommendation(self, rec: Recommendation) -> Tuple[bool, str]:
        cell_data = self._get_datalog_cell(rec.rpm_index, rec.map_index)
        rpm = self._get_rpm_at_index(rec.rpm_index)
        map_kpa = self._get_map_at_index(rec.map_index)

        # Original Rule 4: Occupancy check
        if cell_data and cell_data.occupied_pct < 3.0:
            return False, "Cell occupancy below 3% threshold"

        # Original Rule 3: Knock ignition lock
        if cell_data and cell_data.knock_count > 0:
            if rec.delta_ign_deg > 0:
                rec.delta_ign_deg = 0.0
                return False, "Ignition increase suppressed due to historical knock in cell"

        # NEW: Dataset-backed knock threshold
        ok, msg = self._check_knock_limit(rec, rpm)
        if not ok:
            return False, msg

        # NEW: Safe tuning range enforcement
        ok, msg = self._check_safe_ranges(rec, rpm, map_kpa)
        if not ok:
            return False, msg

        # NEW: VTEC transition safety
        ok, msg = self._check_vtec_transition(rec, rpm)
        if not ok:
            return False, msg

        # NEW: Stoichiometric validation
        ok, msg = self._check_stoich(rec)
        if not ok:
            return False, msg

        # Original Rule 2: Per-cell max delta clamp (fuel)
        if abs(rec.delta_fuel_pct) > self.opts.max_fuel_delta_pct:
            clamped = float(self.opts.max_fuel_delta_pct)
            rec.delta_fuel_pct = -clamped if rec.delta_fuel_pct < 0 else clamped

        # Original Rule 2: Per-cell max delta clamp (ignition)
        if abs(rec.delta_ign_deg) > self.opts.max_ignition_delta_deg:
            clamped = float(self.opts.max_ignition_delta_deg)
            rec.delta_ign_deg = -clamped if rec.delta_ign_deg < 0 else clamped

        # Original Rule 6: Auto-apply mode (fuel only)
        if self.opts.mode == "limited_auto_apply":
            if rec.delta_ign_deg != 0:
                rec.delta_ign_deg = 0
                return False, "Ignition changes not allowed in auto-apply mode"

        # Original Rule 5: Thermal limits
        if cell_data and (cell_data.iat_c > 65 or cell_data.ect_c > 105):
            if rec.delta_ign_deg > 0:
                rec.delta_ign_deg = 0
                return False, "Ignition increase suppressed due to high temperatures"

        return True, "Passed"

    def run_all_guardrails(self, raw_recommendations: List[Recommendation]) -> Tuple[List[Recommendation], List[str]]:
        validated = []
        warnings = []

        # Rule 1: Global injector duty clamp
        if self.request.datalog_summary.global_stats.max_injector_duty_pct > 85.0:
            warnings.append("WARNING: Injector duty exceeded 85% safe threshold. Fuel increases limited.")

        for rec in raw_recommendations:
            # Injector constraint: block fuel adds if duty > 85%
            if rec.delta_fuel_pct > 0 and self.request.datalog_summary.global_stats.max_injector_duty_pct > 85.0:
                rec.delta_fuel_pct = 0.0
                warnings.append(f"Suppressed fuel addition at rpm_idx={rec.rpm_index}, map_idx={rec.map_index} due to duty limit")

            is_valid, reason = self.validate_recommendation(rec)

            if is_valid:
                validated.append(rec)
            else:
                warnings.append(f"Rejected change at rpm_idx={rec.rpm_index}, map_idx={rec.map_index}: {reason}")

        return validated, warnings
