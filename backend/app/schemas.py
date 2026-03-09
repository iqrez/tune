from pydantic import BaseModel, Field
from typing import Any, List, Optional, Dict, Literal
from datetime import datetime

class VehicleProfile(BaseModel):
    vehicle_id: str
    make: str
    model: str
    engine_family: str
    displacement_l: float
    cylinders: int
    aspiration: Literal["turbo", "na", "supercharged"]
    compression_ratio: float
    fuel_type: Literal["gas93", "gas98", "e85", "custom"]
    injector_cc_min: float
    fuel_pressure_psi: float
    max_safe_rpm: int
    turbo_model: Optional[str] = None
    wastegate_type: Optional[Literal["internal", "external"]] = None
    target_hp: Optional[float] = None
    usage: Literal["street", "track", "dyno"]
    notes: Optional[str] = None
    
    # Required for continuous AFR zones (Added during analysis)
    idle_rpm_max: int = 1200
    boost_kpa_min: int = 105

class CalibrationSnapshot(BaseModel):
    axes: Dict[str, List[float]] # e.g. {"rpm": [...], "map_kpa": [...]} 
    fuel_table: List[List[float]]
    ignition_table: List[List[float]]
    boost_table: List[List[float]]
    metadata: dict = Field(default_factory=dict) # timestamp, source

class DatalogCell(BaseModel):
    rpm_index: int
    map_index: int
    occupied_pct: float
    target_afr: Optional[float] = None
    measured_afr: Optional[float] = None
    afr_error_pct: Optional[float] = None
    knock_count: int = 0
    iat_c: float
    ect_c: float
    lambda_corrections: float = 0.0

class DatalogGlobalStats(BaseModel):
    max_knock_cell: Dict[str, int]
    avg_iat_c: float
    max_injector_duty_pct: float

class DatalogSummary(BaseModel):
    session_id: str
    cells: List[DatalogCell]
    global_stats: DatalogGlobalStats

class AnalysisOptions(BaseModel):
    mode: Literal["advisory", "suggested_apply", "limited_auto_apply"]
    aggressiveness: Literal["conservative", "balanced", "aggressive"]
    max_fuel_delta_pct: float = 5.0
    max_ignition_delta_deg: float = 2.0

class AnalysisRequest(BaseModel):
    vehicle_profile: VehicleProfile
    calibration: CalibrationSnapshot
    datalog_summary: DatalogSummary
    options: AnalysisOptions

class Recommendation(BaseModel):
    rpm_index: int
    map_index: int
    delta_fuel_pct: float
    delta_ign_deg: float
    confidence: float
    rationale: str

class AnalysisResponse(BaseModel):
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    recommendations: List[Recommendation]
    summary_text: str
    warnings: List[str]
    signature: str # HMAC

class ApplyRequest(BaseModel):
    session_id: str
    approved_changes: List[Recommendation]
    user_id: str
    signature: str

class ApplyResponse(BaseModel):
    success: bool
    snapshot_id: str
    message: str

class SnapshotListItem(BaseModel):
    id: str
    session_id: str
    created_at: datetime
    signature: str

class RollbackRequest(BaseModel):
    snapshot_id: str
    user_id: str

class SimulateLiveRequest(BaseModel):
    vehicle_profile: VehicleProfile
    calibration: CalibrationSnapshot
    num_cycles: int = 20

class SimulateLiveResponse(BaseModel):
    num_cycles: int
    total_corrections_applied: int
    unique_cells_touched: int
    avg_initial_afr_error_pct: float
    avg_final_afr_error_pct: float
    improvement_pct: float
    history: List[dict]
    corrected_fuel_table: List[List[float]]

class PowerRampRequest(BaseModel):
    vehicle_profile: VehicleProfile
    calibration: CalibrationSnapshot
    target_boost_psi: float = 0.0
    samples_per_stage: int = 5

class PowerRampResponse(BaseModel):
    total_stages: int
    completed_stages: int
    status: str  # "COMPLETED" or "ABORTED"
    abort_details: Optional[dict] = None
    stages: List[dict]

class ConnectRequest(BaseModel):
    connection_type: Literal["tcp", "serial"]
    host: Optional[str] = "127.0.0.1"
    port: Optional[int] = 29002
    serial_port: Optional[str] = None
    baudrate: int = 115200

class LiveDataResponse(BaseModel):
    connected: bool
    rpm: float
    map_kpa: float
    afr: float
    iat: float
    ect: float
    advance: float
    knock_count: int
    injector_duty: float
    voltage: float = 0.0
    tps: float = 0.0
    lambda_val: float = 0.0
    console_mode: bool = False
    signature_mode: bool = False
    uptime_s: Optional[float] = None
    port: Optional[str] = None
    connection_type: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class TableRequest(BaseModel):
    table_name: str # e.g. "veTable1"
    page: int = 0
    offset: int = 0
    count: int = 256

class TableWriteRequest(BaseModel):
    table_name: str
    page: int = 0
    offset: int = 0
    data: List[float] # Flattened 1D list for writing chunks

class TablesLoadRequest(BaseModel):
    table_name: str

class TablesLoadResponse(BaseModel):
    table_name: str
    rows: int
    cols: int
    rpm_axis: List[float]
    map_axis: List[float]
    data: List[List[float]]
    connected_port: str

class TablesSaveRequest(BaseModel):
    table_name: str
    data: List[List[float]]
    confirm_out_of_range: bool = False

class TablesGuardrailWarning(BaseModel):
    requires_confirmation: bool
    out_of_range_cells: int
    min_allowed: float
    max_allowed: float
    message: str

class TablesSaveResponse(BaseModel):
    status: str
    table_name: str
    cells_written: int
    warning: Optional[TablesGuardrailWarning] = None

class TablesExportMsqRequest(BaseModel):
    table_name: str
    data: List[List[float]]
    rpm_axis: List[float]
    map_axis: List[float]

class TablesImportMsqResponse(BaseModel):
    table_name: str
    rows: int
    cols: int
    rpm_axis: List[float]
    map_axis: List[float]
    data: List[List[float]]


class DatalogStartRequest(BaseModel):
    profile_id: str = "unknown"
    high_speed: bool = False


class DatalogStopRequest(BaseModel):
    filename: Optional[str] = None


class DatalogLoadResponse(BaseModel):
    filename: str
    rows: List[Dict[str, float]]
    channels: List[str]
    samples: int


class DatalogAnalyzeRequest(BaseModel):
    log_data_summary: Dict[str, Any]
