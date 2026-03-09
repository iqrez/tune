import os

PROJECT_ROOT = r"C:\Users\Rezi\.gemini\antigravity\scratch\basetune_architect"

# All directories from both the primary instruction guide AND the supplemental plan
DIRS = [
    # Primary (ECU Maps)
    "data/ROMs/B18C_LS_VTEC",
    "data/ROMs/B16A",
    "data/ROMs/B18C",
    "data/ROMs/B20B",
    "data/ROMs/D16Z6",
    "data/Msq/B16A",
    "data/Msq/B18C",
    "data/Msq/B20B",
    "data/Msq/D16Z6",
    "data/logs/LSVTEC",
    # Supplemental
    "data/sensors/LSVTEC",
    "data/injectors/B18C",
    "data/turbos/B18C",
    "data/historical/B18C_LSVTEC",
    "data/manuals/LSVTEC",
    "data/calculators/LSVTEC",
]

for d in DIRS:
    path = os.path.join(PROJECT_ROOT, d)
    os.makedirs(path, exist_ok=True)
    print(f"  [OK] {d}")

print(f"\nAll {len(DIRS)} directories created successfully.")
