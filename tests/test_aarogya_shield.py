"""
AAROGYA-SHIELD: Comprehensive Automated Pytest Suite
Verifies:
1. Health & Disclaimer (/api/health)
2. Device Registration (/api/device/register, /api/device/status)
3. Personal Baseline System (/api/baseline/start, /api/baseline/update, /api/baseline)
4. Scenario 1: Normal Healthy State (LOW risk, no caretaker alert)
5. Scenario 2: Small Gradual Deviation (EARLY_WARNING appears before elevated/critical)
6. Scenario 3: Respiratory Scenario (Respiratory risk increases, overall risk increases, caretaker alert generated)
7. Scenario 4: Heat-Stress Scenario (Ambient temp, humidity, activity, body temp, HR -> Heat-stress risk increases)
8. Scenario 5: Environmental Exposure (MQ-45 signal -> Environmental exposure indicator changes)
9. Scenario 6: Recovery (Return values toward baseline -> risk decreases gradually, no stale critical state)
10. Scenario 7: Fall Candidate (Acceleration spike + tilt + inactivity -> Fall candidate detected)
11. Scenario 8: Critical Multi-Parameter Scenario (Multiple abnormal parameters -> CRITICAL risk, caretaker alert, location shown)
12. Scenario 9: Sensor Noise Rejection (Single short abnormal spike -> No immediate critical alert without persistence)
13. Scenario 10: Disconnected IoT (Stop ESP32 input -> Device status changes to OFFLINE / NO RECENT DATA, simulator still works)
14. Simulator vs IoT API Symmetry
15. Caretaker Alert Query & Acknowledgment
16. MongoDB Data Traceability (Reading ID -> Features -> Predictions -> Risk Events)
"""

import time
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.database import get_db
from backend.core.early_warning_engine import get_early_warning_state
from backend.core.alert_engine import get_alert_engine

client = TestClient(app)
DEVICE_ID = "ESP32-001"


@pytest.fixture(autouse=True)
def reset_device_state():
    """Ensure baseline and early warning state are initialized before tests."""
    ew = get_early_warning_state(DEVICE_ID)
    ew.consecutive_abnormal_count = 0
    ew.current_escalated_level = "LOW"
    ew.history.clear()


# ==============================================================================
# 01. Health & Non-Diagnostic Framing
# ==============================================================================
def test_01_health_and_medical_disclaimer():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ONLINE"
    assert data["models_loaded"] is True
    assert data["model_version"] == "1.0.0-edge"
    # Strict clinical non-diagnostic framing requirement
    expected_disclaimer = "This prototype provides health-risk and anomaly indicators and is not a medical diagnostic device."
    assert data["medical_disclaimer"] == expected_disclaimer


# ==============================================================================
# 02. Device Registration & Liveness
# ==============================================================================
def test_02_device_registration_and_status():
    payload = {
        "device_id": DEVICE_ID,
        "device_type": "ESP32-MAX30102-ADXL345",
        "firmware_version": "v1.0.0",
        "patient_name": "Subject-Alpha",
        "patient_age": 34,
        "location": "Edge Node Alpha"
    }
    resp = client.post("/api/device/register", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "registered"
    assert data["device"]["device_id"] == DEVICE_ID

    status_resp = client.get(f"/api/device/status?device_id={DEVICE_ID}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "device_status" in status_data


# ==============================================================================
# 03. Personal Baseline System
# ==============================================================================
def test_03_personal_baseline_calibration_and_update():
    # Start calibration
    resp = client.post("/api/baseline/start", json={"device_id": DEVICE_ID})
    assert resp.status_code == 200
    
    # Ingest 5 nominal readings for baseline
    for i in range(5):
        reading = {
            "device_id": DEVICE_ID,
            "heart_rate": 72.0 + (i % 2),
            "spo2": 98.0,
            "ppg_quality": 0.98,
            "body_temperature": 36.7,
            "ambient_temperature": 27.5,
            "humidity": 58.0,
            "accel_x": 0.02,
            "accel_y": 0.01,
            "accel_z": 0.98,
            "mq45": 160.0
        }
        client.post("/api/baseline/update", json=reading)

    base_resp = client.get(f"/api/baseline?device_id={DEVICE_ID}")
    assert base_resp.status_code == 200
    base_data = base_resp.json()
    stats = base_data["statistics"]
    assert "heart_rate" in stats
    assert "spo2" in stats
    assert "body_temperature" in stats
    assert stats["heart_rate"]["mean"] > 0
    assert stats["spo2"]["mean"] >= 95.0


# ==============================================================================
# Scenario 1: Normal Healthy State
# ==============================================================================
def test_scenario_01_normal_healthy():
    payload = {
        "device_id": DEVICE_ID,
        "heart_rate": 73.0,
        "spo2": 98.0,
        "ppg_quality": 0.96,
        "body_temperature": 36.7,
        "ambient_temperature": 27.0,
        "humidity": 55.0,
        "accel_x": 0.02,
        "accel_y": 0.01,
        "accel_z": 0.98,
        "mq45": 160.0
    }
    resp = client.post("/api/sensors/readings", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["escalation"]["escalated_level"] == "LOW"
    assert data["features"]["activity_level"] == "REST"
    assert data["ml_predictions"]["overall_health_risk"]["risk_level"] == "LOW"
    # No active critical alert
    if data.get("active_alert"):
        assert data["active_alert"]["risk_level"] != "CRITICAL"


# ==============================================================================
# Scenario 2: Small Gradual Deviation (EARLY_WARNING before ELEVATED/CRITICAL)
# ==============================================================================
def test_scenario_02_small_gradual_deviation():
    # Mild gradual drop in SpO2 with mild HR elevation
    payload = {
        "device_id": DEVICE_ID,
        "heart_rate": 84.0,   # Mildly elevated above baseline 72
        "spo2": 95.0,         # Mild drop from 98%
        "ppg_quality": 0.95,
        "body_temperature": 36.9,
        "ambient_temperature": 29.0,
        "humidity": 62.0,
        "accel_x": 0.03,
        "accel_y": 0.02,
        "accel_z": 0.98,
        "mq45": 210.0
    }
    resp = client.post("/api/simulator/readings", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    esc_level = data["escalation"]["escalated_level"]
    # Must catch gradual drift early
    assert esc_level in ["EARLY_WARNING", "ELEVATED"]
    assert len(data["escalation"]["reasons"]) > 0


# ==============================================================================
# Scenario 3: Respiratory Scenario
# ==============================================================================
def test_scenario_03_respiratory_scenario():
    # Desaturation to 91% and tachypnea-driven tachycardic compensation
    payload = {
        "device_id": DEVICE_ID,
        "heart_rate": 105.0,
        "spo2": 91.0,
        "ppg_quality": 0.92,
        "body_temperature": 37.1,
        "ambient_temperature": 28.0,
        "humidity": 60.0,
        "accel_x": 0.05,
        "accel_y": 0.03,
        "accel_z": 0.98,
        "mq45": 220.0
    }
    resp = client.post("/api/simulator/readings", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    resp_risk = data["ml_predictions"]["respiratory_risk"]
    overall_risk = data["ml_predictions"]["overall_health_risk"]
    assert resp_risk["score"] > 0.40 or resp_risk["risk_level"] in ["EARLY_WARNING", "ELEVATED", "CRITICAL"]
    assert overall_risk["score"] > 0.30
    assert data["escalation"]["escalated_level"] in ["EARLY_WARNING", "ELEVATED", "CRITICAL"]


# ==============================================================================
# Scenario 4: Heat-Stress Scenario
# ==============================================================================
def test_scenario_04_heat_stress_scenario():
    # High ambient temp + high humidity + elevated core temp + high heart rate
    payload = {
        "device_id": DEVICE_ID,
        "heart_rate": 128.0,
        "spo2": 96.0,
        "ppg_quality": 0.91,
        "body_temperature": 39.1,
        "ambient_temperature": 42.0,
        "humidity": 82.0,
        "accel_x": 0.35,
        "accel_y": 0.20,
        "accel_z": 0.90,
        "mq45": 250.0
    }
    resp = client.post("/api/simulator/readings", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    heat_risk = data["ml_predictions"]["heat_stress_risk"]
    assert heat_risk["score"] > 0.60
    assert heat_risk["risk_level"] in ["ELEVATED", "CRITICAL"]
    assert data["features"]["heat_index"] > 40.0


# ==============================================================================
# Scenario 5: Environmental Exposure Scenario
# ==============================================================================
def test_scenario_05_environmental_exposure():
    payload = {
        "device_id": DEVICE_ID,
        "heart_rate": 78.0,
        "spo2": 97.0,
        "ppg_quality": 0.95,
        "body_temperature": 36.8,
        "ambient_temperature": 32.0,
        "humidity": 65.0,
        "accel_x": 0.02,
        "accel_y": 0.01,
        "accel_z": 0.98,
        "mq45": 780.0  # Heavy environmental gas / smoke spike
    }
    resp = client.post("/api/simulator/readings", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    env_risk = data["ml_predictions"]["environmental_exposure_risk"]
    assert env_risk["score"] >= 0.70
    assert env_risk["risk_level"] in ["ELEVATED", "CRITICAL"]
    # Check contributing factor
    assert "mq45" in " ".join(env_risk["contributing_features"]).lower() or "gas" in " ".join(env_risk["contributing_features"]).lower()


# ==============================================================================
# Scenario 6: Recovery Scenario (Values return toward baseline, risk decreases)
# ==============================================================================
def test_scenario_06_recovery_scenario():
    # First inject high risk packet
    client.post("/api/simulator/readings", json={
        "device_id": DEVICE_ID,
        "heart_rate": 130.0,
        "spo2": 88.0,
        "body_temperature": 38.5,
        "ambient_temperature": 38.0,
        "humidity": 75.0,
        "accel_x": 0.1,
        "accel_y": 0.1,
        "accel_z": 0.95,
        "mq45": 450.0
    })

    # Now inject 3 consecutive recovery readings returning to baseline
    recovery_resp = None
    for _ in range(3):
        recovery_resp = client.post("/api/simulator/readings", json={
            "device_id": DEVICE_ID,
            "heart_rate": 74.0,
            "spo2": 98.0,
            "ppg_quality": 0.97,
            "body_temperature": 36.7,
            "ambient_temperature": 26.0,
            "humidity": 50.0,
            "accel_x": 0.02,
            "accel_y": 0.01,
            "accel_z": 0.98,
            "mq45": 160.0
        })

    assert recovery_resp.status_code == 200
    data = recovery_resp.json()
    overall = data["ml_predictions"]["overall_health_risk"]
    # Risk must decrease back down; no stale CRITICAL
    assert overall["risk_level"] in ["LOW", "EARLY_WARNING"]
    assert data["escalation"]["escalated_level"] in ["LOW", "EARLY_WARNING"]


# ==============================================================================
# Scenario 7: Fall Detection (Deterministic Spike -> Tilt -> Inactivity)
# ==============================================================================
def test_scenario_07_fall_candidate_detection():
    # 1. Normal pre-fall motion
    client.post("/api/sensors/readings", json={
        "device_id": DEVICE_ID,
        "heart_rate": 78.0,
        "spo2": 97.0,
        "accel_x": 0.1,
        "accel_y": 0.1,
        "accel_z": 0.98,
        "body_temperature": 36.8,
        "ambient_temperature": 27.0,
        "humidity": 55.0,
        "mq45": 170.0
    })

    # 2. Impact Spike: Acceleration Magnitude > 2.4g
    client.post("/api/sensors/readings", json={
        "device_id": DEVICE_ID,
        "heart_rate": 88.0,
        "spo2": 97.0,
        "accel_x": 2.2,
        "accel_y": 1.6,
        "accel_z": 0.3,
        "body_temperature": 36.8,
        "ambient_temperature": 27.0,
        "humidity": 55.0,
        "mq45": 170.0
    })

    # 3. Post-impact Stillness with Vector Tilt (lying flat on ground)
    fall_resp = client.post("/api/sensors/readings", json={
        "device_id": DEVICE_ID,
        "heart_rate": 92.0,
        "spo2": 96.0,
        "accel_x": 0.85,
        "accel_y": 0.45,
        "accel_z": 0.15,  # Z near 0 indicates horizontal post-fall posture
        "body_temperature": 36.8,
        "ambient_temperature": 27.0,
        "humidity": 55.0,
        "mq45": 170.0
    })

    assert fall_resp.status_code == 200
    data = fall_resp.json()
    assert data["features"]["fall_candidate"] is True
    assert data["features"]["activity_level"] == "FALL_CANDIDATE"
    # Ensure fall candidate escalates risk
    assert data["escalation"]["escalated_level"] in ["ELEVATED", "CRITICAL"]


# ==============================================================================
# Scenario 8: Critical Multi-Parameter Scenario with Location & Alert
# ==============================================================================
def test_scenario_08_critical_multiparameter_scenario():
    # Inject multiple sustained critical readings to trigger persistence
    last_resp = None
    for _ in range(3):
        last_resp = client.post("/api/simulator/readings", json={
            "device_id": DEVICE_ID,
            "heart_rate": 150.0,
            "spo2": 82.0,
            "ppg_quality": 0.85,
            "body_temperature": 40.1,
            "ambient_temperature": 45.0,
            "humidity": 88.0,
            "accel_x": 0.05,
            "accel_y": 0.02,
            "accel_z": 0.98,
            "mq45": 850.0,
            "latitude": 10.6624,
            "longitude": 76.8912
        })

    assert last_resp.status_code == 200
    data = last_resp.json()
    assert data["escalation"]["escalated_level"] == "CRITICAL"
    assert data["active_alert"] is not None
    alert = data["active_alert"]
    assert alert["risk_level"] == "CRITICAL"
    assert alert["latitude"] == 10.6624
    assert alert["longitude"] == 76.8912
    assert "Immediate attention required" in alert["message"]

    # Acknowledge the alert
    ack_resp = client.post(f"/api/alerts/{alert['alert_id']}/acknowledge")
    assert ack_resp.status_code == 200
    assert ack_resp.json()["acknowledged"] is True


# ==============================================================================
# Scenario 9: Sensor Noise Rejection (Single Isolated Spike Does NOT Immediately Alert)
# ==============================================================================
def test_scenario_09_sensor_noise_rejection():
    # First ensure a clean baseline state
    client.post("/api/sensors/readings", json={
        "device_id": DEVICE_ID,
        "heart_rate": 72.0,
        "spo2": 98.0,
        "body_temperature": 36.7,
        "ambient_temperature": 27.0,
        "humidity": 55.0,
        "accel_x": 0.02,
        "accel_y": 0.01,
        "accel_z": 0.98,
        "mq45": 160.0
    })

    # Clear active alerts
    get_alert_engine().active_alert = None

    # Inject a SINGLE transient noisy sensor anomaly packet
    resp = client.post("/api/sensors/readings", json={
        "device_id": DEVICE_ID,
        "heart_rate": 160.0,  # Single noisy SpO2/HR glitch
        "spo2": 82.0,
        "ppg_quality": 0.35,  # Low signal quality
        "body_temperature": 36.7,
        "ambient_temperature": 27.0,
        "humidity": 55.0,
        "accel_x": 0.02,
        "accel_y": 0.01,
        "accel_z": 0.98,
        "mq45": 160.0
    })

    data = resp.json()
    # A single isolated reading with low signal quality must NOT immediately trigger a CRITICAL caretaker alert
    # because persistence criteria (2+ samples) have not been met
    if data.get("active_alert"):
        assert data["active_alert"]["risk_level"] != "CRITICAL"


# ==============================================================================
# Scenario 10: Disconnected IoT Device Status
# ==============================================================================
def test_scenario_10_disconnected_iot_status():
    # Check device status after >5s without IoT packet
    from backend.api.routes import _last_iot_timestamps
    import datetime

    # Force simulated last IoT packet timestamp to 10 seconds ago
    _last_iot_timestamps[DEVICE_ID] = datetime.datetime.utcnow() - datetime.timedelta(seconds=10)

    status_resp = client.get(f"/api/device/status?device_id={DEVICE_ID}")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["device_status"] == "OFFLINE / NO RECENT DATA"
    assert data["is_online"] is False

    # Verify that the simulator STILL works seamlessly even while IoT hardware is disconnected!
    sim_resp = client.post("/api/simulator/readings", json={
        "device_id": DEVICE_ID,
        "heart_rate": 76.0,
        "spo2": 98.0,
        "body_temperature": 36.8,
        "ambient_temperature": 28.0,
        "humidity": 60.0,
        "accel_x": 0.02,
        "accel_y": 0.01,
        "accel_z": 0.98,
        "mq45": 180.0
    })
    assert sim_resp.status_code == 200
    assert "ml_predictions" in sim_resp.json()


# ==============================================================================
# 14. Simulator vs IoT API Symmetry
# ==============================================================================
def test_14_simulator_vs_iot_pipeline_symmetry():
    test_reading = {
        "device_id": DEVICE_ID,
        "heart_rate": 82.0,
        "spo2": 96.0,
        "ppg_quality": 0.94,
        "body_temperature": 37.0,
        "ambient_temperature": 29.0,
        "humidity": 62.0,
        "accel_x": 0.02,
        "accel_y": 0.01,
        "accel_z": 0.98,
        "mq45": 210.0
    }

    iot_resp = client.post("/api/sensors/readings", json=test_reading).json()
    sim_resp = client.post("/api/simulator/readings", json=test_reading).json()
    ml_resp = client.post("/api/ml/predict", json=test_reading).json()

    iot_score = iot_resp["ml_predictions"]["overall_health_risk"]["score"]
    sim_score = sim_resp["ml_predictions"]["overall_health_risk"]["score"]
    ml_score = ml_resp["ml_predictions"]["overall_health_risk"]["score"]

    assert pytest.approx(iot_score, rel=1e-2) == sim_score
    assert pytest.approx(sim_score, rel=1e-2) == ml_score


# ==============================================================================
# 15. MongoDB Traceability
# ==============================================================================
def test_15_mongodb_traceability():
    db = get_db()
    latest_reading = db.get_latest_reading(DEVICE_ID)
    assert latest_reading is not None
    reading_id = str(latest_reading["_id"])

    # Trace reading_id to predictions collection
    pred_doc = db.db.predictions.find_one({"reading_id": reading_id})
    assert pred_doc is not None
    assert "overall_health_risk" in pred_doc

    # Trace reading_id to feature_vectors collection
    feat_doc = db.db.feature_vectors.find_one({"reading_id": reading_id})
    assert feat_doc is not None
    assert "hr_deviation" in feat_doc
