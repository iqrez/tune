import json
import os
import random
from typing import List, Dict, Optional
from ..schemas import VehicleProfile, CalibrationSnapshot
from .math_engine import DeterministicEngineModel

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def _load_json(rel_path: str) -> Optional[dict]:
    full = os.path.join(DATA_DIR, rel_path)
    if os.path.exists(full):
        with open(full, "r") as f:
            return json.load(f)
    return None


class SafetyTrigger:
    """Represents a single safety abort condition."""
    def __init__(self, name: str, condition_met: bool, value: float, limit: float, action: str):
        self.name = name
        self.condition_met = condition_met
        self.value = value
        self.limit = limit
        self.action = action

    def to_dict(self):
        return {
            "trigger": self.name,
            "fired": self.condition_met,
            "measured_value": round(self.value, 2),
            "limit": round(self.limit, 2),
            "corrective_action": self.action
        }


class PowerRampEngine:
    """
    Staged power ramp simulator.
    
    Gradually increases load through defined stages. At each stage,
    simulates sensor readings and checks safety triggers. Only advances
    if all checks pass for consecutive samples. Aborts immediately
    if any trigger fires.
    """

    def __init__(self, profile: VehicleProfile, calibration: CalibrationSnapshot, target_boost_psi: float = 0.0):
        self.profile = profile
        self.calibration = calibration
        self.engine = DeterministicEngineModel(profile)
        self.target_boost_psi = target_boost_psi
        
        # Load safety limits from datasets
        safe_ranges = _load_json("historical/B18C_LSVTEC/safe_tuning_ranges.json")
        self.safe_ranges = safe_ranges or {}
        
        # Build stages based on aspiration
        self.stages = self._build_stages()

    def _get_range_key(self) -> str:
        is_turbo = self.profile.aspiration == "turbo"
        is_e85 = self.profile.fuel_type == "e85"
        if is_turbo and is_e85:
            return "turbo_e85"
        elif is_turbo:
            return "turbo_93oct"
        else:
            return "na_93oct"

    def _build_stages(self) -> List[Dict]:
        """Define the ramp stages from idle to max power."""
        is_turbo = self.profile.aspiration == "turbo"
        
        stages = [
            {"name": "Stage 1: Idle Check", "rpm": 850, "map_kpa": 40, "boost_psi": 0, "hold_seconds": 3},
            {"name": "Stage 2: Light Cruise", "rpm": 2500, "map_kpa": 55, "boost_psi": 0, "hold_seconds": 3},
            {"name": "Stage 3: Mid Cruise", "rpm": 3500, "map_kpa": 70, "boost_psi": 0, "hold_seconds": 3},
            {"name": "Stage 4: Heavy Load", "rpm": 4500, "map_kpa": 85, "boost_psi": 0, "hold_seconds": 5},
            {"name": "Stage 5: WOT NA", "rpm": 6000, "map_kpa": 100, "boost_psi": 0, "hold_seconds": 5},
        ]

        if is_turbo and self.target_boost_psi > 0:
            # Add boost stages in increments
            boost_step = self.target_boost_psi / 3.0
            stages.extend([
                {"name": "Stage 6: Low Boost", "rpm": 5500, "map_kpa": 100 + boost_step * 6.895, "boost_psi": round(boost_step, 1), "hold_seconds": 5},
                {"name": "Stage 7: Mid Boost", "rpm": 6500, "map_kpa": 100 + boost_step * 2 * 6.895, "boost_psi": round(boost_step * 2, 1), "hold_seconds": 5},
                {"name": "Stage 8: Full Boost", "rpm": 7000, "map_kpa": 100 + self.target_boost_psi * 6.895, "boost_psi": round(self.target_boost_psi, 1), "hold_seconds": 8},
            ])

        return stages

    def _simulate_readings(self, stage: Dict, sample: int) -> Dict:
        """Generate realistic sensor readings for a stage with some noise."""
        rpm = stage["rpm"]
        map_kpa = stage["map_kpa"]
        boost_psi = stage["boost_psi"]
        
        target_afr = self.engine.generate_base_afr_target(float(rpm), float(map_kpa))
        
        # Simulate realistic readings with noise
        measured_afr = target_afr + random.gauss(0, 0.3)
        iat_c = 30.0 + boost_psi * 1.5 + random.gauss(0, 2)  # Boost heats intake
        ect_c = 85.0 + boost_psi * 0.8 + random.gauss(0, 1.5)
        measured_boost = boost_psi + random.gauss(0, 0.3)
        knock_count = 1 if random.random() < 0.02 else 0  # 2% chance of knock
        injector_duty = 40.0 + (rpm / 8000.0) * 30.0 + boost_psi * 2.5 + random.gauss(0, 2)
        
        ign_timing = self.engine.generate_base_ignition_timing(float(rpm), float(map_kpa))
        
        return {
            "rpm": rpm,
            "map_kpa": round(map_kpa, 1),
            "target_afr": round(target_afr, 2),
            "measured_afr": round(measured_afr, 2),
            "iat_c": round(iat_c, 1),
            "ect_c": round(ect_c, 1),
            "measured_boost_psi": round(measured_boost, 1),
            "target_boost_psi": boost_psi,
            "knock_count": knock_count,
            "injector_duty_pct": round(min(100, injector_duty), 1),
            "ignition_timing_deg": round(ign_timing, 1),
            "sample": sample + 1
        }

    def _check_safety_triggers(self, readings: Dict, stage: Dict) -> List[SafetyTrigger]:
        """Evaluate all abort conditions against current readings."""
        triggers = []
        range_key = self._get_range_key()
        safe = self.safe_ranges.get(range_key, {})

        # Trigger 1: Lean AFR spike
        max_afr_wot = safe.get("max_afr_wot", 13.2)
        if stage["map_kpa"] > 85:  # Only check at high load
            triggers.append(SafetyTrigger(
                "LEAN_AFR_SPIKE",
                readings["measured_afr"] > max_afr_wot,
                readings["measured_afr"],
                max_afr_wot,
                "Cut boost, add 5% fuel enrichment, abort ramp"
            ))

        # Trigger 2: Knock detected
        triggers.append(SafetyTrigger(
            "KNOCK_DETECTED",
            readings["knock_count"] > 0,
            float(readings["knock_count"]),
            0,
            "Retard ignition 3°, cut boost to previous stage, abort ramp"
        ))

        # Trigger 3: IAT over-temperature
        iat_limit = 60.0
        triggers.append(SafetyTrigger(
            "IAT_OVERTEMP",
            readings["iat_c"] > iat_limit,
            readings["iat_c"],
            iat_limit,
            "Reduce boost 3 PSI, wait for cooling, abort if persistent"
        ))

        # Trigger 4: ECT over-temperature
        ect_limit = 100.0
        triggers.append(SafetyTrigger(
            "ECT_OVERTEMP",
            readings["ect_c"] > ect_limit,
            readings["ect_c"],
            ect_limit,
            "Abort ramp, reduce load, enable cooling enrichment"
        ))

        # Trigger 5: Boost overshoot (>15% above target)
        if stage["boost_psi"] > 0:
            overshoot_limit = stage["boost_psi"] * 1.15
            triggers.append(SafetyTrigger(
                "BOOST_OVERSHOOT",
                readings["measured_boost_psi"] > overshoot_limit,
                readings["measured_boost_psi"],
                overshoot_limit,
                "Close wastegate, abort ramp, check wastegate actuator"
            ))

        # Trigger 6: Injector duty exceeded
        duty_limit = safe.get("max_duty_cycle_pct", 85.0)
        triggers.append(SafetyTrigger(
            "INJECTOR_DUTY_EXCEEDED",
            readings["injector_duty_pct"] > duty_limit,
            readings["injector_duty_pct"],
            duty_limit,
            "Abort ramp, reduce fuel demand. Upgrade injectors required."
        ))

        return triggers

    def run_ramp(self, samples_per_stage: int = 5) -> Dict:
        """
        Execute the full power ramp.
        Returns stage-by-stage results with pass/fail and abort details.
        """
        results = {
            "total_stages": len(self.stages),
            "completed_stages": 0,
            "status": "COMPLETED",
            "abort_details": None,
            "stages": []
        }

        for stage_idx, stage in enumerate(self.stages):
            stage_result = {
                "stage_number": stage_idx + 1,
                "name": stage["name"],
                "rpm": stage["rpm"],
                "map_kpa": stage["map_kpa"],
                "boost_psi": stage["boost_psi"],
                "status": "PASSED",
                "samples": [],
                "fired_triggers": []
            }

            consecutive_safe = 0
            required_safe = 3  # Need 3 consecutive safe samples to advance

            for sample in range(samples_per_stage):
                readings = self._simulate_readings(stage, sample)
                triggers = self._check_safety_triggers(readings, stage)
                
                fired = [t for t in triggers if t.condition_met]
                
                readings["triggers_checked"] = len(triggers)
                readings["triggers_fired"] = len(fired)
                stage_result["samples"].append(readings)

                if fired:
                    # ABORT
                    stage_result["status"] = "ABORTED"
                    stage_result["fired_triggers"] = [t.to_dict() for t in fired]
                    results["stages"].append(stage_result)
                    results["status"] = "ABORTED"
                    results["abort_details"] = {
                        "aborted_at_stage": stage_idx + 1,
                        "stage_name": stage["name"],
                        "triggers": [t.to_dict() for t in fired],
                        "last_safe_stage": stage_idx,
                        "recommendation": f"Ramp aborted at {stage['name']}. {fired[0].action}"
                    }
                    results["completed_stages"] = stage_idx
                    return results
                else:
                    consecutive_safe += 1

            # Stage passed
            stage_result["consecutive_safe_samples"] = consecutive_safe
            results["stages"].append(stage_result)
            results["completed_stages"] = stage_idx + 1

        return results
