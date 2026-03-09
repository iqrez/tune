
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import struct

# Add project root to path
sys.path.insert(0, os.getcwd())

from backend.core.rusefi_connector import RusefiTunerClient, TS_HELLO_COMMAND

class TestLegacyFallback(unittest.TestCase):
    def setUp(self):
        self.client = RusefiTunerClient()
        self.client.ser = MagicMock()
        self.client._mode = 'serial'

    def test_binary_handshake_success(self):
        # Mock successful binary handshake
        # Packet: [Size:2][Code:1][Payload:rusefi][CRC:4]
        payload = b"rusefi_test"
        size = 1 + len(payload)
        header = struct.pack(">H", size)
        inner = b'\x80' + payload # Assuming 0x80 is OK
        crc = struct.pack(">I", 0) # Mock CRC
        
        self.client._read = MagicMock(side_effect=[header, inner + crc])
        
        # We need to bypass the actual send_and_receive_binary or mock its internal calls
        with patch.object(self.client, 'send_and_receive_binary', return_value=(True, 0x80, payload)):
            res = self.client.handshake()
            self.assertTrue(res)
            self.assertTrue(self.client.binary_mode)
            self.assertFalse(self.client.console_mode)

    def test_console_fallback_success(self):
        # 1. Binary handshake fails (timeout)
        # 2. Naked 'S' fails (timeout)
        # 3. Console 't' returns data
        
        # Mock _read to return empty for binary attempts, then console data
        # handshake calls:
        # 1. send_and_receive_binary -> fails
        # 2. _write(S) -> _read(256) -> empty
        # 3. _write(\r\n), _write(t\r\n) -> _read(256) -> "rpm: 800 uptime: 10s"
        
        self.client.send_and_receive_binary = MagicMock(return_value=(False, 0, b''))
        
        def mock_read(n, timeout=1.0):
            if timeout == 1.0 and n == 256:
                # This could be the naked 'S' call or 't' call
                # We'll use a counter or check internal state if possible, 
                # but simplest is to return empty first then data
                if not hasattr(self, '_read_count'): self._read_count = 0
                self._read_count += 1
                if self._read_count == 1: return b"" # Naked S fails
                return b"rpm: 850 uptime: 120s CLT: 85.0 IAT: 30.0"
            return b""

        self.client._read = mock_read
        
        res = self.client.handshake()
        self.assertTrue(res)
        self.assertFalse(self.client.binary_mode)
        self.assertTrue(self.client.console_mode)
        
    def test_live_data_console_parsing(self):
        self.client.console_mode = True
        self.client._read = MagicMock(return_value=b"rpm: 1200 uptime: 50s CLT: 90 IAT: 25 MAP: 45.5 AFR: 14.7")
        
        data = self.client.get_live_data()
        self.assertEqual(data["RPM"], 1200)
        self.assertEqual(data["Uptime_s"], 50)
        self.assertEqual(data["MAP_kPa"], 45.5)
        self.assertEqual(data["AFR"], 14.7)
        self.assertEqual(data["ECT_C"], 90)
        self.assertEqual(data["IAT_C"], 25)

    def test_read_parameter_console(self):
        # Mock "get EngineDisplacement" -> "Value is 2.0"
        self.client._read = MagicMock(return_value=b"Value is 2.0\r\n>")
        val = self.client.read_parameter_console("EngineDisplacement")
        self.assertEqual(val, 2.0)

    def test_write_parameter_console(self):
        # Mock "set EngineDisplacement 2.5" -> "EngineDisplacement set to 2.5\r\n>"
        self.client._read = MagicMock(return_value=b"EngineDisplacement set to 2.5\r\n>")
        res = self.client.write_parameter_console("EngineDisplacement", 2.5)
        self.assertTrue(res)

    def test_write_parameter_console_failure(self):
        # Mock failure
        self.client._read = MagicMock(return_value=b"Error: unknown command\r\n>")
        res = self.client.write_parameter_console("EngineDisplacement", 2.5)
        self.assertFalse(res)

if __name__ == '__main__':
    unittest.main()
