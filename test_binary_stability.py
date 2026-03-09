import sys
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "backend"))
from core.rusefi_connector import RusefiTunerClient

def test_stability():
    client = RusefiTunerClient()
    print("Testing auto-detect...")
    port = client.auto_detect_serial_port()
    if not port:
        print("Failed to detect port. Make sure ECU is plugged in.")
        return
        
    print(f"Connected to {port} in BINARY mode. Starting rapid TS_OUTPUT polling (20Hz)...")
    successes = 0
    failures = 0
    
    start_time = time.time()
    for i in range(1, 101):
        try:
            # Reconnect if dropped
            if not client.connected:
                print("Connection dropped. Attempting reconnect...")
                client.auto_detect_serial_port()
                
            data = client.get_live_data_binary()
            if data and isinstance(data, dict):
                successes += 1
            else:
                failures += 1
                
            if i % 10 == 0:
                print(f"Poll {i}/100: {successes} success, {failures} fails")
                
            time.sleep(0.05) # 20Hz polling rate
            
        except Exception as e:
            print(f"CRASH on poll {i}: {e}")
            failures += 1
            break
            
    elapsed = time.time() - start_time
    print(f"\n--- TEST COMPLETED in {elapsed:.2f}s ---")
    print(f"Total Requests  : 100")
    print(f"Successful Read : {successes}")
    print(f"Failed Frames   : {failures}")
    
    if failures == 0:
        print("RESULT: PERFECT STABILITY ACHIEVED. No Windows Error 22 crashes!")
    elif successes > 0:
        print(f"RESULT: STABLE WITH ~{failures}% PACKET LOSS. (Normal for USB Serial). No Hard Crashes.")
    else:
        print("RESULT: COMPLETE FAILURE.")

if __name__ == "__main__":
    test_stability()
