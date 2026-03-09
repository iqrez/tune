import httpx
import json
import logging
import os
from pathlib import Path
from typing import Optional, Any, List, Dict

logger = logging.getLogger("ApiClient")


class RusefiApiClient:
    """Async HTTP client for the BaseTune Architect backend API (FastAPI on port 8000)."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or self._discover_base_url()
        # Keep UI responsive when probing stale ports (.port can be outdated).
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=0.6))
        self.last_connect_error: str = ""
        logger.info(f"ApiClient using base_url={self.base_url}")

    @staticmethod
    def _discover_base_url() -> str:
        # Prefer explicit env var, then .port files near this repo, then fallback.
        default = "http://127.0.0.1:8000/api/v1"
        env_url = os.getenv("BASETUNE_API_BASE_URL", "").strip()
        if env_url:
            return env_url.rstrip("/")
        try:
            here = Path(__file__).resolve()
            # api_client.py -> ui -> frontend_pyqt -> basetune_architect
            repo_root = here.parents[2]
            cwd = Path.cwd()
            candidates = [cwd / ".port", cwd / "backend" / ".port", repo_root / ".port", repo_root / "backend" / ".port"]

            # Also scan a few ancestor dirs to handle unexpected launch CWDs.
            for parent in list(cwd.parents)[:6]:
                candidates.append(parent / ".port")
                candidates.append(parent / "backend" / ".port")

            for p in candidates:
                if not p.exists():
                    continue
                raw = p.read_text(encoding="utf-8").strip()
                if not raw:
                    continue
                port = int(raw)
                if port > 0:
                    return f"http://127.0.0.1:{port}/api/v1"
        except Exception:
            pass
        return default

    def _refresh_base_url(self):
        self.base_url = self._discover_base_url()

    def _candidate_base_urls(self) -> List[str]:
        out: List[str] = []

        def add(url: str):
            u = (url or "").rstrip("/")
            if u and u not in out:
                out.append(u)

        add(self.base_url)
        add(self._discover_base_url())

        # Common local backend ports used in this project.
        for port in (8000, 8001, 8002, 8003):
            add(f"http://127.0.0.1:{port}/api/v1")

        return out

    async def _request_with_fallback(self, method: str, endpoint: str, **kwargs):
        last_exc: Optional[Exception] = None
        for base in self._candidate_base_urls():
            url = f"{base}{endpoint}"
            try:
                resp = await self.client.request(method, url, **kwargs)
                self.base_url = base
                return resp
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as e:
                last_exc = e
                continue
            except Exception as e:
                last_exc = e
                continue
        if last_exc:
            raise last_exc
        raise httpx.ConnectError("All connection attempts failed")

    # ------------------------------------------------------------------ ECU Connection
    async def connect(self, port: Optional[str] = None) -> bool:
        self.last_connect_error = ""
        attempted_ports: List[Optional[str]] = []
        connect_timeout = httpx.Timeout(20.0, connect=1.0)

        if port:
            attempted_ports = [port]
        else:
            # Honda/uaEFI preferred order first, then backend auto-detect and simulator fallback.
            attempted_ports = ["COM5", "COM6", "COM4", "COM3", None, "TCP:29001"]

        for candidate in attempted_ports:
            try:
                if candidate == "TCP:29001":
                    payload = {
                        "connection_type": "tcp",
                        "host": "127.0.0.1",
                        "port": 29001,
                        "serial_port": None,
                    }
                elif candidate is None:
                    payload = {
                        "connection_type": "serial",
                        "serial_port": None,
                        "host": None,
                        "port": None,
                    }
                else:
                    payload = {
                        "connection_type": "serial",
                        "serial_port": candidate,
                        "host": None,
                        "port": None,
                    }

                resp = await self._request_with_fallback(
                    "POST",
                    "/rusefi/connect",
                    json=payload,
                    timeout=connect_timeout,
                )
                if resp.status_code == 200:
                    self.last_connect_error = ""
                    return True

                detail = ""
                try:
                    body = resp.json()
                    if isinstance(body, dict):
                        detail = str(body.get("detail", body))
                    else:
                        detail = str(body)
                except Exception:
                    detail = resp.text
                self.last_connect_error = f"{candidate or 'auto'} -> HTTP {resp.status_code}: {detail}"

            except Exception as e:
                self._refresh_base_url()
                self.last_connect_error = f"{candidate or 'auto'} -> {type(e).__name__}: {e!r}"
                logger.error(f"Connect failed on {candidate or 'auto'}: {e!r}")

        # Try wakeup endpoint once for COM5/COM6 if all direct attempts failed.
        for wake_port in ("COM5", "COM6"):
            try:
                wake_payload = {
                    "connection_type": "serial",
                    "serial_port": wake_port,
                    "host": None,
                    "port": None,
                }
                await self._request_with_fallback(
                    "POST",
                    "/rusefi/wakeup",
                    json=wake_payload,
                    timeout=connect_timeout,
                )
                resp = await self._request_with_fallback(
                    "POST",
                    "/rusefi/connect",
                    json=wake_payload,
                    timeout=connect_timeout,
                )
                if resp.status_code == 200:
                    self.last_connect_error = ""
                    return True
            except Exception as e:
                logger.error(f"Wake/connect retry failed on {wake_port}: {e!r}")

        if not self.last_connect_error:
            self.last_connect_error = "All connect attempts failed."
        return False

    # ------------------------------------------------------------------ Live Data
    async def get_live_data(self) -> dict:
        """GET /rusefi/live -> LiveDataResponse with rpm, map_kpa, afr, etc."""
        try:
            resp = await self._request_with_fallback("GET", "/rusefi/live")
            return resp.json()
        except Exception:
            self._refresh_base_url()
            return {}

    # ------------------------------------------------------------------ Parameters
    async def get_parameters(self, query: str = "", category: str = "", kind: str = "") -> list:
        """GET /parameters/list -> list of {name, category, menu_order, kind, units, min, max, read_only}"""
        try:
            params = {}
            if query:
                params["query"] = query
            if category:
                params["category"] = category
            if kind:
                params["kind"] = kind
            resp = await self._request_with_fallback("GET", "/parameters/list", params=params)
            data = resp.json()
            # Backend returns a plain list of dicts
            if isinstance(data, list):
                return data
            # Safety: handle if wrapped in {"parameters": [...]}
            if isinstance(data, dict) and "parameters" in data:
                return data["parameters"]
            return []
        except Exception as e:
            self._refresh_base_url()
            logger.error(f"List parameters failed: {e}")
            return []

    async def read_parameter(self, name: str) -> dict:
        """GET /parameters/read/{name} -> {name, value, units, min, max}"""
        try:
            resp = await self._request_with_fallback("GET", f"/parameters/read/{name}")
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                # Not all INI definitions expose the same parameter names.
                return {}
            logger.error(f"Read {name} status={resp.status_code}: {resp.text}")
            return {}
        except Exception as e:
            logger.error(f"Read parameter {name} failed: {e!r}")
            return {}

    async def write_parameter(self, name: str, value: Any) -> bool:
        """POST /parameters/write with {name, value}"""
        try:
            payload = {"name": name, "value": value}
            resp = await self._request_with_fallback("POST", "/parameters/write", json=payload)
            if resp.status_code != 200:
                logger.error(f"Write failed: {resp.text}")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Write parameter {name} failed: {e!r}")
            return False

    async def burn(self) -> bool:
        """POST /parameters/burn"""
        try:
            resp = await self._request_with_fallback("POST", "/parameters/burn", json={})
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Burn failed: {e!r}")
            return False

    # ------------------------------------------------------------------ MSQ Import/Export
    async def import_msq(self, data: bytes) -> dict:
        """POST /parameters/import_msq (multipart file upload)"""
        try:
            resp = await self._request_with_fallback(
                "POST",
                "/parameters/import_msq",
                files={"file": ("tune.msq", data, "application/xml")},
            )
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Import MSQ failed: {e!r}")
            return {}

    async def export_msq(self) -> bytes:
        """POST /parameters/export_msq -> XML bytes"""
        try:
            resp = await self._request_with_fallback("POST", "/parameters/export_msq")
            return resp.content if resp.status_code == 200 else b""
        except Exception as e:
            logger.error(f"Export MSQ failed: {e!r}")
            return b""

    # ------------------------------------------------------------------ Tables
    async def load_table(self, table_name: str) -> dict:
        """POST /tables/load -> {table_name, rows, cols, data, rpm_axis, map_axis, ...}"""
        try:
            resp = await self._request_with_fallback(
                "POST",
                "/tables/load",
                json={"table_name": table_name},
            )
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Load table {table_name} failed: {e!r}")
            return {}

    async def save_table(self, table_name: str, data: list) -> dict:
        """POST /tables/save -> write table back to ECU"""
        try:
            resp = await self._request_with_fallback(
                "POST",
                "/tables/save",
                json={"table_name": table_name, "data": data},
            )
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Save table {table_name} failed: {e!r}")
            return {}

    # ------------------------------------------------------------------ Autotune
    async def autotune_run(self, tool_name: str, **kwargs) -> dict:
        """POST /autotune/run -> start autotune session (streaming NDJSON)"""
        try:
            payload = {"tool_name": tool_name, **kwargs}
            resp = await self._request_with_fallback("POST", "/autotune/run", json=payload)
            return resp.json() if resp.status_code == 200 else {"error": resp.text}
        except Exception as e:
            logger.error(f"Autotune run failed: {e!r}")
            return {"error": str(e)}

    async def autotune_preview(self, tool_name: str, **kwargs) -> dict:
        """POST /autotune/preview"""
        try:
            payload = {"tool_name": tool_name, **kwargs}
            resp = await self._request_with_fallback("POST", "/autotune/preview", json=payload)
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Autotune preview failed: {e!r}")
            return {}

    # ------------------------------------------------------------------ Dyno
    async def dyno_estimate(self, vehicle_mass_kg: int) -> dict:
        """POST /dyno/estimate"""
        try:
            resp = await self._request_with_fallback(
                "POST",
                "/dyno/estimate",
                json={"vehicle_mass_kg": vehicle_mass_kg},
            )
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Dyno estimate failed: {e!r}")
            return {}

    # ------------------------------------------------------------------ Datalog
    async def datalog_start(self, high_speed: bool = False) -> dict:
        try:
            resp = await self._request_with_fallback(
                "POST",
                "/datalog/start",
                json={"profile_id": None, "high_speed": high_speed},
            )
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Datalog start failed: {e!r}")
            return {}

    async def datalog_stop(self) -> dict:
        try:
            resp = await self._request_with_fallback("POST", "/datalog/stop")
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Datalog stop failed: {e!r}")
            return {}

    async def datalog_recent(self) -> list:
        try:
            resp = await self._request_with_fallback("GET", "/datalog/recent")
            data = resp.json()
            return data.get("logs", []) if isinstance(data, dict) else []
        except Exception as e:
            logger.error(f"Datalog recent failed: {e!r}")
            return []

    # ------------------------------------------------------------------ Presets
    async def get_presets(self) -> list:
        try:
            resp = await self._request_with_fallback("GET", "/presets/list")
            if resp.status_code != 200:
                return []
            payload = resp.json()
            return payload.get("presets", []) if isinstance(payload, dict) else []
        except Exception as e:
            logger.error(f"Get presets failed: {e!r}")
            return []

    async def apply_preset(self, preset_name: str, burn_after: bool = False, overrides: Optional[Dict[str, Any]] = None) -> dict:
        try:
            payload: Dict[str, Any] = {
                "preset_name": preset_name,
                "burn_after": bool(burn_after),
            }
            if overrides:
                payload["overrides"] = overrides
            resp = await self._request_with_fallback("POST", "/presets/apply", json=payload)
            return resp.json() if resp.status_code == 200 else {"status": "error", "detail": resp.text}
        except Exception as e:
            logger.error(f"Apply preset failed: {e!r}")
            return {"status": "error", "detail": str(e)}

    async def save_custom_preset(
        self,
        name: str,
        values: Optional[Dict[str, Any]] = None,
        notes: Optional[List[str]] = None,
        base_preset: Optional[str] = None,
    ) -> dict:
        try:
            payload: Dict[str, Any] = {"name": name}
            if values is not None:
                payload["values"] = values
            if notes is not None:
                payload["notes"] = notes
            if base_preset:
                payload["base_preset"] = base_preset
            resp = await self._request_with_fallback("POST", "/presets/save", json=payload)
            return resp.json() if resp.status_code == 200 else {"status": "error", "detail": resp.text}
        except Exception as e:
            logger.error(f"Save preset failed: {e!r}")
            return {"status": "error", "detail": str(e)}

    # ------------------------------------------------------------------ Cleanup
    async def close(self):
        await self.client.aclose()
