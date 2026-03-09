import struct
import binascii

def rusefi_crc32(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xEDB88320 if crc & 1 else crc >> 1
    return (~crc) & 0xFFFFFFFF

def swap32(v: int) -> int:
    return ((v & 0x000000FF) << 24) | ((v & 0x0000FF00) << 8) | ((v & 0x00FF0000) >> 8) | ((v & 0xFF000000) >> 24)

def calculate_packet_crc(payload: bytes) -> bytes:
    crc = rusefi_crc32(payload)
    return struct.pack(">I", swap32(crc))

print("Testing 'H' CRC:")
crc_h = rusefi_crc32(b'H')
print(f"CRC of 'H': 0x{crc_h:08x}")
pkt_crc_h = calculate_packet_crc(b'H')
print(f"Packet CRC bytes: {binascii.hexlify(pkt_crc_h)}")
