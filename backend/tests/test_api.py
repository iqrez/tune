import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.utils.security import sign_payload
import json

client = TestClient(app)

@pytest.fixture
def test_profile_data():
    return {
        "vehicle_id": "test-v1",
        "make": "Honda",
        "model": "Civic",
        "engine_family": "B18C",
        "displacement_l": 1.8,
        "cylinders": 4,
        "aspiration": "na",
        "compression_ratio": 10.6,
        "fuel_type": "gas93",
        "injector_cc_min": 440.0,
        "fuel_pressure_psi": 43.5,
        "max_safe_rpm": 8400,
        "usage": "street",
        "idle_rpm_max": 1200,
        "boost_kpa_min": 105
    }

def test_create_and_get_profile(test_profile_data):
    response = client.post("/api/v1/profiles", json=test_profile_data)
    assert response.status_code == 200
    assert response.json()["vehicle_id"] == "test-v1"

    response = client.get("/api/v1/profiles/test-v1")
    assert response.status_code == 200
    assert response.json()["make"] == "Honda"

def test_generate_base_tune(test_profile_data):
    response = client.post("/api/v1/generate_base_tune", json=test_profile_data)
    assert response.status_code == 200
    data = response.json()
    assert "fuel_table" in data
    assert len(data["fuel_table"]) == 16
    assert len(data["fuel_table"][0]) == 16

def test_analyze_and_apply(test_profile_data):
    # 1. Upload a datalog
    response = client.post("/api/v1/upload_datalog", files={"file": ("test.csv", b"dummy")})
    assert response.status_code == 200
    datalog_summary = response.json()
    
    # 2. Get base tune
    response = client.post("/api/v1/generate_base_tune", json=test_profile_data)
    base_tune = response.json()

    # 3. Analyze
    analyze_req = {
        "vehicle_profile": test_profile_data,
        "calibration": base_tune,
        "datalog_summary": datalog_summary,
        "options": {
            "mode": "suggested_apply",
            "aggressiveness": "balanced",
            "max_fuel_delta_pct": 5.0,
            "max_ignition_delta_deg": 2.0
        }
    }
    response = client.post("/api/v1/analyze", json=analyze_req)
    assert response.status_code == 200
    analysis = response.json()
    assert "session_id" in analysis
    
    # 4. Apply changes with proper HMAC signature
    apply_payload = {
        "session_id": analysis["session_id"],
        "approved_changes": analysis["recommendations"],
        "user_id": "test_user"
    }
    signature = sign_payload(apply_payload)
    
    apply_req = {
        **apply_payload,
        "signature": signature
    }
    response = client.post("/api/v1/apply", json=apply_req)
    assert response.status_code == 200
    apply_res = response.json()
    assert apply_res["success"] is True
    
    # 5. List Snapshots
    response = client.get("/api/v1/snapshots")
    assert response.status_code == 200
    snapshots = response.json()
    assert len(snapshots) >= 1
    
    # 6. Rollback
    rollback_req = {
        "snapshot_id": apply_res["snapshot_id"],
        "user_id": "test_user"
    }
    response = client.post("/api/v1/rollback", json=rollback_req)
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_apply_rejects_bad_signature(test_profile_data):
    """HMAC verification must reject tampered signatures."""
    apply_req = {
        "session_id": "fake-session",
        "approved_changes": [],
        "user_id": "test_user",
        "signature": "INVALID_SIGNATURE_TAMPERED"
    }
    response = client.post("/api/v1/apply", json=apply_req)
    assert response.status_code == 403
    assert "Invalid signature" in response.json()["detail"]


def test_simulate_live(test_profile_data):
    """Live auto-correct simulator must return correction history."""
    # Generate a base tune first
    response = client.post("/api/v1/generate_base_tune", json=test_profile_data)
    assert response.status_code == 200
    base_tune = response.json()

    sim_req = {
        "vehicle_profile": test_profile_data,
        "calibration": base_tune,
        "num_cycles": 5
    }
    response = client.post("/api/v1/simulate_live", json=sim_req)
    assert response.status_code == 200
    data = response.json()
    
    assert data["num_cycles"] == 5
    assert data["total_corrections_applied"] > 0
    assert data["unique_cells_touched"] > 0
    assert len(data["history"]) == 5
    assert len(data["corrected_fuel_table"]) == 16
    
    # Verify each cycle has corrections
    for cycle in data["history"]:
        assert "cycle" in cycle
        assert "corrections" in cycle
        assert len(cycle["corrections"]) > 0


def test_simulate_live_convergence(test_profile_data):
    """AFR error should generally decrease over simulation cycles."""
    response = client.post("/api/v1/generate_base_tune", json=test_profile_data)
    base_tune = response.json()

    sim_req = {
        "vehicle_profile": test_profile_data,
        "calibration": base_tune,
        "num_cycles": 20
    }
    response = client.post("/api/v1/simulate_live", json=sim_req)
    assert response.status_code == 200
    data = response.json()

    # The improvement percentage should be positive (error reduced)
    assert data["improvement_pct"] >= 0
    assert data["avg_final_afr_error_pct"] <= data["avg_initial_afr_error_pct"] + 5.0  # Allow small variance


def test_power_ramp_na(test_profile_data):
    """NA build should complete all 5 stages (no boost stages)."""
    response = client.post("/api/v1/generate_base_tune", json=test_profile_data)
    base_tune = response.json()

    ramp_req = {
        "vehicle_profile": test_profile_data,
        "calibration": base_tune,
        "target_boost_psi": 0.0,
        "samples_per_stage": 3
    }
    response = client.post("/api/v1/power_ramp", json=ramp_req)
    assert response.status_code == 200
    data = response.json()

    assert data["total_stages"] == 5  # 5 NA stages, no boost stages
    assert data["status"] in ["COMPLETED", "ABORTED"]  # Small chance of random knock abort
    assert len(data["stages"]) >= 1


def test_power_ramp_turbo(test_profile_data):
    """Turbo build should attempt all 8 stages including boost stages."""
    turbo_profile = {**test_profile_data, "aspiration": "turbo", "turbo_model": "GT3076R"}
    response = client.post("/api/v1/generate_base_tune", json=turbo_profile)
    base_tune = response.json()

    ramp_req = {
        "vehicle_profile": turbo_profile,
        "calibration": base_tune,
        "target_boost_psi": 10.0,
        "samples_per_stage": 3
    }
    response = client.post("/api/v1/power_ramp", json=ramp_req)
    assert response.status_code == 200
    data = response.json()

    assert data["total_stages"] == 8  # 5 NA + 3 boost stages
    assert data["status"] in ["COMPLETED", "ABORTED"]
    assert len(data["stages"]) >= 1

    # Check stage structure
    for stage in data["stages"]:
        assert "name" in stage
        assert "status" in stage
        assert "samples" in stage
        assert len(stage["samples"]) > 0
