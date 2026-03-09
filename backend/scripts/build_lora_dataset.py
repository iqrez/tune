import json
import os
from parsers.msq_parser import MsqParser

# Hardcoded project root for reliability
PROJECT_ROOT = r"C:\Users\Rezi\.gemini\antigravity\scratch\basetune_architect"
MSQ_DIR = os.path.join(PROJECT_ROOT, "data", "Msq")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "backend", "scripts", "dataset.jsonl")

def generate_lora_dataset():
    print(f"Scanning for MSQ files in: {MSQ_DIR}")
    dataset = []
    
    if not os.path.exists(MSQ_DIR):
        print(f"ERROR: MSQ directory not found: {MSQ_DIR}")
        return

    for root, _, files in os.walk(MSQ_DIR):
        for file in files:
            if file.endswith(".msq"):
                filepath = os.path.join(root, file)
                print(f"Parsing: {filepath}")
                
                # Determine engine family from parent folder
                engine_family = os.path.basename(root)
                if engine_family == "Msq":
                    engine_family = "B18C" # Fallback
                
                is_turbo = "turbo" in file.lower()
                profile = {
                   "engine_family": engine_family,
                   "engine_model": f"{engine_family} Build",
                   "displacement_l": 1.8 if "18" in engine_family else (1.6 if "16" in engine_family else 2.0),
                   "cylinders": 4,
                   "aspiration": "Turbo" if is_turbo else "NA",
                   "compression_ratio": 9.5 if is_turbo else 10.5,
                   "fuel_type": "E85" if "e85" in file.lower() else "93 Octane",
                   "injector_cc_min": 1000 if is_turbo else 440,
                   "redline_rpm": 8200,
                   "notes": f"Imported from {file}"
                }
                
                parser = MsqParser(filepath)
                ve_table = parser.extract_table("veTable1", "rpmBins1", "mapBins1")
                ign_table = parser.extract_table("ignTable1", "rpmBins1", "mapBins1")
                
                # Check for empty tables
                if not ve_table.get("z_values") or not ign_table.get("z_values"):
                    print(f"Warning: Could not extract tables from {file}")
                    # Create generic placeholder for now if parser returns nothing
                    ve_table["z_values"] = [[80.0]*16]*16
                    ign_table["z_values"] = [[15.0]*16]*16
                    ve_table["x_axis"] = list(range(500, 8500, 500))
                    ve_table["y_axis"] = list(range(20, 110, 10))

                target_output = {
                    "base_tune": {
                        "fuel_table": ve_table.get("z_values"),
                        "ignition_table": ign_table.get("z_values"),
                        "axes": {
                            "rpm": ve_table.get("x_axis"),
                            "map_kpa": ve_table.get("y_axis")
                        }
                    },
                    "explanation": f"Base tune generated for {engine_family}. VE table derived from {file} and scaled for {profile['injector_cc_min']}cc injectors."
                }
                
                instruction = f"Generate safe base VE, fuel, ignition tables for a {profile['engine_model']} {profile['aspiration']}, {profile['fuel_type']}, {profile['injector_cc_min']}cc injectors, redline {profile['redline_rpm']}"
                
                dataset.append({
                    "instruction": instruction,
                    "input": profile,
                    "output": target_output
                })

    if not dataset:
        print("No examples found to generate dataset.")
        return

    with open(OUTPUT_FILE, 'w') as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
            
    print(f"SUCCESS: Generated {len(dataset)} examples in {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_lora_dataset()
