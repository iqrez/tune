import os
import json
import requests

PROJECT_ROOT = r"C:\Users\Rezi\.gemini\antigravity\scratch\basetune_architect"
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# ──────────────────────────────────────────────
# 1. ECU Maps & MSQ Files (Primary Guide §3.3)
# ──────────────────────────────────────────────
MSQ_TARGETS = [
    {
        "url": "https://raw.githubusercontent.com/rusefi/rusefi/master/firmware/tunerstudio/rusefi_mre.msq",
        "dest": "Msq/B18C/rusefi_mre.msq"
    },
    {
        "url": "https://raw.githubusercontent.com/rusefi/rusefi/master/firmware/tunerstudio/frankenso_na6.msq",
        "dest": "Msq/B16A/frankenso_na6.msq"
    },
]

# ──────────────────────────────────────────────
# 2. Injector Deadtime Data (Supplemental §3)
# ──────────────────────────────────────────────
INJECTOR_DATA = {
    "injectors/B18C/common_injectors.json": [
        {"name": "OEM 240cc", "cc_min": 240, "deadtime_ms": [1.20, 1.10, 1.00, 0.95, 0.90], "voltage": [10.0, 11.0, 12.0, 13.0, 14.0]},
        {"name": "RC 370cc", "cc_min": 370, "deadtime_ms": [1.35, 1.20, 1.05, 0.95, 0.88], "voltage": [10.0, 11.0, 12.0, 13.0, 14.0]},
        {"name": "RC 440cc", "cc_min": 440, "deadtime_ms": [1.45, 1.28, 1.10, 1.00, 0.92], "voltage": [10.0, 11.0, 12.0, 13.0, 14.0]},
        {"name": "RC 550cc", "cc_min": 550, "deadtime_ms": [1.55, 1.35, 1.15, 1.05, 0.95], "voltage": [10.0, 11.0, 12.0, 13.0, 14.0]},
        {"name": "ID 1000cc", "cc_min": 1000, "deadtime_ms": [1.80, 1.55, 1.30, 1.15, 1.02], "voltage": [10.0, 11.0, 12.0, 13.0, 14.0]},
        {"name": "ID 1700cc", "cc_min": 1700, "deadtime_ms": [2.10, 1.80, 1.50, 1.30, 1.15], "voltage": [10.0, 11.0, 12.0, 13.0, 14.0]},
    ]
}

# ──────────────────────────────────────────────
# 3. Sensor Physics Reference (Supplemental §1)
# ──────────────────────────────────────────────
SENSOR_DATA = {
    "sensors/LSVTEC/knock_thresholds.json": {
        "description": "Knock sensor threshold reference for B18C LS VTEC",
        "fuel_93oct": {
            "rpm_bins": [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000],
            "knock_threshold_deg": [32, 30, 28, 26, 25, 24, 23, 22],
            "notes": "Max safe ignition advance before knock onset on 93 octane pump gas"
        },
        "fuel_e85": {
            "rpm_bins": [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000],
            "knock_threshold_deg": [38, 36, 34, 32, 31, 30, 29, 28],
            "notes": "E85 allows significantly more advance before knock"
        }
    },
    "sensors/LSVTEC/iat_ve_correction.json": {
        "description": "IAT-based VE correction factors for B-series engines",
        "iat_celsius": [-10, 0, 10, 20, 30, 40, 50, 60, 70],
        "ve_correction_pct": [5.0, 3.5, 2.0, 0.0, -1.5, -3.0, -5.0, -7.0, -10.0],
        "notes": "Positive = add VE (cold dense air), Negative = subtract VE (hot air)"
    }
}

# ──────────────────────────────────────────────
# 4. Environmental Correction (Supplemental §5)
# ──────────────────────────────────────────────
ENVIRONMENTAL_DATA = {
    "sensors/LSVTEC/altitude_corrections.json": {
        "description": "Altitude-based barometric VE/AFR correction",
        "altitude_ft": [0, 1000, 2000, 3000, 4000, 5000, 6000],
        "baro_kpa": [101.3, 97.7, 94.2, 90.8, 87.5, 84.3, 81.2],
        "ve_correction_pct": [0.0, -1.5, -3.0, -4.5, -6.0, -7.5, -9.0],
        "notes": "Higher altitude = less air density = reduce VE and richen slightly for safety"
    }
}

# ──────────────────────────────────────────────
# 5. Turbo Specs (Supplemental §3)
# ──────────────────────────────────────────────
TURBO_DATA = {
    "turbos/B18C/common_turbos.json": [
        {
            "name": "Garrett GT2860RS",
            "max_hp": 300,
            "compressor_inducer_mm": 44,
            "turbine_exducer_mm": 47.6,
            "max_flow_lbs_min": 28,
            "surge_flow_lbs_min": 8,
            "peak_efficiency": 0.72,
            "notes": "Good bolt-on for mild B18 turbo builds"
        },
        {
            "name": "Garrett GT3076R",
            "max_hp": 475,
            "compressor_inducer_mm": 56,
            "turbine_exducer_mm": 56.5,
            "max_flow_lbs_min": 52,
            "surge_flow_lbs_min": 16,
            "peak_efficiency": 0.76,
            "notes": "Popular for 300-450whp B18 turbo builds"
        },
        {
            "name": "Precision 5558 CEA",
            "max_hp": 550,
            "compressor_inducer_mm": 55,
            "turbine_exducer_mm": 58,
            "max_flow_lbs_min": 55,
            "surge_flow_lbs_min": 18,
            "peak_efficiency": 0.78,
            "notes": "High power B18 turbo builds, 400-500+ whp"
        }
    ]
}

# ──────────────────────────────────────────────
# 6. Historical Tuning Reference (Supplemental §4)
# ──────────────────────────────────────────────
HISTORICAL_DATA = {
    "historical/B18C_LSVTEC/safe_tuning_ranges.json": {
        "description": "Known safe tuning parameter ranges for B18C LS VTEC",
        "na_93oct": {
            "max_ignition_wot_deg": 32,
            "min_afr_wot": 12.5,
            "max_afr_wot": 13.2,
            "max_duty_cycle_pct": 80,
            "idle_afr_range": [13.5, 14.5],
            "cruise_afr_range": [14.2, 15.0],
            "vtec_engagement_rpm": [5500, 6000]
        },
        "turbo_93oct": {
            "max_ignition_wot_deg": 22,
            "min_afr_wot": 11.0,
            "max_afr_wot": 11.8,
            "max_boost_psi": 12,
            "max_duty_cycle_pct": 85,
            "idle_afr_range": [13.5, 14.5],
            "cruise_afr_range": [14.2, 14.8],
            "vtec_engagement_rpm": [4500, 5500]
        },
        "turbo_e85": {
            "max_ignition_wot_deg": 28,
            "min_afr_wot": 9.5,
            "max_afr_wot": 10.5,
            "max_boost_psi": 18,
            "max_duty_cycle_pct": 85,
            "idle_afr_range": [13.8, 14.8],
            "cruise_afr_range": [14.5, 15.2],
            "vtec_engagement_rpm": [4500, 5500]
        }
    },
    "historical/B18C_LSVTEC/failure_cases.json": {
        "description": "Documented failure modes for guardrail training",
        "cases": [
            {
                "type": "lean_detonation",
                "conditions": "WOT, 7000 RPM, AFR > 13.5, boost 10 psi",
                "result": "Piston ring land failure",
                "lesson": "Never allow AFR > 12.5 at WOT under boost on 93 octane"
            },
            {
                "type": "overadvanced_ignition",
                "conditions": "WOT, 6500 RPM, 34 deg advance, boost 8 psi",
                "result": "Severe knock, rod bearing damage",
                "lesson": "Max 22 deg advance under boost on 93 octane"
            },
            {
                "type": "injector_duty_exceeded",
                "conditions": "WOT, 8000 RPM, 440cc injectors, turbo 12 psi",
                "result": "Lean condition, 100% duty cycle",
                "lesson": "440cc injectors max safe power ~250whp. Upgrade injectors for higher boost"
            }
        ]
    }
}


def download_file(url, dest_rel):
    full_path = os.path.join(DATA_DIR, dest_rel)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    print(f"  Downloading: {url}")
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            with open(full_path, "wb") as f:
                f.write(resp.content)
            print(f"  -> Saved: {dest_rel} ({len(resp.content)} bytes)")
            return True
        else:
            print(f"  -> FAILED (HTTP {resp.status_code})")
            return False
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return False


def write_json_dataset(rel_path, data):
    full_path = os.path.join(DATA_DIR, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  -> Written: {rel_path}")


if __name__ == "__main__":
    print("=" * 60)
    print("AI BaseTune Architect — Full Dataset Downloader")
    print("=" * 60)

    # Step 1: Download MSQ/ROM files
    print("\n[1/5] Downloading ECU Maps & MSQ files...")
    msq_ok = 0
    for t in MSQ_TARGETS:
        if download_file(t["url"], t["dest"]):
            msq_ok += 1
    print(f"  Downloaded {msq_ok}/{len(MSQ_TARGETS)} MSQ files.\n")

    # Step 2: Write injector data
    print("[2/5] Writing injector specification datasets...")
    for path, data in INJECTOR_DATA.items():
        write_json_dataset(path, data)

    # Step 3: Write sensor physics data
    print("\n[3/5] Writing sensor & engine physics datasets...")
    for path, data in SENSOR_DATA.items():
        write_json_dataset(path, data)
    for path, data in ENVIRONMENTAL_DATA.items():
        write_json_dataset(path, data)

    # Step 4: Write turbo specs
    print("\n[4/5] Writing turbo specification datasets...")
    for path, data in TURBO_DATA.items():
        write_json_dataset(path, data)

    # Step 5: Write historical tuning data
    print("\n[5/5] Writing historical tuning & failure case datasets...")
    for path, data in HISTORICAL_DATA.items():
        write_json_dataset(path, data)

    print("\n" + "=" * 60)
    print("Dataset population complete!")
    print("=" * 60)
