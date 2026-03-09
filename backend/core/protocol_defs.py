"""
rusEFI Binary Protocol Definitions (Serial Protocol 3.0)
Based on firmware/console/binary/tunerstudio.cpp
"""

# Protocol Framing
TS_PACKET_HEADER_SIZE = 2  # 16-bit length
TS_PACKET_TAIL_SIZE = 4    # 32-bit CRC
TS_RESPONSE_OK = 0x80      # Standard success response code

# Commands
TS_HELLO = b'H'              # Handshake / Hello
TS_OUTPUT = b'O'             # Live Data (Output Channels)
TS_READ = b'R'               # Read Page Chunk
TS_WRITE = b'C'              # Write Page Chunk (Chunk Write)
TS_BURN = b'B'               # Burn to Flash
TS_GET_VERSION = b'V'        # Get Firmware Version
TS_GET_TEXT = b'T'           # Get Text Console Buffer

# Page Definitions
TS_PAGE_SETTINGS = 0x0000
TS_PAGE_SCATTER = 0x0100     # High speed scatter read offsets
TS_PAGE_LTFT = 0x0200        # Long Term Fuel Trim
