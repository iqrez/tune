from __future__ import annotations

import logging
import socket
import struct
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import serial
from serial.tools.list_ports import comports

logger = logging.getLogger("RusefiConnector")

# ---------------------------------------------------------
# TunerStudio Binary Protocol Constants (msEnvelope 1.0)
# ---------------------------------------------------------
TS_HELLO_COMMAND = b"H"
TS_QUERY_COMMAND = b"S"
TS_OUTPUT_COMMAND = b"O"
TS_READ_COMMAND = b"R"
TS_WRITE_COMMAND = b"P"
TS_CHUNK_WRITE_COMMAND = b"C"
TS_BURN_COMMAND = b"B"
TS_GET_VERSION_COMMAND = b"V"

# Response codes
TS_RESPONSE_OK = 0x80
TS_RESPONSE_OK_ALT = 0x00
TS_RESPONSE_BURN_OK = 0x84
TS_RESPONSE_CRC_FAILURE = 0x82
TS_RESPONSE_UNRECOGNIZED_COMMAND = 0x83
TS_RESPONSE_OUT_OF_RANGE = 0x84

SIM_TS_PORT = 29001
DEFAULT_OCH_SIZE = 1896
MAX_PACKET_SIZE = 65535


# ---------------------------------------------------------
# CRC32 Helpers (rusEFI standard)
# ---------------------------------------------------------
def rusefi_crc32(data: bytes) -> int:
    """rusEFI CRC32 implementation (bitwise, init/xor per TS protocol)."""
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return (~crc) & 0xFFFFFFFF


def swap32(value: int) -> int:
    return (
        ((value & 0x000000FF) << 24)
        | ((value & 0x0000FF00) << 8)
        | ((value & 0x00FF0000) >> 8)
        | ((value & 0xFF000000) >> 24)
    )


def calculate_packet_crc(payload: bytes) -> bytes:
    return struct.pack(">I", rusefi_crc32(payload))


def verify_incoming_crc(inner_bytes: bytes, received_crc_bytes: bytes) -> bool:
    return calculate_packet_crc(inner_bytes) == received_crc_bytes


class RusefiTunerClient:
    """
    Connector for rusEFI binary protocol over TCP or serial.

    Safety:
    - All write operations require allow_writes=True.
    - Use write_session() to auto-reset write permission in finally blocks.
    """

    TABLES: Dict[str, Dict[str, Any]] = {
        "veTable": {"page": 0, "offset": 16748, "size": 512, "type": "uint16", "scale": 0.1},
        "veTable1": {"page": 0, "offset": 16748, "size": 512, "type": "uint16", "scale": 0.1},
        "veTable2": {"page": 0, "offset": 16748, "size": 512, "type": "uint16", "scale": 0.1},
        "veTable3": {"page": 0, "offset": 16748, "size": 512, "type": "uint16", "scale": 0.1},
        "afrTable1": {"page": 0, "offset": 17324, "size": 256, "type": "uint8", "scale": 1.0},
        "afrTable2": {"page": 0, "offset": 17324, "size": 256, "type": "uint8", "scale": 1.0},
        "lambdaTable": {"page": 0, "offset": 17324, "size": 256, "type": "uint8", "scale": 1.0},
        "lambdaTable1": {"page": 0, "offset": 17324, "size": 256, "type": "uint8", "scale": 1.0},
        "ignitionTable": {"page": 0, "offset": 16172, "size": 512, "type": "int16", "scale": 0.1},
        "ignitionTable1": {"page": 0, "offset": 16172, "size": 512, "type": "int16", "scale": 0.1},
        "ignitionTable2": {"page": 0, "offset": 16172, "size": 512, "type": "int16", "scale": 0.1},
        "boostTableOpenLoop": {"page": 0, "offset": 5336, "size": 64, "type": "uint8", "scale": 1.0},
        "boostTableClosedLoop": {"page": 0, "offset": 5424, "size": 64, "type": "uint8", "scale": 1.0},
        "boostTable1": {"page": 0, "offset": 5336, "size": 64, "type": "uint8", "scale": 1.0},
    }

    def __init__(self):
        self.ser: Optional[serial.Serial] = None
        self._sock: Optional[socket.socket] = None
        self._mode = "none"

        self.connected = False
        self.binary_mode = False
        self.console_mode = False
        self.signature_mode = False
        self.limited_mode = False
        self.allow_writes = False

        self.port_name: Optional[str] = None
        self.connection_type = "none"
        self.last_connected_signature = ""
        self._last_detection: Dict[str, Any] = {"results": [], "warning": "", "binary_port": None, "console_port": None}

        self._och_size = DEFAULT_OCH_SIZE
        self._lock = threading.RLock()
        self._last_cmd_time = 0.0
        self._min_cmd_gap_s = 0.03
        self._read_timeout_s = 1.5
        self._last_target: Dict[str, Any] = {}

    # ---------------------------------------------------------
    # Safety helpers
    # ---------------------------------------------------------
    def set_allow_writes(self, allow: bool):
        self.allow_writes = bool(allow)

    @contextmanager
    def write_session(self):
        prev = self.allow_writes
        self.set_allow_writes(True)
        try:
            yield
        finally:
            self.set_allow_writes(prev)

    # ---------------------------------------------------------
    # IO internals
    # ---------------------------------------------------------
    def _cmd_guard(self):
        elapsed = time.time() - self._last_cmd_time
        if elapsed < self._min_cmd_gap_s:
            time.sleep(self._min_cmd_gap_s - elapsed)
        self._last_cmd_time = time.time()

    def _write(self, data: bytes):
        if self._mode == "tcp" and self._sock:
            self._sock.sendall(data)
            return
        if self._mode == "serial" and self.ser:
            self.ser.write(data)
            self.ser.flush()
            return
        raise RuntimeError("Not connected")

    def _read(self, n: int, timeout: Optional[float] = None) -> bytes:
        timeout = self._read_timeout_s if timeout is None else timeout
        if n <= 0:
            return b""

        buf = b""
        deadline = time.time() + timeout
        if self._mode == "tcp" and self._sock:
            while len(buf) < n:
                left = deadline - time.time()
                if left <= 0:
                    break
                try:
                    self._sock.settimeout(left)
                    chunk = self._sock.recv(n - len(buf))
                    if not chunk:
                        break
                    buf += chunk
                except (socket.timeout, OSError):
                    break
            return buf

        if self._mode == "serial" and self.ser:
            while len(buf) < n:
                left = deadline - time.time()
                if left <= 0:
                    break
                self.ser.timeout = left
                chunk = self.ser.read(n - len(buf))
                if not chunk:
                    break
                buf += chunk
            return buf

        return b""

    def _read_exact(self, n: int, timeout: float) -> bytes:
        buf = b""
        deadline = time.time() + timeout
        while len(buf) < n:
            left = deadline - time.time()
            if left <= 0:
                break
            chunk = self._read(n - len(buf), timeout=min(left, self._read_timeout_s))
            if not chunk:
                break
            buf += chunk
        return buf

    def _reset_input(self):
        if self._mode == "tcp" and self._sock:
            try:
                self._sock.settimeout(0.001)
                while self._sock.recv(4096):
                    pass
            except Exception:
                pass
            return
        if self._mode == "serial" and self.ser:
            try:
                self.ser.reset_input_buffer()
            except Exception:
                pass

    # ---------------------------------------------------------
    # Packet framing
    # ---------------------------------------------------------
    def wrap_packet(self, command: int, payload: bytes = b"") -> bytes:
        inner = bytes([command]) + payload
        size = struct.pack(">H", len(inner))
        return size + inner + calculate_packet_crc(inner)

    def unwrap_packet(self, raw: bytes) -> Tuple[bool, int, bytes]:
        if len(raw) < 2 + 1 + 4:
            return False, 0, b""

        size = struct.unpack(">H", raw[:2])[0]
        if size <= 0 or size > MAX_PACKET_SIZE:
            return False, 0, b""

        expected_len = 2 + size + 4
        if len(raw) < expected_len:
            return False, 0, b""

        inner = raw[2 : 2 + size]
        crc = raw[2 + size : expected_len]
        if not verify_incoming_crc(inner, crc):
            return False, 0, b""

        code = inner[0]
        if code in (
            TS_RESPONSE_OK,
            TS_RESPONSE_OK_ALT,
            TS_RESPONSE_BURN_OK,
            TS_RESPONSE_CRC_FAILURE,
            TS_RESPONSE_UNRECOGNIZED_COMMAND,
            TS_RESPONSE_OUT_OF_RANGE,
        ):
            return True, code, inner[1:]

        # Some responses may omit explicit response code; treat full payload as data.
        return True, TS_RESPONSE_OK, inner

    def _reconnect_last_target(self) -> bool:
        target = dict(self._last_target or {})
        kind = target.get("kind")
        if kind == "tcp":
            return self.connect_tcp(target.get("host", "127.0.0.1"), int(target.get("port", SIM_TS_PORT)))
        if kind == "serial":
            return self._connect_serial(target.get("port", "COM6"))
        return False

    def send_and_receive_binary(self, cmd: int, payload: bytes = b"", max_retries: int = 3) -> Tuple[bool, int, bytes]:
        for _attempt in range(max_retries):
            if not self.connected:
                if not self._reconnect_last_target():
                    return False, 0, b""

            with self._lock:
                try:
                    self._cmd_guard()
                    packet = self.wrap_packet(cmd, payload)
                    self._reset_input()
                    self._write(packet)

                    header = self._read_exact(2, timeout=self._read_timeout_s)
                    if len(header) != 2:
                        continue
                    size = struct.unpack(">H", header)[0]
                    if size <= 0 or size > MAX_PACKET_SIZE:
                        continue

                    body_and_crc = self._read_exact(size + 4, timeout=self._read_timeout_s + 0.8)
                    if len(body_and_crc) != size + 4:
                        continue

                    ok, code, data = self.unwrap_packet(header + body_and_crc)
                    if ok:
                        return ok, code, data
                except Exception as e:
                    logger.debug("Binary exchange failed: %s", e)
                    # try next retry
                    pass
        return False, 0, b""

    # ---------------------------------------------------------
    # Connection / handshake
    # ---------------------------------------------------------
    def handshake(self) -> bool:
        """
        Handshake sequence:
        1) Send naked 'H' + 'S' to capture raw signature text.
        2) Verify framed communications with 'V' or small 'O' read.
        """
        signature_seen = ""
        for _ in range(3):
            try:
                self._reset_input()
                self._write(TS_HELLO_COMMAND)
                time.sleep(0.05)
                self._write(TS_QUERY_COMMAND)
                raw = self._read(1024, timeout=0.8)
                if b"rusEFI" in raw:
                    pos = raw.find(b"rusEFI")
                    sig = raw[pos:].split(b"\x00")[0].split(b"\n")[0].split(b"\r")[0]
                    signature_seen = sig.decode("ascii", errors="ignore").strip()
                    self.last_connected_signature = signature_seen
                    self.signature_mode = True
            except Exception:
                pass

            # Try framed command path regardless of signature text.
            ok_v, _code_v, _data_v = self.send_and_receive_binary(ord(TS_GET_VERSION_COMMAND), b"", max_retries=1)
            if ok_v:
                self.binary_mode = True
                self.console_mode = False
                return True

            ok_o, _code_o, data_o = self.get_live_data_raw(0, 32)
            if ok_o and data_o:
                self.binary_mode = True
                self.console_mode = False
                return True

        # Console-only fallback if we at least identified a signature.
        if signature_seen:
            self.console_mode = True
            self.binary_mode = False
            return True
        return False

    def connect_tcp(self, host: str = "127.0.0.1", port: int = SIM_TS_PORT) -> bool:
        try:
            self.disconnect()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((host, port))
            self._sock = s
            self._mode = "tcp"
            self._last_target = {"kind": "tcp", "host": host, "port": port}
            if not self.handshake():
                self.disconnect()
                return False
            self.connected = True
            self.connection_type = "tcp"
            self.port_name = f"TCP:{host}:{port}"
            return True
        except Exception as e:
            logger.debug("TCP connect failed: %s", e)
            self.disconnect()
            return False

    def _connect_serial(self, port: str) -> bool:
        try:
            self.disconnect()
            p = f"\\\\.\\{port}" if port.upper().startswith("COM") and not port.startswith("\\\\") else port
            self.ser = serial.Serial(p, 115200, timeout=1.0)
            self._mode = "serial"
            self._last_target = {"kind": "serial", "port": port}
            if not self.handshake():
                self.disconnect()
                return False
            self.connected = True
            self.connection_type = "serial"
            self.port_name = port
            return True
        except Exception as e:
            logger.debug("Serial connect failed on %s: %s", port, e)
            self.disconnect()
            return False

    def connect(self, serial_port: Optional[str] = None, tcp_host: Optional[str] = None, tcp_port: int = SIM_TS_PORT) -> bool:
        if tcp_host:
            return self.connect_tcp(tcp_host, tcp_port)
        if serial_port:
            return self._connect_serial(serial_port)

        # Prefer commonly-used rusEFI COM ports first.
        for p in ("COM6", "COM5", "COM4", "COM3"):
            if self._connect_serial(p):
                return True

        for p in comports():
            if self._connect_serial(p.device):
                return True

        return self.connect_tcp("127.0.0.1", SIM_TS_PORT)

    def disconnect(self):
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        try:
            if self.ser:
                self.ser.close()
        except Exception:
            pass

        self._sock = None
        self.ser = None
        self._mode = "none"
        self.connected = False
        self.binary_mode = False
        self.console_mode = False
        self.signature_mode = False
        self.port_name = None
        self.connection_type = "none"

    def is_connected(self) -> bool:
        return bool(self.connected)

    # ---------------------------------------------------------
    # Live data
    # ---------------------------------------------------------
    def get_live_data_raw(self, offset: int, count: int) -> Tuple[bool, int, bytes]:
        payload = struct.pack("<HH", int(offset), int(count))
        return self.send_and_receive_binary(ord(TS_OUTPUT_COMMAND), payload)

    @staticmethod
    def _u16(data: bytes, offset: int, scale: float = 1.0) -> float:
        if offset + 2 > len(data):
            return 0.0
        return struct.unpack("<H", data[offset : offset + 2])[0] * scale

    @staticmethod
    def _s16(data: bytes, offset: int, scale: float = 1.0) -> float:
        if offset + 2 > len(data):
            return 0.0
        return struct.unpack("<h", data[offset : offset + 2])[0] * scale

    @staticmethod
    def _u8(data: bytes, offset: int, scale: float = 1.0) -> float:
        if offset + 1 > len(data):
            return 0.0
        return struct.unpack("<B", data[offset : offset + 1])[0] * scale

    @staticmethod
    def _u32(data: bytes, offset: int, scale: float = 1.0) -> float:
        if offset + 4 > len(data):
            return 0.0
        return struct.unpack("<I", data[offset : offset + 4])[0] * scale

    def parse_output_channels(self, payload: bytes) -> Dict[str, Any]:
        """
        Parse rusEFI output channels by known offsets.
        Works with full 1896-byte layout and larger variants.
        """
        if len(payload) < 290:
            return {"connected": False}

        # Offsets validated against current INI.
        rpm = self._u16(payload, 4, 1.0)
        clt = self._s16(payload, 16, 0.01)
        iat = self._s16(payload, 18, 0.01)
        tps = self._s16(payload, 24, 0.01)
        map_kpa = self._u16(payload, 34, 0.03333333333333333)
        lambda_val = self._u16(payload, 38, 0.0001)
        vbatt = self._u16(payload, 40, 0.001)
        duty = self._u8(payload, 53, 0.5)
        uptime = self._u32(payload, 88, 1.0)
        afr = self._u16(payload, 254, 0.001)
        advance = self._s16(payload, 288, 0.02)
        knock = int(self._u32(payload, 1016, 1.0))

        return {
            "connected": True,
            "rpm": int(round(rpm)),
            "map": round(map_kpa, 2),
            "clt": round(clt, 2),
            "iat": round(iat, 2),
            "tps": round(tps, 2),
            "lambda": round(lambda_val, 4),
            "afr": round(afr, 3),
            "vbatt": round(vbatt, 3),
            "duty": round(duty, 3),
            "advance": round(advance, 3),
            "knock": knock,
            "uptime": int(round(uptime)),
        }

    def get_live_data(self) -> Dict[str, Any]:
        if not self.is_connected():
            return {"connected": False, "status": "disconnected", "rpm": 0}

        probe_counts: List[int] = []
        for size in (self._och_size, DEFAULT_OCH_SIZE, 2080, 884):
            if size not in probe_counts:
                probe_counts.append(size)

        for count in probe_counts:
            ok, _code, data = self.get_live_data_raw(0, count)
            if not ok or not data:
                continue
            parsed = self.parse_output_channels(data)
            if parsed.get("connected"):
                self._och_size = len(data)
                return parsed

        return {"connected": False, "status": "live_read_failed", "rpm": 0}

    def get_live_data_binary(self, offset: int = 0, count: Optional[int] = None) -> bytes:
        if count is None:
            count = self._och_size
        ok, _code, data = self.get_live_data_raw(offset, count)
        return data if ok else b""

    # ---------------------------------------------------------
    # Table operations
    # ---------------------------------------------------------
    def read_table(
        self,
        page_or_name: Any,
        offset: Optional[int] = None,
        count: Optional[int] = None,
        max_retries: int = 2,
    ) -> Optional[bytes]:
        if isinstance(page_or_name, str):
            meta = self.TABLES.get(page_or_name)
            if not meta:
                return None
            page = int(meta["page"])
            off = int(meta["offset"])
            cnt = int(meta["size"])
        else:
            if offset is None or count is None:
                return None
            page = int(page_or_name)
            off = int(offset)
            cnt = int(count)

        payload_le = struct.pack("<HHH", page, off, cnt)
        payload_be = struct.pack(">HHH", page, off, cnt)

        for payload in (payload_le, payload_be):
            ok, code, data = self.send_and_receive_binary(ord(TS_READ_COMMAND), payload, max_retries=max_retries)
            if ok and code in (TS_RESPONSE_OK, TS_RESPONSE_OK_ALT) and len(data) == cnt:
                return data
        return None

    def write_table(
        self,
        page_or_name: Any,
        offset_or_data: Any = None,
        count: Optional[int] = None,
        data: Optional[bytes] = None,
        max_retries: int = 2,
    ) -> bool:
        if not self.allow_writes:
            return False

        if isinstance(page_or_name, str):
            meta = self.TABLES.get(page_or_name)
            if not meta:
                return False
            page = int(meta["page"])
            off = int(meta["offset"])
            cnt = int(meta["size"])
            payload_data = offset_or_data
        else:
            if offset_or_data is None or count is None or data is None:
                return False
            page = int(page_or_name)
            off = int(offset_or_data)
            cnt = int(count)
            payload_data = data

        if not isinstance(payload_data, (bytes, bytearray)):
            return False
        payload_data = bytes(payload_data)
        if len(payload_data) != cnt:
            return False

        payload_le = struct.pack("<HHH", page, off, cnt) + payload_data
        payload_be = struct.pack(">HHH", page, off, cnt) + payload_data

        for cmd in (ord(TS_WRITE_COMMAND), ord(TS_CHUNK_WRITE_COMMAND)):
            for payload in (payload_le, payload_be):
                ok, code, _ = self.send_and_receive_binary(cmd, payload, max_retries=max_retries)
                if ok and code in (TS_RESPONSE_OK, TS_RESPONSE_OK_ALT):
                    return True
        return False

    def burn(self, page: int = 0, max_retries: int = 2) -> bool:
        if not self.allow_writes:
            return False
        payload = struct.pack("<H", int(page))
        ok, code, _ = self.send_and_receive_binary(ord(TS_BURN_COMMAND), payload, max_retries=max_retries)
        return bool(ok and code in (TS_RESPONSE_OK, TS_RESPONSE_OK_ALT, TS_RESPONSE_BURN_OK))

    # ---------------------------------------------------------
    # Discovery / compatibility wrappers
    # ---------------------------------------------------------
    def auto_detect_serial_port(self) -> Optional[str]:
        ports = list(comports())
        if not ports:
            return None
        preferred = [
            p.device
            for p in ports
            if "rusefi" in (p.description or "").lower() or "stm32" in (p.description or "").lower()
        ]
        return preferred[0] if preferred else ports[0].device

    def list_all_ports_with_test(self) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for p in comports():
            desc = p.description or ""
            results.append(
                {
                    "port": p.device,
                    "description": desc,
                    "is_rusefi": ("rusefi" in desc.lower() or "stm32" in desc.lower() or "usb serial" in desc.lower()),
                }
            )
        if not results:
            results.append({"port": "127.0.0.1:29001", "description": "Local Simulator", "is_rusefi": True})
        self._last_detection = {
            "results": results,
            "warning": "",
            "binary_port": self.port_name if self.binary_mode else None,
            "console_port": self.port_name if self.console_mode else None,
        }
        return results

    def get_last_detection(self) -> Dict[str, Any]:
        if not self._last_detection.get("results"):
            self.list_all_ports_with_test()
        self._last_detection["binary_port"] = self.port_name if self.binary_mode else None
        self._last_detection["console_port"] = self.port_name if self.console_mode else None
        return dict(self._last_detection)

    def try_wake_binary(self) -> bool:
        return bool(self.binary_mode and self.connected)

    def wake_binary_port(self, port: str) -> Optional[str]:
        if self._connect_serial(port) and self.binary_mode:
            return self.port_name
        return None

    def force_ecu_wakeup(self, port: str) -> bool:
        return self._connect_serial(port)

    def auto_connect(self, force_port: Optional[str] = None) -> bool:
        if force_port:
            return self._connect_serial(force_port)
        return self.connect()
