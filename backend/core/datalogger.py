import csv
import io
import os
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Tuple


DEFAULT_CHANNELS = [
    "RPM",
    "MAP_kPa",
    "AFR",
    "IAT_C",
    "ECT_C",
    "IgnitionTiming",
    "KnockCount",
    "InjectorDuty_pct",
    "TPS",
    "batteryV",
    "CLT",
    "Lambda",
    "TargetAFR",
    "BoostPsi",
    "FuelPressure",
    "OilTemp",
    "OilPressure",
    "VSS",
    "AccelPedal",
    "WGDC",
]


class DatalogRecorder:
    """
    Threaded recorder for live ECU channels.
    Supports 50ms standard and 10ms high-speed logging.
    """

    def __init__(self, client: Any, db_path: str, max_buffer_rows: int = 50000) -> None:
        self.client = client
        self.db_path = db_path
        self.max_buffer_rows = max_buffer_rows
        self.buffer: Deque[Dict[str, Any]] = deque(maxlen=max_buffer_rows)

        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._session_id: Optional[str] = None
        self._session_filename: Optional[str] = None
        self._interval = 0.05
        self._last_flush_ts = 0.0
        self._total_samples = 0
        self._dropped_samples = 0
        self._disconnect_detected = False
        self._profile_id = "unknown"

        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS datalog_sessions (
                    session_id TEXT PRIMARY KEY,
                    filename TEXT UNIQUE,
                    created_at REAL,
                    stopped_at REAL,
                    profile_id TEXT,
                    sample_interval_ms INTEGER,
                    total_samples INTEGER DEFAULT 0,
                    dropped_samples INTEGER DEFAULT 0,
                    disconnected_mid_log INTEGER DEFAULT 0,
                    notes TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS datalog_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp REAL,
                    RPM REAL,
                    MAP_kPa REAL,
                    AFR REAL,
                    IAT_C REAL,
                    ECT_C REAL,
                    IgnitionTiming REAL,
                    KnockCount REAL,
                    InjectorDuty_pct REAL,
                    TPS REAL,
                    batteryV REAL,
                    CLT REAL,
                    Lambda REAL,
                    TargetAFR REAL,
                    BoostPsi REAL,
                    FuelPressure REAL,
                    OilTemp REAL,
                    OilPressure REAL,
                    VSS REAL,
                    AccelPedal REAL,
                    WGDC REAL,
                    raw_json TEXT,
                    FOREIGN KEY(session_id) REFERENCES datalog_sessions(session_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_datalog_samples_session_ts ON datalog_samples(session_id, timestamp)")
            conn.commit()
        finally:
            conn.close()

    def is_recording(self) -> bool:
        return self._running

    def is_paused(self) -> bool:
        return self._paused

    def start(self, profile_id: str = "unknown", high_speed: bool = False, filename: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            if self._running:
                return {"status": "already_running", "session_id": self._session_id, "filename": self._session_filename}

            now = time.time()
            stamp = datetime.utcfromtimestamp(now).strftime("%Y%m%d_%H%M%S")
            self._session_id = f"log_{stamp}_{int(now * 1000)}"
            self._profile_id = profile_id or "unknown"
            self._session_filename = filename or f"{self._profile_id}_{stamp}.msl"
            self._interval = 0.01 if high_speed else 0.05
            self.buffer.clear()
            self._running = True
            self._paused = False
            self._last_flush_ts = now
            self._total_samples = 0
            self._dropped_samples = 0
            self._disconnect_detected = False

            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO datalog_sessions(session_id, filename, created_at, profile_id, sample_interval_ms)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (self._session_id, self._session_filename, now, self._profile_id, int(self._interval * 1000)),
                )
                conn.commit()
            finally:
                conn.close()

            self._thread = threading.Thread(target=self._record_loop, name="DatalogRecorder", daemon=True)
            self._thread.start()

            return {
                "status": "started",
                "session_id": self._session_id,
                "filename": self._session_filename,
                "sample_interval_ms": int(self._interval * 1000),
            }

    def pause(self) -> Dict[str, Any]:
        with self._lock:
            if not self._running:
                return {"status": "not_running"}
            self._paused = True
            return {"status": "paused", "session_id": self._session_id}

    def resume(self) -> Dict[str, Any]:
        with self._lock:
            if not self._running:
                return {"status": "not_running"}
            self._paused = False
            return {"status": "resumed", "session_id": self._session_id}

    def stop(self, filename: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            if not self._running:
                return {"status": "not_running"}
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        with self._lock:
            if filename:
                self._session_filename = filename
            self._flush_buffer_locked(force=True)
            self._finalize_session_locked()

            return {
                "status": "stopped",
                "session_id": self._session_id,
                "filename": self._session_filename,
                "samples": self._total_samples,
                "dropped_samples": self._dropped_samples,
                "disconnected_mid_log": self._disconnect_detected,
            }

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            created_at = self._session_created_at(self._session_id) if self._session_id else None
            elapsed = max(0.0, time.time() - created_at) if created_at else 0.0
            return {
                "recording": self._running,
                "paused": self._paused,
                "session_id": self._session_id,
                "filename": self._session_filename,
                "samples": self._total_samples,
                "dropped_samples": self._dropped_samples,
                "elapsed_sec": elapsed,
                "sample_interval_ms": int(self._interval * 1000),
                "disconnected_mid_log": self._disconnect_detected,
                "buffer_size": len(self.buffer),
            }

    def _session_created_at(self, session_id: Optional[str]) -> Optional[float]:
        if not session_id:
            return None
        conn = self._connect()
        try:
            row = conn.execute("SELECT created_at FROM datalog_sessions WHERE session_id = ?", (session_id,)).fetchone()
            return float(row["created_at"]) if row else None
        finally:
            conn.close()

    def _record_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                paused = self._paused
                interval = self._interval

            if paused:
                time.sleep(0.05)
                continue

            ts = time.time()
            sample = self._read_sample(ts)
            with self._lock:
                if sample is None:
                    self._disconnect_detected = True
                    self._flush_buffer_locked(force=True)
                    self._running = False
                    break

                if len(self.buffer) == self.max_buffer_rows:
                    self._dropped_samples += 1
                self.buffer.append(sample)
                self._total_samples += 1

                if ts - self._last_flush_ts >= 5.0:
                    self._flush_buffer_locked(force=True)
                    self._last_flush_ts = ts

            time.sleep(interval)

    def _read_sample(self, timestamp: float) -> Optional[Dict[str, Any]]:
        try:
            data = self.client.get_live_data() or {}
            if not data:
                return None

            sample = {"timestamp": timestamp}
            for ch in DEFAULT_CHANNELS:
                sample[ch] = float(data.get(ch, 0.0) or 0.0)
            sample["raw_json"] = json_dumps_safe(data)
            return sample
        except Exception:
            return None

    def _flush_buffer_locked(self, force: bool = False) -> None:
        if not self.buffer and not force:
            return
        if not self.buffer:
            return

        rows = list(self.buffer)
        self.buffer.clear()

        conn = self._connect()
        try:
            conn.executemany(
                """
                INSERT INTO datalog_samples(
                    session_id, timestamp, RPM, MAP_kPa, AFR, IAT_C, ECT_C, IgnitionTiming,
                    KnockCount, InjectorDuty_pct, TPS, batteryV, CLT, Lambda, TargetAFR,
                    BoostPsi, FuelPressure, OilTemp, OilPressure, VSS, AccelPedal, WGDC, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        self._session_id,
                        r["timestamp"],
                        r["RPM"],
                        r["MAP_kPa"],
                        r["AFR"],
                        r["IAT_C"],
                        r["ECT_C"],
                        r["IgnitionTiming"],
                        r["KnockCount"],
                        r["InjectorDuty_pct"],
                        r["TPS"],
                        r["batteryV"],
                        r["CLT"],
                        r["Lambda"],
                        r["TargetAFR"],
                        r["BoostPsi"],
                        r["FuelPressure"],
                        r["OilTemp"],
                        r["OilPressure"],
                        r["VSS"],
                        r["AccelPedal"],
                        r["WGDC"],
                        r["raw_json"],
                    )
                    for r in rows
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def _finalize_session_locked(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE datalog_sessions
                SET stopped_at = ?, total_samples = ?, dropped_samples = ?, disconnected_mid_log = ?, filename = ?
                WHERE session_id = ?
                """,
                (
                    time.time(),
                    self._total_samples,
                    self._dropped_samples,
                    1 if self._disconnect_detected else 0,
                    self._session_filename,
                    self._session_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()


class DatalogViewer:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def list_recent_logs(self, limit: int = 25) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT filename, session_id, created_at, stopped_at, total_samples, dropped_samples
                FROM datalog_sessions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def load_log(self, filename: str, downsample_max: int = 100000) -> Dict[str, Any]:
        conn = self._connect()
        try:
            session = conn.execute(
                "SELECT session_id, created_at, stopped_at, total_samples FROM datalog_sessions WHERE filename = ?",
                (filename,),
            ).fetchone()
            if not session:
                raise FileNotFoundError(f"Log not found: {filename}")

            rows = conn.execute(
                "SELECT * FROM datalog_samples WHERE session_id = ? ORDER BY timestamp ASC",
                (session["session_id"],),
            ).fetchall()
        finally:
            conn.close()

        data_rows = [dict(r) for r in rows]
        if len(data_rows) > downsample_max:
            step = max(1, len(data_rows) // downsample_max)
            data_rows = data_rows[::step]

        return self._post_process_log(filename, data_rows)

    def import_log_file(self, file_path: str, profile_id: str = "imported") -> str:
        ext = os.path.splitext(file_path)[1].lower()
        with open(file_path, "rb") as f:
            blob = f.read()

        rows = []
        if ext in (".csv", ".msl", ".mlv"):
            rows = self._parse_tunerstudio_text(blob)
        else:
            rows = self._parse_tunerstudio_text(blob)

        if not rows:
            raise ValueError("No readable rows found in log file")

        now = time.time()
        stamp = datetime.utcfromtimestamp(now).strftime("%Y%m%d_%H%M%S")
        filename = f"{profile_id}_import_{stamp}.msl"
        session_id = f"import_{stamp}_{int(now * 1000)}"

        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO datalog_sessions(session_id, filename, created_at, stopped_at, profile_id, sample_interval_ms, total_samples)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, filename, now, now, profile_id, 50, len(rows)),
            )
            conn.executemany(
                """
                INSERT INTO datalog_samples(
                    session_id, timestamp, RPM, MAP_kPa, AFR, IAT_C, ECT_C, IgnitionTiming,
                    KnockCount, InjectorDuty_pct, TPS, batteryV, CLT, Lambda, TargetAFR,
                    BoostPsi, FuelPressure, OilTemp, OilPressure, VSS, AccelPedal, WGDC, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        session_id,
                        float(r.get("timestamp", now + i * 0.05)),
                        float(r.get("RPM", 0.0)),
                        float(r.get("MAP_kPa", 0.0)),
                        float(r.get("AFR", 0.0)),
                        float(r.get("IAT_C", 0.0)),
                        float(r.get("ECT_C", 0.0)),
                        float(r.get("IgnitionTiming", 0.0)),
                        float(r.get("KnockCount", 0.0)),
                        float(r.get("InjectorDuty_pct", 0.0)),
                        float(r.get("TPS", 0.0)),
                        float(r.get("batteryV", 0.0)),
                        float(r.get("CLT", 0.0)),
                        float(r.get("Lambda", 0.0)),
                        float(r.get("TargetAFR", 14.7)),
                        float(r.get("BoostPsi", 0.0)),
                        float(r.get("FuelPressure", 0.0)),
                        float(r.get("OilTemp", 0.0)),
                        float(r.get("OilPressure", 0.0)),
                        float(r.get("VSS", 0.0)),
                        float(r.get("AccelPedal", 0.0)),
                        float(r.get("WGDC", 0.0)),
                        json_dumps_safe(r),
                    )
                    for i, r in enumerate(rows)
                ],
            )
            conn.commit()
        finally:
            conn.close()

        return filename

    def export_log(self, filename: str, fmt: str = "csv") -> bytes:
        log = self.load_log(filename, downsample_max=5_000_000)
        rows = log.get("rows", [])
        if not rows:
            return b""

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        data = output.getvalue().encode("utf-8")

        if fmt.lower() in ("csv", "msl"):
            return data
        return data

    def anonymize_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        scrub = {"GPSLat", "GPSLon", "GPSAlt", "GPS_Speed"}
        rows = []
        for row in log_data.get("rows", []):
            clean = {k: v for k, v in row.items() if k not in scrub}
            rows.append(clean)
        out = dict(log_data)
        out["rows"] = rows
        return out

    def _post_process_log(self, filename: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        for r in rows:
            target = float(r.get("TargetAFR", 14.7) or 14.7)
            afr = float(r.get("AFR", 0.0) or 0.0)
            ign = float(r.get("IgnitionTiming", 0.0) or 0.0)
            base_ign = float(r.get("BaseIgnition", ign) or ign)
            knock = float(r.get("KnockCount", 0.0) or 0.0)

            r["AFR_error"] = (afr - target) / target if target else 0.0
            r["KnockRetard"] = (ign - base_ign) if knock > 0 else 0.0

        return {
            "filename": filename,
            "rows": rows,
            "channels": sorted(list(rows[0].keys())) if rows else [],
            "samples": len(rows),
        }

    def _parse_tunerstudio_text(self, blob: bytes) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        text = None
        for enc in ("utf-8", "utf-16", "latin-1"):
            try:
                text = blob.decode(enc, errors="ignore")
                if text:
                    break
            except Exception:
                continue

        if not text:
            return rows

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return rows

        header_line = lines[0]
        delimiter = "," if header_line.count(",") >= header_line.count("\t") else "\t"
        headers = [h.strip() for h in header_line.split(delimiter)]
        header_map = map_headers(headers)

        bad_rows = 0
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(delimiter)]
            if len(parts) < 2:
                continue
            try:
                item: Dict[str, Any] = {}
                for idx, key in enumerate(headers):
                    if idx >= len(parts):
                        continue
                    canonical = header_map.get(key, key)
                    value = safe_float(parts[idx])
                    item[canonical] = value

                if "timestamp" not in item:
                    item["timestamp"] = time.time() + len(rows) * 0.05
                rows.append(item)
            except Exception:
                bad_rows += 1
                if bad_rows > 500:
                    break
                continue

        return rows


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def json_dumps_safe(value: Any) -> str:
    try:
        return json.dumps(value, separators=(",", ":"))
    except Exception:
        return "{}"


def map_headers(headers: List[str]) -> Dict[str, str]:
    mapping = {}
    for h in headers:
        key = h.strip()
        lower = key.lower()
        if lower in ("time", "timestamp", "ts"):
            mapping[key] = "timestamp"
        elif lower in ("rpm",):
            mapping[key] = "RPM"
        elif lower in ("map", "map_kpa", "map(kpa)"):
            mapping[key] = "MAP_kPa"
        elif lower in ("afr",):
            mapping[key] = "AFR"
        elif lower in ("iat", "iat_c"):
            mapping[key] = "IAT_C"
        elif lower in ("ect", "clt", "clt_c"):
            mapping[key] = "ECT_C"
        elif lower in ("ignitiontiming", "ign", "spark"):
            mapping[key] = "IgnitionTiming"
        elif lower in ("knockcount", "knock"):
            mapping[key] = "KnockCount"
        elif lower in ("injectorduty", "injectorduty_pct", "duty"):
            mapping[key] = "InjectorDuty_pct"
        elif lower in ("tps", "throttle"):
            mapping[key] = "TPS"
        elif lower in ("batt", "battv", "batteryv"):
            mapping[key] = "batteryV"
        elif lower in ("targetafr", "afr_target"):
            mapping[key] = "TargetAFR"
        else:
            mapping[key] = key
    return mapping

