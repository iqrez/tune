import sys
import os
import time
import logging

# Ensure backend is in path
sys.path.append(os.path.join(os.getcwd(), "backend"))
from core.rusefi_connector import RusefiTunerClient

def hardware_probe():
    print("==========================================")
    print("   🏎️ rusEFI REAL HARDWARE PROBE v3.0    ")
    print("==========================================\n")
    
    client = RusefiTunerClient()
    
    # 1. Manual check of COM5 (NO TCP FALLBACK)
    print("🔍 Probing COM5 ONLY (Serial Protocol 3.0)...")
    # We skip client.connect() and go straight to internal serial helper to avoid fallback
    if client._try_serial("COM5"):
        print("\n🎉 SUCCESS! Connected to physical ECU on COM5.")
        print(f"📡 Mode: {client.connection_type} | Port: {client.port_name}")
        
        print("\n📥 Fetching Real-Time Gauges...")
        data = client.get_live_data()
        if data:
            print(f"   - RPM: {data.get('RPM')}")
            print(f"   - MAP: {data.get('MAP_kPa')} kPa")
            print(f"   - AFR: {data.get('AFR')}")
        else:
            print("   ❌ Telemetry read failed.")
    else:
        print("\n❌ Handshake failed on COM5.")
        print("ECU is either off, silent, or still in bootloader.")
    
    print("\n==========================================")

if __name__ == "__main__":
    hardware_probe()
