import argparse
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "backend"))
from core.rusefi_connector import RusefiTunerClient


def print_results(results):
    if not results:
        print("RESULT: NO_PORTS_FOUND")
        return
    for r in results:
        role_raw = r.get("port_role", "none")
        role = "Binary" if role_raw == "binary" else ("Console" if role_raw == "console" else "None")
        match = "MATCH" if r.get("is_rusefi") else "FAIL"
        detail = r.get("error") or r.get("response_text") or "NO_DATA"
        bh = r.get("raw_hex_binary") or ""
        sh = r.get("raw_hex_signature") or ""
        st = r.get("signature_text") or ""
        ch = r.get("raw_hex_console") or ""
        print(
            f"PORT: {r.get('port')} | BAUD: {r.get('baud')} | ROLE: {role} | STATUS: {match} | "
            f"DETAIL: {detail} | SIG: {st} | BIN_HEX: {bh} | SIG_HEX: {sh} | CON_HEX: {ch}"
        )


def run_diagnostics(wake_binary_port=None, try_higher_from=None):
    client = RusefiTunerClient()

    print("--- DIAGNOSTIC START ---")
    print("[1] Initial scan")
    results = client.list_all_ports_with_test()
    print_results(results)

    if wake_binary_port:
        print(f"[2] Wake binary attempt from console port: {wake_binary_port}")
        binary = client.try_wake_and_handshake(wake_binary_port)
        if binary:
            print(f"WAKE_BINARY: SUCCESS -> {wake_binary_port}")
        else:
            print("WAKE_BINARY: FAIL")

        print("[3] Re-scan after wake")
        results = client.list_all_ports_with_test()
        print_results(results)

    print("[4] Auto-Connect Test")
    detected = client.auto_detect_serial_port()
    if detected:
        print(f"AUTO_DETECT: Found ECU at {detected}")
    else:
        print("AUTO_DETECT: No robust ECU connection found.")

    detection = client.get_last_detection()
    print("DETECTION_WARNING:", detection.get("warning", ""))
    results = detection.get("results", []) or []
    has_sig = any("rusEFI" in str(r.get("signature_text", "")) for r in results)
    if detection.get("console_port") and not detection.get("binary_port") and has_sig:
        print("CONCLUSION: Signature-mode detected on console port (queryCommand 'S' works), but TS binary framing is unavailable.")
        print("NEXT ACTION: use console fallback now; full table/tune features require implementing this firmware's transport profile.")
    elif detection.get("console_port") and not detection.get("binary_port"):
        print("CONCLUSION: Console-only firmware detected.")
        print("RECOMMENDED FIX:")
        print("  1) Download latest rusEFI firmware bundle")
        print("  2) Hold PROG and replug USB (bootloader mode)")
        print("  3) Run rusefi_console.exe -> Update Firmware")
        print("  4) Replug ECU and run diagnostics again")
    print("--- DIAGNOSTIC END ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="rusEFI dual-port diagnostics")
    parser.add_argument("--wake-binary", dest="wake_binary", default=None, help="Console COM port to trigger binary wake, e.g. COM3")
    parser.add_argument("--try-higher", dest="try_higher", default=None, help="Try higher COM ports for binary handshake, e.g. COM3")
    args = parser.parse_args()
    run_diagnostics(wake_binary_port=args.wake_binary, try_higher_from=args.try_higher)
