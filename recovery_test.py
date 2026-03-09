import sys
import os
import time
import logging

# Ensure backend is in path
sys.path.append(os.path.join(os.getcwd(), "backend"))
from core.rusefi_connector import RusefiTunerClient

def run_recovery():
    print("==========================================")
    print("   🏎️ rusEFI BULLETPROOF RECOVERY TEST   ")
    print("==========================================\n")
    
    client = RusefiTunerClient()
    
    print("🔍 Step 1: Scanning for all available COM ports...")
    ports = client.list_all_ports_with_test()
    if not ports:
        print("❌ CRITICAL: No COM ports detected. Check USB cable.")
        return

    for p in ports:
        print(f"   - {p['port']} ({p['baud']} baud): {'✅ rusEFI Found' if p['is_rusefi'] else '❓ Ghost/Silent'}")

    print("\n🔍 Step 2: Attempting Auto-RECOVERY on all ports...")
    target_port = client.auto_detect_serial_port()
    
    if target_port:
        print(f"\n🎉 SUCCESS! rusEFI detected and responding on {target_port}.")
        print("You can now start the main application.")
    else:
        print("\n❌ RECOVERY FAILED: ECU is still silent.")
        print("Possible causes:")
        print("  1. USB cable is 'charge-only' (no data).")
        print("  2. ECU is not getting 5V/12V power.")
        print("  3. Firmware is corrupted (needs DFU flash).")
    
    print("\n==========================================")

if __name__ == "__main__":
    run_recovery()
