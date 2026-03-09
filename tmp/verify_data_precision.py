import sys
import os
import struct
import time
import threading
import json

# Add backend and root to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.rusefi_connector import RusefiTunerClient
from mock_ecu import MockRusefi

def run_verification():
    # 1. Start Mock ECU
    mock = MockRusefi(port=29003)
    t = threading.Thread(target=mock.run, daemon=True)
    t.start()
    time.sleep(1)

    # 2. Fill VE table (offset 16748) with test data
    # veTable1 is U16, scale 0.1. 
    # Let's put 1234 (which should be 123.4) in the first cell
    # And 500 (which should be 50.0) in the second cell
    test_data = [1234, 500] + [0] * 254
    packed = struct.pack('<' + 'H' * 256, *test_data)
    mock.page0[16748:16748+512] = packed

    # 3. Connect client
    client = RusefiTunerClient()
    print("Connecting to Mock ECU...")
    if not client.connect_tcp("127.0.0.1", 29003):
        print("FAILED to connect")
        return

    print("Connected. Reading VE Table...")
    raw = client.read_table("veTable1")
    if not raw:
        print("FAILED to read table")
        return

    print(f"Read {len(raw)} bytes.")
    
    # 4. Mock the api_v1 decoding logic
    import math
    def _decode_raw_value(raw, meta):
        return round((raw * meta['scale']), 3)

    meta = client.TABLES["veTable1"]
    raw_vals = struct.unpack(f'<{len(raw)//2}H', raw)
    logical = [_decode_raw_value(v, meta) for v in raw_vals]
    
    print(f"First two logical values: {logical[0]}, {logical[1]}")
    
    if logical[0] == 123.4 and logical[1] == 50.0:
        print("✅ SUCCESS: Data precision and scaling verified!")
    else:
        print(f"❌ FAILURE: Expected 123.4, 50.0 but got {logical[0]}, {logical[1]}")

    # 5. Test Write
    print("Testing Write...")
    new_logical = [100.0, 95.5] + [0.0] * 254
    encoded_vals = [int(round(v / meta['scale'])) for v in new_logical]
    new_packed = struct.pack(f'<{len(encoded_vals)}H', *encoded_vals)
    
    client.set_allow_writes(True)
    if client.write_table("veTable1", new_packed):
        print("Write command sent.")
        # Verify in mock memory
        mock_raw = mock.page0[16748:16748+4]
        v1, v2 = struct.unpack("<HH", mock_raw)
        print(f"Mock memory now: {v1}, {v2} (raw)")
        if v1 == 1000 and v2 == 955:
            print("✅ SUCCESS: Write verification passed!")
        else:
            print(f"❌ FAILURE: Write verification failed. Got {v1}, {v2}")
    else:
        print("❌ FAILURE: Write failed")

if __name__ == "__main__":
    run_verification()
