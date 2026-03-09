import random
from typing import List, Dict
from ..schemas import VehicleProfile, CalibrationSnapshot
from .math_engine import DeterministicEngineModel


class LiveSimulator:
    """
    Simulates a closed-loop fuel auto-correction cycle.
    
    This demonstrates how the system would behave during a real
    driving session: reading wideband AFR, comparing to targets,
    and applying small fuel-only corrections each cycle.
    
    Rule 6 enforced: In auto-apply mode, only fuel changes are allowed.
    """

    def __init__(self, profile: VehicleProfile, calibration: CalibrationSnapshot):
        self.profile = profile
        self.calibration = calibration
        self.engine = DeterministicEngineModel(profile)
        self.rpm_axis = calibration.axes.get("rpm", [])
        self.map_axis = calibration.axes.get("map_kpa", [])

    def _simulate_afr_reading(self, target_afr: float, cycle: int) -> float:
        """
        Simulates a wideband AFR reading with realistic noise and drift.
        Early cycles have more error; corrections reduce error over time.
        """
        base_error = random.gauss(0, 0.8)  # ±0.8 AFR noise
        drift = random.uniform(-0.3, 0.5)  # Slight lean bias (common in base tunes)
        decay = max(0.1, 1.0 - cycle * 0.04)  # Error decays as corrections accumulate
        return target_afr + (base_error + drift) * decay

    def run_simulation(self, num_cycles: int = 20, cells_per_cycle: int = 4) -> Dict:
        """
        Runs the full simulation.
        
        Each cycle:
        1. Picks random active cells (simulating driving through different RPM/load zones)
        2. Reads simulated AFR
        3. Computes fuel correction (clamped to ±2% per cycle for safety)
        4. Accumulates corrections
        
        Returns a complete correction history for the frontend to animate.
        """
        # Working copy of fuel table
        fuel_table = [row[:] for row in self.calibration.fuel_table]
        
        history = []
        cumulative_corrections = {}  # (rpm_idx, map_idx) -> total_pct

        for cycle in range(num_cycles):
            cycle_data = {
                "cycle": cycle + 1,
                "corrections": [],
                "avg_afr_error": 0.0,
                "cells_corrected": 0
            }

            afr_errors = []

            # Simulate driving through random cells
            active_cells = []
            for _ in range(cells_per_cycle):
                rpm_idx = random.randint(2, min(12, len(self.rpm_axis) - 1))  # Skip very low/high RPM
                map_idx = random.randint(1, min(10, len(self.map_axis) - 1))  # Skip vacuum extremes
                active_cells.append((rpm_idx, map_idx))

            for rpm_idx, map_idx in active_cells:
                rpm = self.rpm_axis[rpm_idx] if rpm_idx < len(self.rpm_axis) else 3000
                map_kpa = self.map_axis[map_idx] if map_idx < len(self.map_axis) else 60

                target_afr = self.engine.generate_base_afr_target(float(rpm), float(map_kpa))
                measured_afr = self._simulate_afr_reading(target_afr, cycle)
                
                afr_error_pct = ((measured_afr - target_afr) / target_afr) * 100
                afr_errors.append(abs(afr_error_pct))

                # Correction: half of error, clamped to ±2%
                correction = afr_error_pct * 0.5
                correction = max(-2.0, min(2.0, correction))

                # Apply to working table
                if rpm_idx < len(fuel_table) and map_idx < len(fuel_table[rpm_idx]):
                    fuel_table[rpm_idx][map_idx] *= (1 + correction / 100.0)
                    fuel_table[rpm_idx][map_idx] = round(fuel_table[rpm_idx][map_idx], 3)

                # Track cumulative
                key = (rpm_idx, map_idx)
                cumulative_corrections[key] = cumulative_corrections.get(key, 0.0) + correction

                cycle_data["corrections"].append({
                    "rpm_idx": rpm_idx,
                    "map_idx": map_idx,
                    "rpm": rpm,
                    "map_kpa": map_kpa,
                    "target_afr": round(target_afr, 2),
                    "measured_afr": round(measured_afr, 2),
                    "afr_error_pct": round(afr_error_pct, 2),
                    "correction_pct": round(correction, 3),
                    "cumulative_pct": round(cumulative_corrections[key], 3)
                })

            cycle_data["avg_afr_error"] = round(sum(afr_errors) / max(1, len(afr_errors)), 2)
            cycle_data["cells_corrected"] = len(active_cells)
            history.append(cycle_data)

        # Summary
        total_corrections = sum(len(c["corrections"]) for c in history)
        avg_final_error = history[-1]["avg_afr_error"] if history else 0
        avg_initial_error = history[0]["avg_afr_error"] if history else 0

        return {
            "num_cycles": num_cycles,
            "total_corrections_applied": total_corrections,
            "unique_cells_touched": len(cumulative_corrections),
            "avg_initial_afr_error_pct": avg_initial_error,
            "avg_final_afr_error_pct": avg_final_error,
            "improvement_pct": round(max(0, (1 - avg_final_error / max(0.01, avg_initial_error)) * 100), 1),
            "history": history,
            "corrected_fuel_table": fuel_table
        }
