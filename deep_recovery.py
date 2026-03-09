import serial
import time
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "backend"))
from core.rusefi_connector import RusefiTunerClient

def deep_recovery(port):
    print(f"--- 🚨 DEEP RECOVERY STARTING ON {port} ---")
    
    for baud in [9600, 115200]:
        print(f"\n📡 Testing Baud: {baud}")
        try:
            ser = serial.Serial(port, baudrate=baud, timeout=1.0)
            
            # Reset hardware
            print("   ⚡ Pulsing DTR/RTS...")
            ser.dtr = False; ser.rts = False; time.sleep(0.5)
            ser.dtr = True; ser.rts = True; time.sleep(1.0)
            
            # Send wakeup strings
            print("   ⌨️ Sending wakeup commands...")
            for _ in range(5):
                ser.write(b"\r\n")
                time.sleep(0.1)
            ser.write(b"rusefi\r\n")
            ser.write(b"exit\r\n")
            time.sleep(0.5)
            
            # Check for ANY response
            resp = ser.read(1024)
            if resp:
                print(f"   ✅ RECEIVED BYTES: {resp.hex()}")
                print(f"   📝 TEXT: {resp.decode('ascii', errors='ignore')}")
            else:
                print("   ❌ No response.")
            
            ser.close()
        except Exception as e:
            print(f"   ❌ Error: {e}")

    print("\n--- 🏁 DEEP RECOVERY FINISHED ---")

if __name__ == "__main__":
    deep_recovery("COM5")
