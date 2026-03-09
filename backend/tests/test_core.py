import pytest
from app.schemas import VehicleProfile, AnalysisRequest, CalibrationSnapshot, DatalogSummary, DatalogGlobalStats, DatalogCell, AnalysisOptions, Recommendation
from app.core.math_engine import DeterministicEngineModel
from app.core.guardrails import GuardrailEngine

@pytest.fixture
def mock_profile():
    return VehicleProfile(
        vehicle_id="test-123",
        make="Honda",
        model="Civic",
        engine_family="B18C",
        displacement_l=1.8,
        cylinders=4,
        aspiration="na",
        compression_ratio=10.6,
        fuel_type="gas93",
        injector_cc_min=440.0,
        fuel_pressure_psi=43.5,
        max_safe_rpm=8400,
        usage="street"
    )

def test_math_engine_injector_scaling(mock_profile):
    engine = DeterministicEngineModel(mock_profile)
    # 100 kPa (WOT NA), 80% VE, 30C IAT, 13.0 AFR
    pw = engine.estimate_injector_scaling_ms(0.80, 100.0, 30.0, 13.0)
    # Just asserting it calculates something reasonable (e.g. 5-15ms for this setup)
    assert 5.0 < pw < 10.0

def test_guardrails_duty_cycle_rejection(mock_profile):
    # Setup global stats exceeding duty cycle
    req = AnalysisRequest(
        vehicle_profile=mock_profile,
        calibration=CalibrationSnapshot(axes={"rpm":[],"map_kpa":[]}, fuel_table=[], ignition_table=[], boost_table=[]),
        datalog_summary=DatalogSummary(
            session_id="session1",
            cells=[],
            global_stats=DatalogGlobalStats(max_knock_cell={"rpm":0,"map":0}, avg_iat_c=40, max_injector_duty_pct=88.5) # DANGER
        ),
        options=AnalysisOptions(mode="suggested_apply", aggressiveness="balanced")
    )
    
    guard = GuardrailEngine(req)
    raw_rec = Recommendation(rpm_index=5, map_index=5, delta_fuel_pct=5.0, delta_ign_deg=0.0, confidence=0.9, rationale="Add fuel")
    
    valid_recs, warnings = guard.run_all_guardrails([raw_rec])
    
    # Delta fuel should be clamped to 0 because duty > 85%
    assert len(valid_recs) == 1
    assert valid_recs[0].delta_fuel_pct == 0.0
    assert any("duty exceeded 85%" in w for w in warnings)

def test_guardrails_knock_ignition_lock(mock_profile):
    # Cell has knock
    bad_cell = DatalogCell(rpm_index=10, map_index=10, occupied_pct=10.0, iat_c=40, ect_c=90, knock_count=2)
    req = AnalysisRequest(
        vehicle_profile=mock_profile,
        calibration=CalibrationSnapshot(axes={"rpm":[],"map_kpa":[]}, fuel_table=[], ignition_table=[], boost_table=[]),
        datalog_summary=DatalogSummary(
            session_id="session1",
            cells=[bad_cell],
            global_stats=DatalogGlobalStats(max_knock_cell={"rpm":10,"map":10}, avg_iat_c=40, max_injector_duty_pct=50)
        ),
        options=AnalysisOptions(mode="suggested_apply", aggressiveness="balanced")
    )
    
    guard = GuardrailEngine(req)
    # LLM foolishly recommends adding timing where it just knocked
    raw_rec = Recommendation(rpm_index=10, map_index=10, delta_fuel_pct=0.0, delta_ign_deg=2.0, confidence=0.9, rationale="Add timing")
    
    valid_recs, warnings = guard.run_all_guardrails([raw_rec])
    
    # Should completely reject the ignition change
    assert len(valid_recs) == 0
    assert any("knock in cell" in w for w in warnings)

def test_guardrails_clamp(mock_profile):
    good_cell = DatalogCell(rpm_index=5, map_index=5, occupied_pct=10.0, iat_c=40, ect_c=90, knock_count=0)
    req = AnalysisRequest(
        vehicle_profile=mock_profile,
        calibration=CalibrationSnapshot(axes={"rpm":[],"map_kpa":[]}, fuel_table=[], ignition_table=[], boost_table=[]),
        datalog_summary=DatalogSummary(
            session_id="session1",
            cells=[good_cell],
            global_stats=DatalogGlobalStats(max_knock_cell={"rpm":0,"map":0}, avg_iat_c=40, max_injector_duty_pct=50)
        ),
        options=AnalysisOptions(mode="suggested_apply", aggressiveness="balanced", max_fuel_delta_pct=3.0)
    )
    
    guard = GuardrailEngine(req)
    # Recommend +10% fuel, limit is 3.0%
    raw_rec = Recommendation(rpm_index=5, map_index=5, delta_fuel_pct=10.0, delta_ign_deg=0.0, confidence=0.9, rationale="Way lean")
    valid_recs, warnings = guard.run_all_guardrails([raw_rec])
    
    assert len(valid_recs) == 1
    assert valid_recs[0].delta_fuel_pct == 3.0 # Clamped!
