from typing import List, Dict, Optional
from ..schemas import VehicleProfile

# Constants
STP_AIR_DENSITY_G_CC = 0.001225 # kg/m^3 converted to g/cc
GASOLINE_STOICH = 14.7
E85_STOICH = 9.8

class DeterministicEngineModel:
    def __init__(self, profile: VehicleProfile):
        self.profile = profile

    def _get_stoich_afr(self) -> float:
        if self.profile.fuel_type == "e85":
            return E85_STOICH
        return GASOLINE_STOICH # Default for gas93/gas98

    def estimate_injector_scaling_ms(self, ve_cell: float, map_kpa: float, iat_c: float, target_afr: float) -> float:
        """
        Estimate raw pulsewidth (ms) required for a given cell (assuming deadtime is handled separately by ECU config)
        """
        # 1. Total air mass drawn in 1 cycle (2 engine revolutions for 4-stroke)
        air_mass_total_grams = (self.profile.displacement_l * 1000) * ve_cell * \
                               (map_kpa / 101.325) * \
                               (288 / (273 + iat_c)) * \
                               STP_AIR_DENSITY_G_CC
        
        # 2. Divide by cylinders to get mass per cylinder event
        air_mass_per_cylinder = air_mass_total_grams / self.profile.cylinders

        # 3. Fuel mass required
        fuel_mass_grams = air_mass_per_cylinder / target_afr

        # 4. Injector flow rate (cc/min to g/s)
        # Approximate fuel density = 0.745 g/cc
        injector_flow_g_s = (self.profile.injector_cc_min * 0.745) / 60.0

        # 5. Pulsewidth in ms
        pw_ms = (fuel_mass_grams / injector_flow_g_s) * 1000.0
        return pw_ms

    def generate_base_afr_target(self, rpm: float, map_kpa: float) -> float:
        """
        Calculates target AFR using zone interpolation based on Profile breakpoints.
        """
        base_stoich = self._get_stoich_afr()
        
        # Determine zones
        is_idle = rpm <= self.profile.idle_rpm_max and map_kpa < 70
        is_cruise = rpm > self.profile.idle_rpm_max and map_kpa < 80
        is_boost = map_kpa >= self.profile.boost_kpa_min

        # Richer under boost
        boost_offset = 0.0
        if is_boost:
            boost_amount_kpa = map_kpa - 100
            # Roughly 0.1 AFR richer per 15 kPa of boost
            boost_offset = (boost_amount_kpa / 15.0) * 0.1
        
        if self.profile.fuel_type == "e85":
            if is_idle: return 9.5
            if is_cruise: return 9.8
            if is_boost: return max(7.5, 8.5 - boost_offset)
            return 9.0 # Mid load
        else: # Gasoline
            if is_idle: return 14.0
            if is_cruise: return 14.7
            if is_boost: return max(11.0, 12.0 - boost_offset)
            return 13.0 # Mid load

    def generate_base_ignition_timing(self, rpm: float, map_kpa: float) -> float:
        """ Conservative baseline timing generator. """
        mbt_estimate = 30.0 
        if self.profile.compression_ratio > 10.5:
             mbt_estimate -= (self.profile.compression_ratio - 10.5) * 1.5
        rpm_factor = min(1.0, (rpm - 1000) / 3000.0) if rpm > 1000 else 0.0
        timing_base = 10.0 + (mbt_estimate - 10.0) * rpm_factor
        map_retard = (map_kpa - 100) / 10.0 if map_kpa > 100 else 0.0
        timing_final = timing_base - map_retard
        return max(-5.0, min(mbt_estimate, timing_final))

    def generate_initial_tables(self) -> dict:
        """Helper to generate full 16x16 VE and Ignition tables."""
        rpm_axis = [500 + i*500 for i in range(16)]
        map_axis = [30 + i*15 for i in range(16)]
        
        fuel_table = []
        ign_table = []
        for r in rpm_axis:
            f_row = []
            i_row = []
            for m in map_axis:
                ve = 0.75
                target_afr = self.generate_base_afr_target(float(r), float(m))
                pw = self.estimate_injector_scaling_ms(ve, float(m), 30.0, target_afr)
                f_row.append(round(pw, 2))
                i_row.append(round(self.generate_base_ignition_timing(float(r), float(m)), 1))
            fuel_table.append(f_row)
            ign_table.append(i_row)
            
        return {
            "axes": {"rpm": rpm_axis, "map_kpa": map_axis},
            "fuel_table": fuel_table,
            "ignition_table": ign_table
        }
