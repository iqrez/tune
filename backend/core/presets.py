from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .parameters import ParameterRegistry


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower()).strip("_")


class PresetManager:
    """
    Built-in + custom preset manager for uaEFI boards.

    Presets are applied through ParameterRegistry so all existing guardrails remain active.
    """

    CUSTOM_FILE = "custom_presets.json"

    def __init__(self, registry: ParameterRegistry, storage_dir: Optional[str] = None):
        self.registry = registry
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = Path(__file__).resolve().parents[1] / "state" / "presets"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.custom_file = self.storage_dir / self.CUSTOM_FILE
        self._builtins = self._build_builtin_presets()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_presets(self) -> List[Dict[str, Any]]:
        out = []
        for p in self._builtins:
            out.append(self._preset_summary(p))
        for p in self._load_custom_presets():
            out.append(self._preset_summary(p))
        return out

    def get_preset(self, preset_id_or_name: str) -> Dict[str, Any]:
        key = (preset_id_or_name or "").strip().lower()
        for p in self._builtins + self._load_custom_presets():
            if p.get("id", "").lower() == key or p.get("name", "").lower() == key:
                return deepcopy(p)
        raise KeyError(f"Preset '{preset_id_or_name}' not found")

    def apply_preset(
        self,
        preset_id_or_name: str,
        burn_after: bool = False,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.registry.ensure_loaded()
        preset = self.get_preset(preset_id_or_name)

        values = dict(preset.get("values", {}))
        if overrides:
            values.update({k: v for k, v in overrides.items() if v is not None})

        changed: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        with self.registry.temporary_write_access():
            for raw_name, target_value in values.items():
                try:
                    resolved = self.registry.resolve_name(raw_name)
                except Exception as e:
                    skipped.append({"parameter": raw_name, "reason": f"not found ({e})"})
                    continue

                try:
                    before_data = self.registry.read_parameter(resolved)
                    before = before_data.get("value")
                except Exception as e:
                    skipped.append({"parameter": resolved, "reason": f"read failed ({e})"})
                    continue

                if self._roughly_equal(before, target_value):
                    skipped.append({"parameter": resolved, "reason": "already at target value"})
                    continue

                try:
                    ok = self.registry.write_parameter(resolved, target_value, force=False)
                    if not ok:
                        errors.append({"parameter": resolved, "error": "ECU write rejected"})
                        continue
                except Exception as e:
                    errors.append({"parameter": resolved, "error": str(e)})
                    continue

                changed.append(
                    {
                        "parameter": resolved,
                        "before": before,
                        "after": target_value,
                    }
                )

            burn_ok = False
            if burn_after and changed:
                try:
                    burn_ok = bool(self.registry.burn())
                except Exception as e:
                    errors.append({"parameter": "__burn__", "error": str(e)})
                    burn_ok = False

        status = "success"
        if errors:
            status = "partial"
        if not changed and not errors:
            status = "no_changes"

        return {
            "status": status,
            "preset_id": preset.get("id"),
            "preset_name": preset.get("name"),
            "board": preset.get("board"),
            "engine_focus": preset.get("engine_focus"),
            "changed": changed,
            "skipped": skipped,
            "errors": errors,
            "burn_after": bool(burn_after),
            "burn_ok": burn_ok if burn_after else None,
            "safety_notes": list(preset.get("safety_notes", [])),
            "warnings": list(preset.get("warnings", [])),
        }

    def save_custom_preset(
        self,
        name: str,
        values: Optional[Dict[str, Any]] = None,
        notes: Optional[List[str]] = None,
        base_preset: Optional[str] = None,
    ) -> Dict[str, Any]:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Custom preset name is required")

        payload_values: Dict[str, Any] = {}
        if base_preset:
            base = self.get_preset(base_preset)
            payload_values.update(base.get("values", {}))
        if values:
            payload_values.update(values)
        if not payload_values:
            raise ValueError("Custom preset must contain at least one parameter value")

        custom = {
            "id": f"custom_{_slug(clean_name)}",
            "name": clean_name,
            "board": "Custom",
            "engine_focus": "User Defined",
            "description": "Custom preset saved by user",
            "safety_notes": list(notes or []),
            "warnings": ["Always verify ignition timing with a timing light before hard pulls."],
            "values": payload_values,
            "source": "custom",
            "created_at": _utc_now_iso(),
        }

        all_custom = self._load_custom_presets()
        all_custom = [p for p in all_custom if p.get("id") != custom["id"]]
        all_custom.append(custom)
        self._save_custom_presets(all_custom)
        return self._preset_summary(custom)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _preset_summary(self, preset: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": preset.get("id"),
            "name": preset.get("name"),
            "board": preset.get("board"),
            "engine_focus": preset.get("engine_focus"),
            "description": preset.get("description"),
            "safety_notes": list(preset.get("safety_notes", [])),
            "warnings": list(preset.get("warnings", [])),
            "parameter_count": len(preset.get("values", {})),
            "source": preset.get("source", "builtin"),
        }

    def _load_custom_presets(self) -> List[Dict[str, Any]]:
        if not self.custom_file.exists():
            return []
        try:
            raw = json.loads(self.custom_file.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return [p for p in raw if isinstance(p, dict)]
            return []
        except Exception:
            return []

    def _save_custom_presets(self, presets: List[Dict[str, Any]]):
        self.custom_file.write_text(json.dumps(presets, indent=2), encoding="utf-8")

    @staticmethod
    def _roughly_equal(a: Any, b: Any) -> bool:
        try:
            if isinstance(a, list) and isinstance(b, list):
                if len(a) != len(b):
                    return False
                for i in range(len(a)):
                    if not PresetManager._roughly_equal(a[i], b[i]):
                        return False
                return True
            af = float(a)
            bf = float(b)
            return abs(af - bf) < 1e-6
        except Exception:
            return a == b

    def _build_builtin_presets(self) -> List[Dict[str, Any]]:
        honda_obd1_values = {
            # Core fueling
            "injectorFlow": 240.0,
            "injectorDeadTime": 0.85,
            "injectorLagVoltageCorrection": 0.20,
            "injectorSmallPulseOffset": 0.05,
            "crankingFuel": 12.0,
            "crankingDuration": 4.0,
            "crankingTiming": 12.0,
            "accelerationEnrichment": 15.0,
            "decelerationEnleanment": 10.0,
            "wallWettingCoefficient": 0.30,
            "wallWettingTau": 0.35,
            "globalFuelTrim": 0.0,
            "perCylinderFuelTrim1": 0.0,
            "perCylinderFuelTrim2": 0.0,
            "perCylinderFuelTrim3": 0.0,
            "perCylinderFuelTrim4": 0.0,
            "perCylinderFuelTrim5": 0.0,
            "perCylinderFuelTrim6": 0.0,
            "perCylinderFuelTrim7": 0.0,
            "perCylinderFuelTrim8": 0.0,
            "lambda1SensorOffset": 0.0,
            # Honda-focused trigger + VTEC
            "triggerType": 3,
            "triggerAngle": 80.0,
            "vtecEngagementRPM": 5500.0,
            "vtecSolenoidOutput": 2,
            # Limits and idle
            "rpmHardLimit": 8500.0,
            "revLimiterFuelCut": 1.0,
            "revLimiterSparkCut": 0.0,
            "idleRpmTarget": 900.0,
            # Strategy and sensors
            "fuelStrategy": 1.0,
            "mapSensor": 1.0,
            "mapScaling": 1.0,
            # Boost/fans
            "boostCutPressure": 300.0,
            "fanOnTemperature": 92.0,
            "fanOffTemperature": 88.0,
            # Ignition and knock safety baselines
            "sparkDwell": 2.6,
            "knockRetard": 3.0,
            "knockRecoveryRate": 0.25,
            "knockThreshold": 1.0,
            # VVT/cam offsets (safe neutral)
            "vvt1Offset": 0.0,
            "vvt2Offset": 0.0,
            # Misc hardware
            "batteryVoltageCorrection": 0.0,
            "tachPulsePerRev": 2.0,
            "speedSensor": 1.0,
        }

        uaefi_blank_values = {
            "injectorFlow": 550.0,
            "injectorDeadTime": 0.85,
            "injectorLagVoltageCorrection": 0.20,
            "injectorSmallPulseOffset": 0.08,
            "crankingFuel": 10.0,
            "crankingDuration": 3.5,
            "crankingTiming": 10.0,
            "accelerationEnrichment": 12.0,
            "decelerationEnleanment": 8.0,
            "wallWettingCoefficient": 0.32,
            "wallWettingTau": 0.40,
            "globalFuelTrim": 0.0,
            "lambda1SensorOffset": 0.0,
            "triggerType": 3,
            "triggerAngle": 80.0,
            "rpmHardLimit": 7000.0,
            "revLimiterFuelCut": 1.0,
            "revLimiterSparkCut": 0.0,
            "idleRpmTarget": 850.0,
            "fuelStrategy": 1.0,
            "mapSensor": 1.0,
            "mapScaling": 1.0,
            "boostCutPressure": 260.0,
            "fanOnTemperature": 92.0,
            "fanOffTemperature": 88.0,
            "sparkDwell": 2.7,
            "knockRetard": 2.0,
            "knockRecoveryRate": 0.20,
            "knockThreshold": 1.0,
            "vvt1Offset": 0.0,
            "vvt2Offset": 0.0,
            "batteryVoltageCorrection": 0.0,
            "tachPulsePerRev": 2.0,
            "speedSensor": 1.0,
        }

        return [
            {
                "id": "uaefi_honda_obd1_quick_base_tune",
                "name": "uaEFI Honda OBD1 Quick Base Tune",
                "board": "uaEFI Honda OBD1",
                "engine_focus": "Honda B/D series (OBD1 PnP)",
                "description": "Safe startup baseline for B-series, LS-VTEC, and D-series OBD1 Honda configurations.",
                "safety_notes": [
                    "Timing light required: lock timing and confirm trigger angle before driving.",
                    "Verify injector size and dead-time against your injector data sheet.",
                    "Confirm VTEC output pin/wiring for your exact OBD1 adapter harness.",
                    "Confirm base fuel pressure and MAP sensor calibration before hard load.",
                ],
                "warnings": [
                    "This is a startup preset, not a final tune.",
                    "Do not perform high-load runs until AFR and ignition timing are verified.",
                ],
                "values": honda_obd1_values,
                "source": "builtin",
            },
            {
                "id": "uaefi_ultra_affordable_blank_safe_base",
                "name": "uaEFI Ultra Affordable EFI Blank Safe Base",
                "board": "uaEFI Ultra Affordable EFI",
                "engine_focus": "Universal baseline",
                "description": "Conservative blank safe base for first-fire and sensor validation on generic installs.",
                "safety_notes": [
                    "Use this preset only to get stable idle/startup and sensor sanity checks.",
                    "Confirm trigger mode, ignition output mode, and coil dwell for your hardware.",
                    "Verify injector flow/dead-time before tuning VE or target lambda tables.",
                ],
                "warnings": [
                    "Final fueling and ignition must be tuned for your engine.",
                    "Rev limit is intentionally conservative until calibration is validated.",
                ],
                "values": uaefi_blank_values,
                "source": "builtin",
            },
        ]

