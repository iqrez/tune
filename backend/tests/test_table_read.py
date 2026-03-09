
import logging
import sys
import os
import struct

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.rusefi_connector import RusefiTunerClient, TS_READ_COMMAND

logging.basicConfig(level=logging.DEBUG)

def test_large_read(port="COM5", page=3, offset=0, size=1024):
    client = RusefiTunerClient()
    print(f"Connecting to {port}...")
    if port.startswith("COM") or "/" in port:
        connected = client.connect(serial_port=port)
    else:
        host, p = port.split(":") if ":" in port else (port, 29001)
        connected = client.connect_tcp(host, int(p))
        
    if not connected:
        print("Failed to connect")
        return

    print(f"Testing Read: Page {page}, Offset {offset}, Size {size}")
    # TS_READ_COMMAND is b'R'
    payload = struct.pack('>HHH', page, offset, size)
    ok, code, data = client.send_and_receive_binary(ord(TS_READ_COMMAND), payload)
    
    if ok:
        print(f"Success! Received {len(data)} bytes (code=0x{code:02X})")
    else:
        print(f"Failed! Code=0x{code:02X}, Data={data}")

    if size > 256:
        print("\nTesting Chunked Read (256 bytes)...")
        chunk_size = 256
        total_data = b''
        all_ok = True
        for i in range(0, size, chunk_size):
            p = struct.pack('>HHH', page, offset + i, chunk_size)
            ok, code, chunk = client.send_and_receive_binary(ord(TS_READ_COMMAND), p)
            if ok:
                total_data += chunk
                print(f"  Chunk {i//chunk_size} ok: {len(chunk)} bytes")
            else:
                print(f"  Chunk {i//chunk_size} failed: {code}")
                all_ok = False
                break
        if all_ok:
            print(f"Chunked read success! Total {len(total_data)} bytes")

    client.disconnect()

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    test_large_read(target)
