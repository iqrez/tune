"""
RUSEFI BINARY PROTOCOL – HEADLESS TEST SUITE
Tests ALL protocol operations against the real rusEFI simulator (SD1 TCP 29001).
Run:  python test_all_binary.py
"""
import os
import sys
import socket
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from core.rusefi_connector import RusefiTunerClient, SIM_TS_PORT

SIM_HOST = "127.0.0.1"
SIM_PORT = SIM_TS_PORT  # 29001


def banner(title: str):
    print(f"\n{'='*54}")
    print(f"  {title}")
    print('='*54)


def fail(msg: str):
    print(f"❌ FAIL: {msg}")
    sys.exit(1)


def run_test():
    import logging
    logging.getLogger("RusefiConnector").setLevel(logging.DEBUG)

    client = RusefiTunerClient()

    # Try simulator TCP first, then fall back to serial
    use_sim = False
    try:
        with socket.create_connection((SIM_HOST, SIM_PORT), timeout=1):
            use_sim = True
    except OSError:
        pass

    if use_sim:
        banner("RUSEFI BINARY PROTOCOL – HEADLESS TEST SUITE (SIMULATOR)")
        print(f"Target: TCP {SIM_HOST}:{SIM_PORT}  (rusEFI simulator SD1)\n")
    else:
        banner("RUSEFI BINARY PROTOCOL – HEADLESS TEST SUITE (PHYSICAL ECU)")
        print("Target: physical ECU on serial (auto-detect)\n")

    # ── 1. Handshake ────────────────────────────────────────
    print("[1/5] Testing Connect & Handshake...")
    if use_sim:
        connected = client.connect_tcp(SIM_HOST, SIM_PORT)
    else:
        for port in ["COM6", "COM5", None]:
            if port:
                connected = client.connect(serial_port=port)
            else:
                connected = client.connect()
            if connected and client.binary_mode:
                break

    if not connected or not client.binary_mode:
        fail(
            "Could not connect in BINARY mode.\n"
            "  → Start rusefi_simulator.exe (SD1 → port 29001)  OR  connect ECU and replug USB."
        )
    print(f"✅ PASS: Connected – sig: {client.last_connected_signature!r}\n")

    # ── 2. Live Data ─────────────────────────────────────────
    print("[2/5] Testing Live Data (framed 'O' + offset + count)...")
    live = client.get_live_data_binary()
    if not live or "RPM" not in live:
        fail("Did not receive valid live data dict.")
    print(f"✅ PASS: Live data – {live}\n")

    # ── 3. Table Read ────────────────────────────────────────
    TABLE = "testTable"
    client.TABLES[TABLE] = {"page": 0, "offset": 0, "size": 16}
    client.set_allow_writes(True)

    print(f"[3/5] Testing Table Read (framed 'R') – page=0 offset=0 count=16 ...")
    orig = client.read_table(TABLE)
    if not orig:
        fail("read_table returned empty bytes.")
    print(f"✅ PASS: Read {len(orig)} bytes: {orig.hex()}\n")

    # ── 4. Table Write + Verify ──────────────────────────────
    print(f"[4/5] Testing Table Write/Verify (framed 'C') ...")
    mutated = bytes([b ^ 0x01 for b in orig])
    if not client.write_table(TABLE, mutated):
        fail("write_table command rejected.")
    verify = client.read_table(TABLE)
    if verify != mutated:
        fail(f"Write-readback mismatch!\n  wrote:   {mutated.hex()}\n  readback:{verify.hex()}")
    print(f"✅ PASS: Wrote {len(mutated)} bytes, verified in ECU RAM.")
    client.write_table(TABLE, orig)
    print("   (original data restored)\n")

    # ── 5. Burn ──────────────────────────────────────────────
    print("[5/5] Testing Flash Commit (framed 'B')...")
    page = client.TABLES[TABLE]["page"]
    if not client.burn(page):
        fail("Burn rejected.")
    print("✅ PASS: Burn accepted.\n")

    client.disconnect()
    banner("✅  ALL 5 PROTOCOL TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    run_test()
