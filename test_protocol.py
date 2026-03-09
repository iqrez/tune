import sys
import os
import time

# Ensure backend is in path
sys.path.append(os.path.join(os.getcwd(), "backend"))
from core.rusefi_connector import RusefiTunerClient

def test_protocol():
    print("--- 🧪 rusEFI Protocol Verification ---")
    client = RusefiTunerClient()
    
    print("\n1. Connecting (TCP/Mock)...")
    if client.connect(tcp_port=29002):
        print("✅ Connected to Mock ECU")
    else:
        print("❌ Handshake failed (Framing/CRC error?)")
        return

    print("\n2. Fetching Live Data (OCH)...")
    data = client.get_live_data()
    if data:
        print(f"✅ Data received: RPM={data.get('RPM')} MAP={data.get('MAP_kPa')}")
    else:
        print("❌ OCH request failed")

    print("\n3. Testing Table Read...")
    ve_data = client.read_table("veTable1")
    if ve_data and len(ve_data) == 256:
        print(f"✅ Table Read success (256 bytes)")
    else:
        print("❌ Table Read failed")

    print("\n4. Testing Table Write & Burn...")
    test_data = bytes([i % 256 for i in range(256)])
    if client.write_table("veTable1", test_data):
        print("✅ Table Write success")
        # Verify
        verify_data = client.read_table("veTable1")
        if verify_data == test_data:
            print("✅ Data Verification success")
        else:
            print("❌ Data Verification failed (Corruption?)")
    else:
        print("❌ Table Write failed")

    client.disconnect()
    print("\n--- 🏁 Verification Complete ---")

if __name__ == "__main__":
    test_protocol()
