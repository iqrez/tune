import logging
import binascii
import pytest
from backend.core.rusefi_connector import RusefiTunerClient

# Configure logging to see the massive hex output
logging.basicConfig(level=logging.DEBUG)

def test_binary_protocol_full_sequence(port: str = "COM5"):
    client = RusefiTunerClient()
    
    if port.startswith("COM") or "/" in port:
        print(f"\n[STEP 1] Connecting to Physical ECU on {port}...")
        connected = client.connect(serial_port=port)
    else:
        print(f"\n[STEP 1] Connecting to Simulator on {port}...")
        host, p = port.split(":") if ":" in port else (port, 29001)
        connected = client.connect_tcp(host, int(p))
    
    if not connected:
        pytest.fail("Failed to connect to simulator handshaking failed.")
        
    print(f"Connected! Signature: {client.last_connected_signature}")
    assert "rusEFI" in client.last_connected_signature
    # STEP 2: Live Data (Framed 'O' with LE params)
    print("\n[STEP 2] Requesting Live Data (Framed 'O' @ 2080 bytes)")
    data = client.get_live_data()
    print(f"RPM: {data.get('rpm', 'N/A')}")
    print(f"MAP: {data.get('map', 'N/A')}")
    print(f"AFR: {data.get('afr', 'N/A')}")
    print(f"CLT: {data.get('clt', 'N/A')}")
    print(f"IAT: {data.get('iat', 'N/A')}")
    print(f"TPS: {data.get('tps', 'N/A')}")
    print(f"VBatt: {data.get('vbatt', 'N/A')}")
    print(f"Duty: {data.get('duty', 'N/A')}")
    print(f"Knock: {data.get('knock', 'N/A')}")
    print(f"Advance: {data.get('advance', 'N/A')}")
    print(f"Uptime: {data.get('uptime', 'N/A')}")
    
    # Assert we got some data
    assert data.get('connected') == True, "OCH request failed"
    # We don't check packet_size directly in dict anymore, but we know it returned something
    assert data.get('rpm') is not None
    
    print("\n[STEP 3] Testing Framed 'R' (Table Read)...")
    # Read first 16 bytes of page 0
    data = client.read_table(0, 0, 16)
    
    if data is None:
        pytest.fail("Table read failed.")
        
    print(f"Table data (16 bytes) hex: {binascii.hexlify(data).decode()}")
    assert len(data) == 16
    
    print("\n[STEP 4] Testing Framed 'P' (Table Write) - if allowed ...")
    client.set_allow_writes(True)
    test_data = bytes([0] * 16)
    write_ok = client.write_table(0, 0, 16, test_data)
    assert write_ok
    print("Table write success!")

    print("\nALL TESTS PASSED")
    client.disconnect()

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    test_binary_protocol_full_sequence(target)
