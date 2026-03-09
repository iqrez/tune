import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path("backend").absolute()))

from core.rusefi_connector import RusefiTunerClient
from core.parameters import ParameterRegistry

def test_categorization():
    client = RusefiTunerClient()
    client.is_connected = lambda: True
    
    registry = ParameterRegistry(client)
    registry.ensure_loaded()
    
    # Check some known parameters
    checks = {
        "cylindersCount": "Setup > Vehicle Information",
        "veTable": "Fuel > VE",
        "ignitionTable": "Ignition > Ignition advance",
        "rpmHardLimit": "Setup > Limits and protection > Limits and fallbacks",
        "injector_flow": "Fuel > Injector Setup > Injection configuration"
    }
    
    print(f"\n--- Categorization Results ---")
    for name, expected in checks.items():
        found = next((p for p in registry.list_parameters() if p["name"] == name), None)
        if found:
            actual = found['category']
            status = "PASS" if actual == expected else "FAIL"
            print(f"{status:4} | {name:20} | Actual: {actual}")
            if actual != expected:
                print(f"     | {'':20} | Expect: {expected}")
        else:
            print(f"MISS | {name:20} | NOT FOUND")

if __name__ == "__main__":
    test_categorization()
