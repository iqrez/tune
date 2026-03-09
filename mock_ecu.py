import socket
import struct
import binascii

class MockRusefi:
    def __init__(self, port=29001):
        self.port = port
        self.page0 = bytearray(32768) # 32KB Settings page (real is 23936)

    def crc32(self, data: bytes) -> int:
        return binascii.crc32(data) & 0xFFFFFFFF

    def wrap(self, code, data=b''):
        payload = bytes([code]) + data
        header = struct.pack(">H", len(payload))
        crc = struct.pack(">I", self.crc32(payload))
        return header + payload + crc

    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', self.port))
        server.listen(1)
        print(f"📡 Mock rusEFI listening on {self.port}...")

        while True:
            conn, addr = server.accept()
            print(f"🤝 Connected: {addr}")
            try:
                while True:
                    # rusEFI can receive simple 'H' (1 byte) or framed packet
                    head = conn.recv(1)
                    if not head: break
                    
                    if head == b'H':
                        print("Simple Handshake (H)")
                        conn.sendall(b"rusEFI Mock Identification String")
                        continue
                    if head == b'S':
                        print("Simple Signature (S)")
                        conn.sendall(b"rusEFI mock.signature.123")
                        continue
                    
                    # If not 'H' or 'S', assume it's the start of a framed packet (length MSB)
                    head2 = conn.recv(1)
                    if not head2: break
                    
                    length = struct.unpack(">H", head + head2)[0]
                    body = conn.recv(length + 4)
                    
                    payload = body[:-4]
                    received_crc = struct.unpack(">I", body[-4:])[0]
                    
                    if self.crc32(payload) != received_crc:
                        print("❌ CRC Error in request!")
                        continue

                    cmd = payload[0:1]
                    data = payload[1:]
                    
                    if cmd == b'H':
                        print("Handshake (H)")
                        conn.sendall(self.wrap(0x80, b"rusEFI Mock v1.0"))
                    elif cmd == b'S':
                        print("Signatureframed (S)")
                        conn.sendall(self.wrap(0x80, b"rusEFI mock.signature.123"))
                    elif cmd == b'O':
                        print("Output Channels (O)")
                        # Dummy 16 bytes telemetry
                        conn.sendall(self.wrap(0x80, struct.pack(">HHHHHHHH", 800, 1013, 1470, 250, 850, 100, 0, 50)))
                    elif cmd == b'R':
                        page, offset, count = struct.unpack("<HHH", data)
                        print(f"Read (R) Page={page} Offset={offset} Count={count}")
                        conn.sendall(self.wrap(0x80, bytes(self.page0[offset:offset+count])))
                    elif cmd == b'C':
                        page, offset, count = struct.unpack("<HHH", data[:6])
                        print(f"Write (C) Page={page} Offset={offset} Count={count}")
                        self.page0[offset:offset+count] = data[6:6+count]
                        conn.sendall(self.wrap(0x80))
                    elif cmd == b'B':
                        print("Burn (B)")
                        conn.sendall(self.wrap(0x80))
                    else:
                        print(f"Unknown command: {cmd}")
            except Exception as e:
                print(f"Error: {e}")
            finally:
                conn.close()

if __name__ == "__main__":
    MockRusefi().run()
