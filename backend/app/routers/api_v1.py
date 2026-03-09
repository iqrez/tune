from typing import List, Dict, Optional, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import uuid
import json
import struct
import os
import tempfile
import logging
import math
import time
import xml.etree.ElementTree as ET
from datetime import datetime
import copy

from ..schemas import (
    AnalysisRequest, AnalysisResponse, VehicleProfile, CalibrationSnapshot, 
    DatalogSummary, ApplyRequest, ApplyResponse, SnapshotListItem, 
    RollbackRequest, SimulateLiveRequest, SimulateLiveResponse, 
    PowerRampRequest, PowerRampResponse, ConnectRequest, LiveDataResponse, 
    TableRequest, TableWriteRequest, Recommendation,
    AnalysisOptions, DatalogCell, DatalogGlobalStats,
    TablesLoadRequest, TablesLoadResponse, TablesSaveRequest, TablesSaveResponse,
    TablesGuardrailWarning, TablesExportMsqRequest, TablesImportMsqResponse,
    DatalogStartRequest, DatalogStopRequest, DatalogLoadResponse, DatalogAnalyzeRequest
)
from ..db.database import get_db, DBVehicleProfile, DBSnapshot, DB_PATH
from ..core.math_engine import DeterministicEngineModel
from ..core.guardrails import GuardrailEngine
from ..core.live_simulator import LiveSimulator
from ..utils.security import sign_payload, verify_signature
from ..parsers.msq_parser import MsqParser

# Authority imports from backend/core/
from core.rusefi_connector import RusefiTunerClient
from core.datalogger import DatalogRecorder, DatalogViewer
from core.autotune import AutoTuneEngine
from core.dyno_estimator import DynoEstimator
from core.project_manager import ProjectManager
from core.parameters import ParameterRegistry
from core.presets import PresetManager
from ..core.agent import TuningAgent
from ..core.model_adapter import LocalModelAdapter


# --- Dependencies ---


# Setup logger
logger = logging.getLogger("APIV1")

router = APIRouter(prefix="/api/v1")

# --- Singletons ---
_ecu_client = RusefiTunerClient()
_adapter = LocalModelAdapter()
_agent = TuningAgent(_adapter, _ecu_client)
_datalog_recorder = DatalogRecorder(_ecu_client, DB_PATH)
_datalog_viewer = DatalogViewer(DB_PATH)
_autotune_engine = AutoTuneEngine(_ecu_client, DB_PATH)
_dyno_estimator = DynoEstimator()
_parameters = ParameterRegistry(_ecu_client)
_presets = PresetManager(
    _parameters,
    storage_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "state", "presets"),
)
_project_manager = ProjectManager(
    base_dir=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    db_path=DB_PATH,
)
DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dashboards")
os.makedirs(DASHBOARD_DIR, exist_ok=True)
TABLE_LIMITS: Dict[str, Tuple[float, float]] = {
    "veTable": (0.0, 999.0),
    "veTable1": (0.0, 999.0),
    "ignitionTable": (-20.0, 90.0),
    "ignitionTable1": (-20.0, 90.0),
    "boostTableOpenLoop": (0.0, 300.0),
    "boostTableClosedLoop": (0.0, 300.0),
    "boostTable1": (0.0, 300.0),
    "lambdaTable": (0.0, 2.0),
    "lambdaTable1": (0.0, 2.0),
}



# (Removed duplicate rusefi_live definition here, authoritative one is later in file)
TABLE_RISK_ZONES: Dict[str, Tuple[float, float]] = {
    "veTable1": (210.0, 235.0),
    "ignitionTable1": (45.0, 55.0),
    "boostTable1": (220.0, 270.0),
    "lambdaTable1": (0.75, 1.25),
}


def _infer_dims(cell_count: int) -> Tuple[int, int]:
    if cell_count <= 0:
        return 0, 0
    root = int(math.sqrt(cell_count))
    if root * root == cell_count:
        return root, root

    best_r = 1
    best_c = cell_count
    best_gap = cell_count
    for r in range(1, root + 1):
        if cell_count % r == 0:
            c = cell_count // r
            gap = abs(c - r)
            if gap < best_gap:
                best_gap = gap
                best_r, best_c = r, c
    return best_r, best_c


def _default_axis(table_name: str, count: int, axis: str) -> List[float]:
    if count <= 0:
        return []

    if axis == "rpm":
        if count == 16:
            return [500 + i * 500 for i in range(count)]
        step = max(150, int(7500 / max(1, count - 1)))
        return [500 + i * step for i in range(count)]

    if axis == "map_kpa":
        if count == 16:
            return [30 + i * 15 for i in range(count)]
        step = max(5, int(240 / max(1, count - 1)))
        return [30 + i * step for i in range(count)]

    return [float(i) for i in range(count)]


def _decode_raw_value(table_name: str, raw: float, meta: dict) -> float:
    scale = meta.get("scale", 1.0)
    offset = meta.get("translate", 0.0)  # Added translation support if needed
    return round((raw * scale) + offset, 3)


def _encode_raw_value(table_name: str, value: float, meta: dict) -> int:
    scale = meta.get("scale", 1.0)
    offset = meta.get("translate", 0.0)
    encoded = int(round((value - offset) / scale))
    
    # Handle range based on type
    t = meta.get("type", "uint8")
    if t == "uint8":
        return max(0, min(255, encoded))
    elif t == "int8":
        return max(-128, min(127, encoded))
    elif t == "uint16":
        return max(0, min(65535, encoded))
    elif t == "int16":
        return max(-32768, min(32767, encoded))
    return int(encoded)


def _reshape_flat(flat: List[float], rows: int, cols: int) -> List[List[float]]:
    data: List[List[float]] = []
    for r in range(rows):
        start = r * cols
        data.append(flat[start:start + cols])
    return data


def _flatten_matrix(data: List[List[float]]) -> List[float]:
    return [v for row in data for v in row]


def _table_from_snapshot(table_name: str, snap: CalibrationSnapshot) -> List[List[float]]:
    if table_name == "veTable1":
        return snap.fuel_table
    if table_name == "ignitionTable1":
        return snap.ignition_table
    if table_name == "boostTable1":
        return snap.boost_table
    if table_name == "lambdaTable1":
        rows = len(snap.fuel_table)
        cols = len(snap.fuel_table[0]) if rows else 16
        return [[1.0 for _ in range(cols)] for _ in range(rows)]
    return []


def _validate_matrix(data: List[List[float]]) -> Tuple[int, int]:
    if not data:
        raise HTTPException(status_code=400, detail="Table data is empty")
    cols = len(data[0])
    if cols == 0:
        raise HTTPException(status_code=400, detail="Table data has no columns")
    for row in data:
        if len(row) != cols:
            raise HTTPException(status_code=400, detail="Table rows must have equal length")
    return len(data), cols


def _datalog_guardrail_scan(summary: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    max_duty = float(summary.get("max_injector_duty", 0.0) or 0.0)
    knock_events = int(summary.get("knock_events", 0) or 0)
    max_rpm = float(summary.get("max_rpm", 0.0) or 0.0)
    avg_afr = float(summary.get("avg_afr", 0.0) or 0.0)

    if max_duty > 85.0:
        warnings.append("Injector duty exceeded 85%: avoid fuel additions until injector headroom improves.")
    if knock_events > 0:
        warnings.append("Knock events detected: do not add ignition in affected high-load regions.")
    if max_rpm > 9000:
        warnings.append("RPM exceeded 9000: verify rev-limit and valvetrain safety margins.")
    if avg_afr > 15.5:
        warnings.append("Average AFR appears lean for sustained operation: review fueling before additional load.")
    if not warnings:
        warnings.append("No immediate guardrail violations detected from log summary.")
    return warnings


def _safe_dashboard_name(name: str) -> str:
    clean = "".join(ch for ch in (name or "dashboard") if ch.isalnum() or ch in ("_", "-", "."))
    clean = clean.replace(".json", "")
    return clean or "dashboard"


def _dashboard_path(name: str) -> str:
    return os.path.join(DASHBOARD_DIR, f"{_safe_dashboard_name(name)}.json")


def _parse_dash_bytes(payload: bytes) -> Dict[str, Any]:
    try:
        root = ET.fromstring(payload)
        tabs: List[Dict[str, Any]] = []
        for i, tab in enumerate(root.findall(".//tab")):
            gauges: List[Dict[str, Any]] = []
            for j, g in enumerate(tab.findall(".//gauge")):
                gauges.append(
                    {
                        "id": f"imp_{i}_{j}",
                        "type": g.attrib.get("type", "Digital"),
                        "channel": g.attrib.get("channel", "RPM"),
                        "x": float(g.attrib.get("x", "20")),
                        "y": float(g.attrib.get("y", "20")),
                        "w": float(g.attrib.get("w", "180")),
                        "h": float(g.attrib.get("h", "140")),
                        "rot": float(g.attrib.get("rot", "0")),
                        "min": float(g.attrib.get("min", "0")),
                        "max": float(g.attrib.get("max", "100")),
                        "unit": g.attrib.get("unit", ""),
                        "alarm": float(g.attrib.get("alarm", "0")),
                    }
                )
            tabs.append({"name": tab.attrib.get("name", f"Tab {i+1}"), "gauges": gauges})
        return {
            "name": root.attrib.get("name", "Imported Dash"),
            "background": {"color": "#0f172a", "image": ""},
            "tabs": tabs or [{"name": "Engine Vitals", "gauges": []}],
            "active_tab": 0,
            "values": {},
            "connected": False,
            "selected_gauge_id": None,
        }
    except Exception:
        return {}


def _autotune_default_profile() -> VehicleProfile:
    return VehicleProfile(
        vehicle_id="autotune-default",
        make="Unknown",
        model="Unknown",
        engine_family="Unknown",
        displacement_l=2.0,
        cylinders=4,
        aspiration="na",
        compression_ratio=10.0,
        fuel_type="gas93",
        injector_cc_min=550.0,
        fuel_pressure_psi=43.5,
        max_safe_rpm=8000,
        usage="street",
    )


def _apply_guardrails_to_autotune_changes(
    tool_name: str,
    table_name: str,
    base_table: List[List[float]],
    rpm_axis: List[float],
    map_axis: List[float],
    changes: List[Dict[str, Any]],
    samples: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not changes:
        return [], []
    if tool_name not in ("ve", "ve analyze", "ve_analyze", "ignition", "ignition tune", "ignition_autotune"):
        return changes, []

    profile = _autotune_default_profile()
    fuel_table = copy.deepcopy(base_table) if table_name == "veTable1" else [[0.0 for _ in row] for row in base_table]
    ign_table = copy.deepcopy(base_table) if table_name == "ignitionTable1" else [[0.0 for _ in row] for row in base_table]
    boost_table = [[0.0 for _ in row] for row in base_table]

    cells: List[DatalogCell] = []
    for ch in changes:
        r = int(ch.get("row", -1))
        c = int(ch.get("col", -1))
        if r < 0 or c < 0:
            continue
        cells.append(
            DatalogCell(
                rpm_index=c,
                map_index=r,
                occupied_pct=float(max(3.1, ch.get("samples", 5))),
                target_afr=float(ch.get("target_afr", 12.5)),
                measured_afr=float(ch.get("measured_afr", 12.5)),
                afr_error_pct=float(ch.get("delta_pct", 0.0)),
                knock_count=int(ch.get("knock_count", 0)),
                iat_c=35.0,
                ect_c=90.0,
                lambda_corrections=0.0,
            )
        )

    max_duty = 0.0
    for row in samples or []:
        try:
            max_duty = max(max_duty, float(row.get("InjectorDuty_pct", 0.0) or 0.0))
        except Exception:
            continue
    gstats = DatalogGlobalStats(
        max_knock_cell={"rpm_index": 0, "map_index": 0},
        avg_iat_c=35.0,
        max_injector_duty_pct=max_duty,
    )
    dsum = DatalogSummary(session_id=f"autotune-{int(time.time())}", cells=cells, global_stats=gstats)
    cal = CalibrationSnapshot(
        axes={"rpm": rpm_axis, "map_kpa": map_axis},
        fuel_table=fuel_table,
        ignition_table=ign_table,
        boost_table=boost_table,
        metadata={"source": "autotune_preview"},
    )
    opts = AnalysisOptions(
        mode="advisory",
        aggressiveness="balanced",
        max_fuel_delta_pct=20.0,
        max_ignition_delta_deg=1.0,
    )
    req = AnalysisRequest(vehicle_profile=profile, calibration=cal, datalog_summary=dsum, options=opts)
    guard = GuardrailEngine(req)

    recs: List[Recommendation] = []
    for ch in changes:
        r = int(ch.get("row", -1))
        c = int(ch.get("col", -1))
        if r < 0 or c < 0:
            continue
        recs.append(
            Recommendation(
                rpm_index=c,
                map_index=r,
                delta_fuel_pct=float(ch.get("delta_pct", 0.0)) if table_name == "veTable1" else 0.0,
                delta_ign_deg=float(ch.get("delta_deg", ch.get("delta", 0.0))) if table_name == "ignitionTable1" else 0.0,
                confidence=0.8,
                rationale="AutoTune proposal",
            )
        )

    validated, warnings = guard.run_all_guardrails(recs)
    accepted = {(int(v.map_index), int(v.rpm_index)): v for v in validated}
    out: List[Dict[str, Any]] = []
    for ch in changes:
        key = (int(ch.get("row", -1)), int(ch.get("col", -1)))
        if key not in accepted:
            ch2 = dict(ch)
            ch2["vetoed"] = True
            ch2["veto_reason"] = "Guardrail rejected proposal"
            out.append(ch2)
            continue
        v = accepted[key]
        ch2 = dict(ch)
        if table_name == "veTable1":
            ch2["delta_pct"] = float(v.delta_fuel_pct)
            before = float(ch2.get("before", 0.0))
            ch2["after"] = round(before * (1.0 + (ch2["delta_pct"] / 100.0)), 4)
            ch2["delta"] = round(ch2["after"] - before, 4)
        elif table_name == "ignitionTable1":
            ch2["delta_deg"] = float(v.delta_ign_deg)
            before = float(ch2.get("before", 0.0))
            ch2["after"] = round(before + ch2["delta_deg"], 4)
            ch2["delta"] = round(ch2["after"] - before, 4)
        out.append(ch2)
    return out, warnings

def get_rusefi_client() -> RusefiTunerClient:
    return _ecu_client

@router.post("/agent/chat")
async def agent_chat(request: Dict[str, Any]):
    user_msg = request.get("message", "")
    state = request.get("state", {})

    def stream():
        try:
            for step_data in _agent.stream_run(user_msg, state):
                yield json.dumps(step_data) + "\n"
        except Exception as e:
            logger.error(f"Agent Stream Error: {e}")
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")

@router.post("/profiles", response_model=VehicleProfile)
def create_profile(profile: VehicleProfile, db: Session = Depends(get_db)):
    try:
        existing = db.query(DBVehicleProfile).filter(DBVehicleProfile.id == profile.vehicle_id).first()
        if existing:
            existing.name = f"{profile.make} {profile.model}"
            existing.profile_data_json = profile.model_dump_json()
        else:
            new_prof = DBVehicleProfile(
                id=profile.vehicle_id,
                name=f"{profile.make} {profile.model}",
                profile_data_json=profile.model_dump_json()
            )
            db.add(new_prof)
        db.commit()
        return profile
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")

@router.get("/profiles/{profile_id}", response_model=VehicleProfile)
def get_profile(profile_id: str, db: Session = Depends(get_db)):
    prof = db.query(DBVehicleProfile).filter(DBVehicleProfile.id == profile_id).first()
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    return VehicleProfile.model_validate_json(prof.profile_data_json)


@router.post("/projects/create")
def projects_create(request: Dict[str, Any]):
    name = str(request.get("name", "")).strip()
    profile_json = request.get("profile_json") or {}
    import_msq = request.get("import_msq_path")
    if not name:
        raise HTTPException(status_code=400, detail="Project name is required")
    try:
        return _project_manager.create_project(name=name, profile_json=profile_json, import_msq_path=import_msq)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Project create failed: {str(e)}")


@router.get("/projects/list")
def projects_list():
    try:
        payload = _project_manager.list_projects()
        current = payload.get("current_project") or "untitled"
        payload["history"] = _project_manager.history(current)
        payload["file_tree"] = _project_manager.file_tree(current)
        return payload
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Project list failed: {str(e)}")


@router.post("/projects/switch")
def projects_switch(request: Dict[str, Any]):
    name = str(request.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name is required")
    try:
        out = _project_manager.switch_project(name)
        out["history"] = _project_manager.history(out["name"])
        out["file_tree"] = _project_manager.file_tree(out["name"])
        return out
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Project switch failed: {str(e)}")


@router.post("/projects/compare")
def projects_compare(request: Dict[str, Any]):
    version1 = int(request.get("version1", 0) or 0)
    version2 = int(request.get("version2", 0) or 0)
    table_name = str(request.get("table_name", "veTable1"))
    project = str(request.get("project_name") or _project_manager.get_current_project_name() or "untitled")
    if version1 <= 0 or version2 <= 0:
        raise HTTPException(status_code=400, detail="version1/version2 must be positive")
    try:
        return _project_manager.compare_versions(project, version1, version2, table_name=table_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Version not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Project compare failed: {str(e)}")


@router.post("/projects/rollback")
def projects_rollback(request: Dict[str, Any]):
    version = int(request.get("version", 0) or 0)
    table_name = str(request.get("table_name", "veTable1"))
    project = str(request.get("project_name") or _project_manager.get_current_project_name() or "untitled")
    if version <= 0:
        raise HTTPException(status_code=400, detail="version must be positive")
    try:
        return _project_manager.rollback(project, version, table_name=table_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Version not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Project rollback failed: {str(e)}")


@router.get("/projects/export/{name}")
def projects_export(name: str):
    try:
        zip_path = _project_manager.export_project_zip(name)
        with open(zip_path, "rb") as f:
            payload = f.read()
        return Response(
            content=payload,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={os.path.basename(zip_path)}"},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Project export failed: {str(e)}")


@router.post("/projects/import")
def projects_import(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp.write(file.file.read())
            tmp_path = tmp.name
        out = _project_manager.import_project_zip(tmp_path)
        os.unlink(tmp_path)
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Project import failed: {str(e)}")

@router.post("/generate_base_tune", response_model=CalibrationSnapshot)
def generate_base_tune(profile: VehicleProfile):
    try:
        engine = DeterministicEngineModel(profile)
        # 16x16 standard
        rpm_axis = [500 + i*500 for i in range(16)]
        map_axis = [30 + i*15 for i in range(16)]
        
        fuel_table = []
        ign_table = []
        
        for r in rpm_axis:
            fuel_row = []
            ign_row = []
            for m in map_axis:
                ve_guess = 0.75
                iat_guess_c = 30.0
                target_afr = engine.generate_base_afr_target(float(r), float(m))
                pw_ms = engine.estimate_injector_scaling_ms(ve_guess, float(m), iat_guess_c, target_afr)
                fuel_row.append(round(pw_ms, 2))
                ign_deg = engine.generate_base_ignition_timing(float(r), float(m))
                ign_row.append(round(ign_deg, 1))
            fuel_row_final = fuel_row if len(fuel_row) == 16 else (fuel_row + [0]*16)[:16]
            ign_row_final = ign_row if len(ign_row) == 16 else (ign_row + [0]*16)[:16]
            fuel_table.append(fuel_row_final)
            ign_table.append(ign_row_final)

        return CalibrationSnapshot(
            axes={"rpm": rpm_axis, "map_kpa": map_axis},
            fuel_table=fuel_table,
            ignition_table=ign_table,
            boost_table=[[0]*16 for _ in range(16)],
            metadata={"source": "math_engine_base", "id": str(uuid.uuid4())}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tune Generation Error: {str(e)}")

@router.post("/analyze", response_model=AnalysisResponse)
def analyze(req: AnalysisRequest, db: Session = Depends(get_db)):
    session_id = str(uuid.uuid4())
    try:
        from ..core.rag_knowledge import RagKnowledgeBase
        rag = RagKnowledgeBase()
        context = rag.retrieve_context(req.vehicle_profile.make, req.vehicle_profile.engine_family, req.vehicle_profile.fuel_type)
        raw_recommendations = _adapter.analyze_datalog(req, context)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raw_recommendations = []
    
    if not raw_recommendations:
        engine = DeterministicEngineModel(req.vehicle_profile)
        for cell in req.datalog_summary.cells:
            target_afr = cell.target_afr or engine.generate_base_afr_target(
                req.calibration.axes["rpm"][cell.rpm_index],
                req.calibration.axes["map_kpa"][cell.map_index]
            )
            if cell.measured_afr:
                error_pct = ((cell.measured_afr - target_afr) / target_afr) * 100
                raw_recommendations.append(Recommendation(
                    rpm_index=cell.rpm_index, map_index=cell.map_index,
                    delta_fuel_pct=error_pct * 0.5, delta_ign_deg=0.0,
                    confidence=0.8, rationale=f"Auto-correction: {cell.measured_afr} vs {target_afr}"
                ))

    guard = GuardrailEngine(req)
    validated_recs, warnings = guard.run_all_guardrails(raw_recommendations)
    
    response_data = {
        "session_id": session_id,
        "recommendations": [r.model_dump() for r in validated_recs],
        "summary_text": f"Found {len(validated_recs)} valid corrections.",
        "warnings": warnings,
        "signature": ""
    }
    response_data["signature"] = sign_payload(response_data)
    return AnalysisResponse(**response_data)

@router.post("/apply", response_model=ApplyResponse)
def apply_changes(req: ApplyRequest, db: Session = Depends(get_db)):
    payload_to_verify = {
        "session_id": req.session_id,
        "approved_changes": [r.model_dump() for r in req.approved_changes],
        "user_id": req.user_id
    }
    if not verify_signature(payload_to_verify, req.signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    snapshot_id = str(uuid.uuid4())
    db_snap = DBSnapshot(
        id=snapshot_id, session_id=req.session_id,
        snapshot_json=json.dumps([r.model_dump() for r in req.approved_changes]),
        signature=req.signature
    )
    db.add(db_snap)
    db.commit()
    return ApplyResponse(success=True, snapshot_id=snapshot_id, message="Snapshot saved.")

@router.get("/snapshots", response_model=List[SnapshotListItem])
def list_snapshots(db: Session = Depends(get_db)):
    snaps = db.query(DBSnapshot).order_by(DBSnapshot.created_at.desc()).all()
    return [SnapshotListItem(id=s.id, session_id=s.session_id, created_at=s.created_at, signature=s.signature) for s in snaps]

@router.post("/rollback", response_model=ApplyResponse)
def rollback(req: RollbackRequest, db: Session = Depends(get_db)):
    snap = db.query(DBSnapshot).filter(DBSnapshot.id == req.snapshot_id).first()
    if not snap: raise HTTPException(status_code=404, detail="Snapshot not found")
    return ApplyResponse(success=True, snapshot_id=snap.id, message="Rollback requested.")

@router.post("/simulate_live", response_model=SimulateLiveResponse)
def simulate_live(req: SimulateLiveRequest):
    simulator = LiveSimulator(req.vehicle_profile, req.calibration)
    result = simulator.run_simulation(num_cycles=req.num_cycles)
    return SimulateLiveResponse(**result)

@router.post("/power_ramp", response_model=PowerRampResponse)
def power_ramp(req: PowerRampRequest):
    from ..core.power_ramp import PowerRampEngine
    engine = PowerRampEngine(req.vehicle_profile, req.calibration, req.target_boost_psi)
    result = engine.run_ramp(samples_per_stage=req.samples_per_stage)
    return PowerRampResponse(**result)

@router.get("/rusefi/detect_ports")
def rusefi_detect_ports(client: RusefiTunerClient = Depends(get_rusefi_client)):
    return {
        "ports": client.list_all_ports_with_test(),
        "detection": client.get_last_detection(),
    }

@router.post("/rusefi/connect")
def rusefi_connect(req: ConnectRequest, client: RusefiTunerClient = Depends(get_rusefi_client)):
    # The new connect() in rusefi_connector already calls auto_detect which calls force_ecu_wakeup
    success = client.connect(tcp_host=req.host, tcp_port=req.port) if req.connection_type == "tcp" else client.connect(serial_port=req.serial_port)
    if not success: 
        raise HTTPException(status_code=503, detail={"message": "ECU Connection failed. Try 'Force ECU Wakeup' or 'Wake Binary Port'.", "detection": client.get_last_detection()})
    return {
        "status": "connected",
        "type": client.connection_type,
        "port": client.port_name,
        "limited_mode": bool(getattr(client, "limited_mode", False)),
        "console_mode": bool(getattr(client, "console_mode", False)),
        "signature_mode": bool(getattr(client, "signature_mode", False)),
        "detection": client.get_last_detection(),
    }

@router.post("/rusefi/wakeup")
def rusefi_wakeup(req: ConnectRequest, client: RusefiTunerClient = Depends(get_rusefi_client)):
    port = req.serial_port or client.auto_detect_serial_port()
    if not port:
        raise HTTPException(status_code=404, detail="No COM port found to wake up.")
    
    success = client.force_ecu_wakeup(port)
    if success:
        return {"status": "success", "message": "ECU Woke up! Try connecting now."}
    else:
        raise HTTPException(status_code=503, detail="Wakeup failed. Ensure USB cable is data-capable.")


@router.post("/rusefi/wake_binary")
def rusefi_wake_binary(req: ConnectRequest, client: RusefiTunerClient = Depends(get_rusefi_client)):
    if client.try_wake_binary():
        return {
            "status": "success",
            "console_port": client.get_last_detection().get("console_port"),
            "binary_port": client.port_name,
            "detection": client.get_last_detection(),
        }
    port = req.serial_port or client.get_last_detection().get("console_port") or client.auto_detect_serial_port()
    if not port:
        raise HTTPException(status_code=404, detail="No console port found for wake_binary.")
    binary = client.wake_binary_port(port)
    if binary:
        return {"status": "success", "console_port": port, "binary_port": binary, "detection": client.get_last_detection()}
    raise HTTPException(status_code=503, detail={"message": "Binary port not discovered after wake attempt.", "detection": client.get_last_detection()})

_LIVE_DISCONNECTED = LiveDataResponse(
    connected=False, rpm=0, map_kpa=0, afr=0, iat=0, ect=0, advance=0,
    knock_count=0, injector_duty=0, voltage=0, tps=0, lambda_val=0,
    console_mode=False, signature_mode=False, uptime_s=None, port=None, connection_type=None,
)

@router.get("/rusefi/live", response_model=LiveDataResponse)
def rusefi_live(client: RusefiTunerClient = Depends(get_rusefi_client)):
    if not client.is_connected():
        return _LIVE_DISCONNECTED
    try:
        data = client.get_live_data()
    except Exception as e:
        logger.warning(f"Live data read failed (stale connection?): {e}")
        client.connected = False
        return _LIVE_DISCONNECTED
    if not data or not data.get("connected"):
        return _LIVE_DISCONNECTED
    return LiveDataResponse(
        connected=True,
        rpm=data.get("rpm", 0),
        map_kpa=data.get("map", 0),
        afr=data.get("afr", 0),
        lambda_val=data.get("lambda", 0),
        iat=data.get("iat", 0),
        ect=data.get("clt", 0),
        advance=data.get("advance", 0),
        knock_count=data.get("knock", 0),
        injector_duty=data.get("duty", 0),
        voltage=data.get("vbatt", 0),
        tps=data.get("tps", 0),
        console_mode=bool(getattr(client, "console_mode", False)),
        signature_mode=bool(getattr(client, "signature_mode", False)),
        uptime_s=data.get("uptime"),
        port=client.port_name,
        connection_type=client.connection_type,
    )


@router.post("/datalog/start")
def datalog_start(req: DatalogStartRequest):
    return _datalog_recorder.start(profile_id=req.profile_id, high_speed=req.high_speed)


@router.post("/datalog/pause")
def datalog_pause():
    return _datalog_recorder.pause()


@router.post("/datalog/resume")
def datalog_resume():
    return _datalog_recorder.resume()


@router.get("/datalog/status")
def datalog_status():
    return _datalog_recorder.get_status()


@router.post("/datalog/stop")
def datalog_stop(req: DatalogStopRequest):
    return _datalog_recorder.stop(filename=req.filename)


@router.get("/datalog/recent")
def datalog_recent(limit: int = 25):
    return {"logs": _datalog_viewer.list_recent_logs(limit=limit)}


@router.get("/datalog/load/{filename}", response_model=DatalogLoadResponse)
def datalog_load(filename: str):
    try:
        data = _datalog_viewer.load_log(filename)
        return DatalogLoadResponse(
            filename=data.get("filename", filename),
            rows=data.get("rows", []),
            channels=data.get("channels", []),
            samples=int(data.get("samples", 0)),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Log file not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load datalog: {str(e)}")


@router.post("/datalog/import")
def datalog_import(file: UploadFile = File(...), profile_id: str = "imported"):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or "upload.msl")[1] or ".msl") as tmp:
            tmp.write(file.file.read())
            tmp_path = tmp.name
        filename = _datalog_viewer.import_log_file(tmp_path, profile_id=profile_id)
        os.unlink(tmp_path)
        return {"status": "imported", "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {str(e)}")


@router.get("/datalog/export/{filename}")
def datalog_export(filename: str, fmt: str = "csv"):
    try:
        payload = _datalog_viewer.export_log(filename, fmt=fmt)
        media = "text/csv" if fmt.lower() in ("csv", "msl") else "application/octet-stream"
        ext = "msl" if fmt.lower() == "msl" else "csv"
        return Response(
            content=payload,
            media_type=media,
            headers={"Content-Disposition": f"attachment; filename={os.path.splitext(filename)[0]}.{ext}"},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Export failed: {str(e)}")


@router.post("/datalog/analyze")
def datalog_analyze(req: DatalogAnalyzeRequest):
    summary = req.log_data_summary or {}
    warnings = _datalog_guardrail_scan(summary)
    prompt = {
        "summary": summary,
        "guardrail_warnings": warnings,
        "instruction": "Analyze this datalog summary and return concise tuning recommendations with safety-first tone.",
    }

    llm_result = _adapter.chat([{"role": "user", "content": json.dumps(prompt)}])
    return {
        "status": "ok",
        "guardrail_warnings": warnings,
        "llm_analysis": llm_result,
    }


@router.post("/autotune/preview")
def autotune_preview(request: Dict[str, Any]):
    tool_name = str(request.get("tool_name", "ve"))
    params = request.get("params_json") or {}
    if not isinstance(params, dict):
        raise HTTPException(status_code=400, detail="params_json must be an object")

    result = _autotune_engine.run(tool_name, params, dry_run=True)
    table_name = result.get("table_name", params.get("table_name", "veTable1"))
    base_table = result.get("base_table") or params.get("base_table") or [[100.0 for _ in range(16)] for _ in range(16)]
    rpm_axis = result.get("rpm_axis") or params.get("rpm_axis") or [500 + i * 500 for i in range(16)]
    map_axis = result.get("map_axis") or params.get("map_axis") or [30 + i * 15 for i in range(16)]
    guarded_changes, guard_warnings = _apply_guardrails_to_autotune_changes(
        tool_name=tool_name.strip().lower(),
        table_name=table_name,
        base_table=base_table,
        rpm_axis=rpm_axis,
        map_axis=map_axis,
        changes=result.get("changes", []),
        samples=params.get("samples", []),
    )
    result["changes"] = guarded_changes
    result["guardrail_warnings"] = guard_warnings
    return result


@router.post("/autotune/run")
def autotune_run(request: Dict[str, Any]):
    tool_name = str(request.get("tool_name", "ve"))
    params = request.get("params_json") or {}
    if not isinstance(params, dict):
        raise HTTPException(status_code=400, detail="params_json must be an object")

    def stream():
        started = {
            "type": "progress",
            "message": f"Starting {tool_name} auto-tune",
            "pct": 5,
            "timestamp": datetime.utcnow().isoformat(),
        }
        yield json.dumps(started) + "\n"

        result = _autotune_engine.run(tool_name, params, dry_run=bool(params.get("dry_run", True)))
        for idx, line in enumerate(result.get("progress", [])):
            yield json.dumps(
                {
                    "type": "progress",
                    "message": line,
                    "pct": min(95, 10 + idx * 5),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ) + "\n"

        table_name = result.get("table_name", params.get("table_name", "veTable1"))
        base_table = result.get("base_table") or params.get("base_table") or [[100.0 for _ in range(16)] for _ in range(16)]
        rpm_axis = result.get("rpm_axis") or params.get("rpm_axis") or [500 + i * 500 for i in range(16)]
        map_axis = result.get("map_axis") or params.get("map_axis") or [30 + i * 15 for i in range(16)]
        guarded_changes, guard_warnings = _apply_guardrails_to_autotune_changes(
            tool_name=tool_name.strip().lower(),
            table_name=table_name,
            base_table=base_table,
            rpm_axis=rpm_axis,
            map_axis=map_axis,
            changes=result.get("changes", []),
            samples=params.get("samples", []),
        )
        result["changes"] = guarded_changes
        result["guardrail_warnings"] = guard_warnings

        done = {
            "type": "result",
            "pct": 100,
            "timestamp": datetime.utcnow().isoformat(),
            "result": result,
        }
        yield json.dumps(done) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.post("/autotune/apply")
def autotune_apply(request: Dict[str, Any], client: RusefiTunerClient = Depends(get_rusefi_client)):
    table_name = str(request.get("table_name", "veTable1"))
    changes = request.get("changes_json") or []
    base_table = request.get("base_table") or []
    confirm_ignition = bool(request.get("confirm_ignition", False))

    if not isinstance(changes, list):
        raise HTTPException(status_code=400, detail="changes_json must be a list")
    if not isinstance(base_table, list) or not base_table:
        raise HTTPException(status_code=400, detail="base_table is required")

    if table_name == "ignitionTable1" and not confirm_ignition:
        return {"status": "warning", "message": "Ignition apply requires confirm_ignition=true", "applied": 0}

    rows = len(base_table)
    cols = len(base_table[0]) if rows else 0
    table = [[float(v) for v in row] for row in base_table]

    for ch in changes:
        if ch.get("vetoed"):
            continue
        r = int(ch.get("row", -1))
        c = int(ch.get("col", -1))
        if r < 0 or c < 0 or r >= rows or c >= cols:
            continue
        table[r][c] = float(ch.get("after", table[r][c]))

    min_allowed, max_allowed = TABLE_LIMITS.get(table_name, (0.0, 255.0))
    out_of_range = sum(1 for row in table for v in row if float(v) < min_allowed or float(v) > max_allowed)
    if out_of_range > 0:
        raise HTTPException(status_code=400, detail=f"{out_of_range} cells exceed safe range for {table_name}")

    if client.is_connected() and table_name in client.TABLES:
        payload = bytes([_encode_raw_value(table_name, v) for v in _flatten_matrix(table)])
        client.set_allow_writes(True)
        try:
            if not client.write_table(table_name, payload):
                raise HTTPException(status_code=500, detail="ECU rejected auto-tune write")
        finally:
            client.set_allow_writes(False)
        return {"status": "success", "applied": len(changes), "table_name": table_name, "ecu_written": True}

    return {"status": "success", "applied": len(changes), "table_name": table_name, "ecu_written": False}


@router.post("/dyno/estimate")
def dyno_estimate(request: Dict[str, Any]):
    log_rows = request.get("log_data_json") or []
    params = request.get("params_json") or {}
    mode = str(request.get("mode", "ramp"))
    if not isinstance(log_rows, list):
        raise HTTPException(status_code=400, detail="log_data_json must be a list")
    if not isinstance(params, dict):
        raise HTTPException(status_code=400, detail="params_json must be an object")
    result = _dyno_estimator.estimate(log_rows, params=params, mode=mode)
    return result


@router.post("/dyno/run")
def dyno_run(request: Dict[str, Any], client: RusefiTunerClient = Depends(get_rusefi_client)):
    mode = str(request.get("mode", "ramp")).lower()
    params = request.get("params_json") or {}
    if not isinstance(params, dict):
        raise HTTPException(status_code=400, detail="params_json must be an object")

    safe_check_passed = bool(params.get("safe_check_passed", False))
    if not safe_check_passed:
        return StreamingResponse(
            iter([json.dumps({"type": "error", "message": "Safety check required before dyno run"}) + "\n"]),
            media_type="application/x-ndjson",
        )

    def stream():
        yield json.dumps({"type": "progress", "message": "Dyno run started", "pct": 3, "timestamp": datetime.utcnow().isoformat()}) + "\n"
        partial_rows: List[Dict[str, Any]] = []
        step_count = 0
        for ev in _dyno_estimator.stream_ramp(client, mode=mode, params=params):
            step_count += 1
            latest = ev.get("latest", {})
            partial_rows.append(
                {
                    "timestamp": time.time(),
                    "RPM": latest.get("rpm", 0),
                    "AFR": latest.get("afr", 0),
                    "KnockCount": latest.get("knock", 0),
                    "MAP_kPa": 100 + float(latest.get("boost_kpa", 0)),
                    "IAT_C": 35.0,
                    "ECT_C": 92.0,
                    "IgnitionTiming": 15.0,
                    "TPS": 95.0,
                }
            )

            pct = int(min(95, 5 + (90.0 * ev.get("step", 0) / max(1, ev.get("steps", 1)))))
            yield json.dumps(
                {
                    "type": "progress",
                    "message": f"Step {ev.get('step', 0)}/{ev.get('steps', 0)}",
                    "pct": pct,
                    "latest": latest,
                    "warnings": ev.get("warnings", []),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ) + "\n"

            if "Unsafe dyno condition detected (high knock). Abort dyno test." in (ev.get("warnings") or []):
                break

        result = _dyno_estimator.estimate(partial_rows, params=params, mode=mode)
        yield json.dumps({"type": "result", "pct": 100, "result": result, "timestamp": datetime.utcnow().isoformat()}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.get("/graphs/3d/{table_name}")
def graphs_3d(table_name: str, client: RusefiTunerClient = Depends(get_rusefi_client)):
    table_name = table_name.strip()
    if table_name not in ("veTable1", "ignitionTable1", "boostTable1", "lambdaTable1"):
        raise HTTPException(status_code=400, detail="Unsupported table")

    rows = 16
    cols = 16
    data: List[List[float]] = [[0.0 for _ in range(cols)] for _ in range(rows)]
    connected = False

    if client.is_connected():
        raw = client.read_table(table_name)
        if raw is not None:
            connected = True
            raw_values = list(raw)
            r, c = _infer_dims(len(raw_values))
            if r > 0 and c > 0:
                rows, cols = r, c
                logical = [_decode_raw_value(table_name, v) for v in raw_values]
                data = _reshape_flat(logical, rows, cols)

    rpm_axis = _default_axis(table_name, cols, "rpm")
    map_axis = _default_axis(table_name, rows, "map_kpa")

    plotly_json = {
        "data": [
            {
                "type": "surface",
                "x": rpm_axis,
                "y": map_axis,
                "z": data,
                "colorscale": "RdBu",
                "hovertemplate": "RPM=%{x}<br>MAP=%{y}<br>Value=%{z}<extra></extra>",
            }
        ],
        "layout": {
            "title": f"{table_name} 3D Surface",
            "scene": {
                "xaxis": {"title": "RPM"},
                "yaxis": {"title": "MAP/Load"},
                "zaxis": {"title": "Value"},
            },
            "height": 560,
        },
    }
    return {
        "table_name": table_name,
        "rows": rows,
        "cols": cols,
        "rpm_axis": rpm_axis,
        "map_axis": map_axis,
        "data": data,
        "connected": connected,
        "plotly_json": plotly_json,
    }


@router.get("/dashboards/channels")
def dashboards_channels(client: RusefiTunerClient = Depends(get_rusefi_client)):
    defaults = [
        "RPM",
        "AFR",
        "MAP_kPa",
        "IAT_C",
        "ECT_C",
        "KnockCount",
        "InjectorDuty_pct",
        "TPS",
        "batteryV",
        "OilPressure",
        "FuelLevel",
    ]
    dynamic: List[str] = []
    try:
        if hasattr(client, "get_output_channel_list"):
            dynamic = list(getattr(client, "get_output_channel_list")() or [])
        else:
            live = client.get_live_data() if client.is_connected() else {}
            dynamic = list((live or {}).keys())
    except Exception:
        dynamic = []
    channels = sorted(list({*defaults, *dynamic}))
    return {"channels": channels}


@router.post("/dashboards/save")
def dashboards_save(request: Dict[str, Any]):
    name = request.get("name") or (request.get("layout_json") or {}).get("name") or "dashboard"
    layout_json = request.get("layout_json")
    if not isinstance(layout_json, dict):
        raise HTTPException(status_code=400, detail="layout_json must be an object")
    path = _dashboard_path(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(layout_json, f, indent=2)
    return {"status": "saved", "name": _safe_dashboard_name(name), "path": path}


@router.get("/dashboards/load/{name}")
def dashboards_load(name: str):
    path = _dashboard_path(name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Dashboard not found")
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return {"name": _safe_dashboard_name(name), "layout_json": payload}


@router.get("/dashboards/list")
def dashboards_list():
    names = []
    for file_name in os.listdir(DASHBOARD_DIR):
        if file_name.lower().endswith(".json"):
            names.append(os.path.splitext(file_name)[0])
    names.sort()
    return {"dashboards": names}


@router.post("/dashboards/import")
def dashboards_import(file: UploadFile = File(...)):
    raw = file.file.read()
    layout = _parse_dash_bytes(raw)
    if not layout:
        raise HTTPException(status_code=400, detail="Unable to parse .dash file")
    name = layout.get("name", "imported_dash")
    path = _dashboard_path(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=2)
    return {"status": "imported", "name": _safe_dashboard_name(name)}



# --- Table Operations (Unified) ---

@router.post("/tables/load", response_model=TablesLoadResponse)
def tables_load(req: TablesLoadRequest, client: RusefiTunerClient = Depends(get_rusefi_client)):
    if not client.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    
    try:
        # Use ParameterRegistry for metadata and reading
        p_data = _parameters.read_parameter(req.table_name)
        values = p_data["value"]
        name = p_data["name"]
        
        # Resolve dimensions from definition
        d = _parameters._definitions[name]
        if d.shape:
            rows, cols = d.shape
        else:
            rows, cols = _infer_dims(len(values))
            
        data = _reshape_flat(values, rows, cols)
        
        # Fallback to defaults for axes
        rpm_axis = _default_axis(name, cols, "rpm")
        map_axis = _default_axis(name, rows, "map_kpa")
        
        return TablesLoadResponse(
            table_name=name,
            rows=rows,
            cols=cols,
            rpm_axis=rpm_axis,
            map_axis=map_axis,
            data=data,
            connected_port=client.port_name or "unknown",
        )
    except Exception as e:
        logger.error(f"Table load error: {e}")
        raise HTTPException(status_code=404, detail=f"Table {req.table_name} failed: {str(e)}")


@router.post("/tables/save", response_model=TablesSaveResponse)
def tables_save(req: TablesSaveRequest, client: RusefiTunerClient = Depends(get_rusefi_client)):
    if not client.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    
    rows, cols = _validate_matrix(req.data)
    flat_data = _flatten_matrix(req.data)
    
    try:
        # Check limits using registry
        d = _parameters._definitions.get(_parameters.resolve_name(req.table_name))
        min_allowed = d.min_val if d and d.min_val is not None else -1e38
        max_allowed = d.max_val if d and d.max_val is not None else 1e38
        
        out_of_range = sum(1 for v in flat_data if v < min_allowed or v > max_allowed)
        if out_of_range > 0 and not req.confirm_out_of_range:
            return TablesSaveResponse(
                status="warning",
                table_name=req.table_name,
                cells_written=0,
                warning=TablesGuardrailWarning(
                    requires_confirmation=True,
                    out_of_range_cells=out_of_range,
                    min_allowed=min_allowed,
                    max_allowed=max_allowed,
                    message=f"{out_of_range} cells exceed safety limits."
                )
            )
        
        # Write via registry with explicit safety guard reset.
        with _parameters.temporary_write_access():
            if _parameters.write_parameter(req.table_name, flat_data, force=req.confirm_out_of_range):
                 return TablesSaveResponse(status="success", table_name=req.table_name, cells_written=len(flat_data))
            raise RuntimeError("Write returned False")
            
    except Exception as e:
        logger.error(f"Table save error: {e}")
        raise HTTPException(status_code=500, detail=f"Table save failed: {str(e)}")


@router.post("/tables/compare")
def tables_compare(req: TablesSaveRequest, client: RusefiTunerClient = Depends(get_rusefi_client)):
    if not client.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    
    try:
        ecu_p = _parameters.read_parameter(req.table_name)
        ecu_values = ecu_p["value"]
        local_values = _flatten_matrix(req.data)
        
        if len(ecu_values) != len(local_values):
            raise HTTPException(status_code=400, detail="Table dimension mismatch")
            
        delta = [round(local_values[i] - ecu_values[i], 3) for i in range(len(ecu_values))]
        rows, cols = _infer_dims(len(ecu_values))
        
        return {
            "table_name": req.table_name,
            "ecu_data": _reshape_flat(ecu_values, rows, cols),
            "local_data": req.data,
            "delta": _reshape_flat(delta, rows, cols),
            "changed_cells": sum(1 for d in delta if abs(d) > 0.001)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compare failed: {str(e)}")


@router.post("/tables/export_msq")
def tables_export_msq(req: TablesExportMsqRequest):
    # Handled by ParameterRegistry now
    try:
        content = _parameters.export_msq_bytes()
        return Response(
            content=content,
            media_type="application/xml",
            headers={"Content-Disposition": f"attachment; filename={req.table_name}.msq"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/tables/import_msq", response_model=TablesImportMsqResponse)
def tables_import_msq(file: UploadFile = File(...), table_name: str = "veTable1"):
    try:
        content = file.file.read()
        res = _parameters.import_msq_bytes(content, apply_to_ecu=False)
        
        # We need to return the data for the specific table for the UI
        p_data = _parameters.read_parameter(table_name)
        values = p_data["value"]
        rows, cols = _infer_dims(len(values))
        
        return TablesImportMsqResponse(
            table_name=table_name,
            rows=rows,
            cols=cols,
            rpm_axis=_default_axis(table_name, cols, "rpm"),
            map_axis=_default_axis(table_name, rows, "map_kpa"),
            data=_reshape_flat(values, rows, cols),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {str(e)}")


# --- Parameter Operations (Unified) ---

@router.get("/parameters/list")
def parameters_list(query: str = "", category: str = "", kind: str = ""):
    return _parameters.list_parameters(query, category, kind)


@router.get("/parameters/read/{name}")
@router.post("/parameters/read")
def parameters_read(name: Optional[str] = None, request: Dict[str, Any] | None = None):
    p_name = name or (request or {}).get("name")
    if not p_name: raise HTTPException(status_code=400, detail="Missing name")
    try:
        return _parameters.read_parameter(p_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/parameters/write")
def parameters_write(request: Dict[str, Any]):
    items = request.get("items")
    force = bool(request.get("force", False))
    burn_after = bool(request.get("burn_after", False))
    
    try:
        with _parameters.temporary_write_access():
            if isinstance(items, list):
                results = _parameters.write_many(items, force=force)
            else:
                name = request.get("name")
                value = request.get("value")
                if not name: raise HTTPException(status_code=400, detail="Missing name or items")
                results = {"success": _parameters.write_parameter(name, value, force=force)}
            
            if burn_after:
                _parameters.burn()
            
        return results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/parameters/burn")
def parameters_burn(request: Dict[str, Any] | None = None):
    pages = (request or {}).get("pages")
    with _parameters.temporary_write_access():
        return {"success": _parameters.burn(pages)}


@router.post("/parameters/export_msq")
def parameters_export_msq(include_read_only: bool = False):
    content = _parameters.export_msq_bytes(include_read_only)
    return Response(
        content=content,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=full_tune.msq"},
    )


@router.post("/parameters/import_msq")
def parameters_import_msq(file: UploadFile = File(...), apply_to_ecu: bool = True, burn_after: bool = False, force: bool = False):
    content = file.file.read()
    return _parameters.import_msq_bytes(content, apply_to_ecu, burn_after, force)


# --- Preset Operations ---
@router.get("/presets/list")
def presets_list():
    return {"presets": _presets.list_presets()}


@router.post("/presets/apply")
def presets_apply(request: Dict[str, Any]):
    preset_name = str(request.get("preset_name", "")).strip()
    if not preset_name:
        raise HTTPException(status_code=400, detail="preset_name is required")
    burn_after = bool(request.get("burn_after", False))
    overrides = request.get("overrides")
    if overrides is not None and not isinstance(overrides, dict):
        raise HTTPException(status_code=400, detail="overrides must be an object")
    try:
        return _presets.apply_preset(
            preset_id_or_name=preset_name,
            burn_after=burn_after,
            overrides=overrides,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Preset apply failed: {e}")


@router.post("/presets/save")
def presets_save(request: Dict[str, Any]):
    name = str(request.get("name", "")).strip()
    values = request.get("values")
    notes = request.get("notes")
    base_preset = request.get("base_preset")
    if notes is not None and not isinstance(notes, list):
        raise HTTPException(status_code=400, detail="notes must be a list of strings")
    if values is not None and not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="values must be an object")
    try:
        saved = _presets.save_custom_preset(
            name=name,
            values=values,
            notes=notes,
            base_preset=base_preset,
        )
        return {"status": "saved", "preset": saved}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Preset save failed: {e}")


# --- Legacy / Utility ---

@router.post("/rusefi/read_table")
def rusefi_read_table(req: TableRequest):
    return tables_load(TablesLoadRequest(table_name=req.table_name), _ecu_client)

@router.post("/rusefi/write_table")
def rusefi_write_table(req: TableWriteRequest):
    return tables_save(TablesSaveRequest(table_name=req.table_name, data=req.data), _ecu_client)

@router.post("/rusefi/burn")
def rusefi_burn():
    return parameters_burn()




