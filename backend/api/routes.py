"""
AAROGYA-SHIELD: FastAPI REST & Streaming Routes
Implements all required API endpoints.
Enforces that both ESP32 IoT and Simulator modes execute the exact same
feature processing, baseline calculation, ML inference, and alert engines.
"""

import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks

from backend.api.schemas import (
    SensorReadingSchema,
    DeviceRegisterSchema,
    BaselineStartSchema,
    AlertCreateSchema,
)
from backend.ml.feature_engine import process_features
from backend.ml.model_registry import get_model_registry
from backend.core.baseline_engine import get_device_baseline
from backend.core.early_warning_engine import get_early_warning_state
from backend.core.alert_engine import get_alert_engine
from backend.db.database import get_db
from backend.api.websocket_manager import ws_manager

router = APIRouter(prefix="/api")

_last_iot_timestamps: Dict[str, datetime.datetime] = {}
_packet_counts: Dict[str, int] = {}
_last_readings: Dict[str, Dict[str, Any]] = {}

def get_iot_device_status(device_id: str = "ESP32-001") -> str:
    last_ts = _last_iot_timestamps.get(device_id)
    if not last_ts:
        return "OFFLINE / NO RECENT DATA"
    elapsed = (datetime.datetime.utcnow() - last_ts).total_seconds()
    if elapsed > 5.0:
        return "OFFLINE / NO RECENT DATA"
    return "ONLINE"

async def _execute_unified_pipeline(reading_dict: Dict[str, Any], origin: str = "IOT") -> Dict[str, Any]:
    """
    THE CORE UNIFIED EDGE-AI PIPELINE.
    Every reading (whether from ESP32, Simulator, or direct REST) passes through this exact logic.
    Zero frontend-only calculations; 100% backend ML, baseline, and alert inference.
    """
    db = get_db()
    model_registry = get_model_registry()
    device_id = reading_dict.get("device_id", "ESP32-001")

    # Record packet counts & last readings
    _packet_counts[device_id] = _packet_counts.get(device_id, 0) + 1
    _last_readings[device_id] = dict(reading_dict)

    # Record IoT device liveness if packet originated from real IoT device
    if origin == "IOT" and not reading_dict.get("is_simulator"):
        _last_iot_timestamps[device_id] = datetime.datetime.utcnow()
    
    if "timestamp" not in reading_dict or not reading_dict["timestamp"]:
        reading_dict["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"

    # 1. Store raw sensor reading
    reading_id = db.insert_sensor_reading(reading_dict)

    # 2. Extract features & personal baseline deviations
    features = process_features(reading_dict)
    db.insert_feature_vector(reading_id, features)

    # 3. Dynamic baseline update (if reading is nominal, continually refine rolling baseline)
    baseline = get_device_baseline(device_id)
    baseline.update_with_reading(reading_dict)
    db.save_baseline(baseline.to_dict())

    # 4. ML Model Suite Inference (7 risk outputs)
    ml_preds = model_registry.predict_all(features)
    db.insert_prediction(reading_id, ml_preds)

    # 5. Early-Warning & Trend Persistence Escalation
    ew_state = get_early_warning_state(device_id)
    escalated_eval = ew_state.evaluate(ml_preds, features)
    
    risk_event = {
        "device_id": device_id,
        "timestamp": reading_dict["timestamp"],
        "overall_score": ml_preds["overall_health_risk"]["score"],
        "raw_level": escalated_eval["raw_level"],
        "escalated_level": escalated_eval["escalated_level"],
        "persistence_count": escalated_eval["persistence_count"],
        "reasons": escalated_eval["reasons"],
        "ml_outputs": ml_preds,
    }
    db.insert_risk_event(reading_id, risk_event)

    # 6. Caretaker Alert Engine
    alert_engine = get_alert_engine()
    created_alert = alert_engine.check_and_create_alert(
        device_id=device_id,
        escalated_eval=escalated_eval,
        ml_predictions=ml_preds,
        features=features,
    )
    if created_alert:
        db.save_alert(created_alert)

    # 7. Construct complete unified live payload
    payload = {
        "event_type": "TELEMETRY_UPDATE",
        "origin": origin,
        "reading_id": reading_id,
        "device_id": device_id,
        "device_status": get_iot_device_status(device_id),
        "packets_received": _packet_counts.get(device_id, 0),
        "timestamp": reading_dict["timestamp"],
        "raw_sensors": reading_dict,
        "features": features,
        "ml_predictions": ml_preds,
        "escalation": escalated_eval,
        "timeline": escalated_eval.get("timeline", []),
        "baseline_summary": features.get("baseline_summary", {}),
        "active_alert": alert_engine.get_latest_alert(),
    }

    # 8. Broadcast over WebSocket to all active dashboard clients
    await ws_manager.broadcast(payload)

    return payload


# --- Sensor Telemetry Endpoints ---

@router.post("/sensors/readings")
async def ingest_iot_reading(reading: SensorReadingSchema):
    """IoT Live Mode endpoint: ESP32 sends real sensor readings here."""
    data = reading.model_dump()
    data["is_simulator"] = False
    result = await _execute_unified_pipeline(data, origin="IOT")
    return result

@router.get("/sensors/latest")
def get_latest_sensor_reading(device_id: str = "ESP32-001"):
    """Returns the most recent sensor reading."""
    db = get_db()
    doc = db.get_latest_reading(device_id)
    if not doc:
        # Return sensible default if empty
        return {
            "device_id": device_id,
            "heart_rate": 75,
            "spo2": 98,
            "ppg_quality": 0.95,
            "body_temperature": 36.8,
            "ambient_temperature": 28.0,
            "humidity": 60,
            "accel_x": 0.02,
            "accel_y": 0.01,
            "accel_z": 0.98,
            "mq45": 180,
            "latitude": 10.662,
            "longitude": 76.891,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }
    return doc


# --- Simulator Endpoint ---

@router.post("/simulator/readings")
async def ingest_simulator_reading(reading: SensorReadingSchema):
    """
    Simulator Mode endpoint: Manually adjusted values from browser.
    Runs through the EXACT same ML, baseline, and alert pipeline as ESP32!
    """
    data = reading.model_dump()
    data["is_simulator"] = True
    result = await _execute_unified_pipeline(data, origin="SIMULATOR")
    return result


# --- Unified ML Prediction Endpoint ---

@router.post("/ml/predict")
async def predict_ml(reading: SensorReadingSchema):
    """Direct ML prediction endpoint using identical feature and model pipeline."""
    data = reading.model_dump()
    result = await _execute_unified_pipeline(data, origin="ML_PREDICT")
    return result

@router.get("/ml/latest")
def get_latest_ml_prediction(device_id: str = "ESP32-001"):
    """Returns the latest ML prediction."""
    db = get_db()
    pred = db.get_latest_prediction(device_id)
    if not pred:
        # Compute on default if empty
        features = process_features({"device_id": device_id, "heart_rate": 75, "spo2": 98, "body_temperature": 36.8, "ambient_temperature": 28, "humidity": 60, "mq45": 180})
        return get_model_registry().predict_all(features)
    return pred


# --- Risk State Endpoints ---

@router.get("/risk/current")
def get_current_risk(device_id: str = "ESP32-001"):
    """Returns the current risk state, escalated level, device status, timeline, and explanations."""
    ew_state = get_early_warning_state(device_id)
    alert_engine = get_alert_engine()
    db = get_db()
    latest_pred = db.get_latest_prediction(device_id) or {}
    
    return {
        "device_id": device_id,
        "device_status": get_iot_device_status(device_id),
        "packets_received": _packet_counts.get(device_id, 0),
        "current_escalated_level": ew_state.current_escalated_level,
        "persistence_count": ew_state.consecutive_abnormal_count,
        "active_alert": alert_engine.get_latest_alert(),
        "latest_prediction": latest_pred,
        "timeline": ew_state.get_timeline(15),
        "medical_disclaimer": "This prototype provides health-risk and anomaly indicators and is not a medical diagnostic device.",
        "framing": "This prototype provides health-risk and anomaly indicators and is not a medical diagnostic device."
    }

@router.get("/risk/timeline")
def get_risk_timeline(device_id: str = "ESP32-001", limit: int = 30):
    """Returns early-warning progression timeline events."""
    ew_state = get_early_warning_state(device_id)
    return ew_state.get_timeline(limit=limit)

@router.get("/risk/history")
def get_risk_history(limit: int = 50):
    """Returns historical risk events."""
    db = get_db()
    return db.get_risk_history(limit=limit)


# --- Personal Baseline Endpoints ---

@router.post("/baseline/start")
def start_baseline_calibration(body: BaselineStartSchema):
    """Starts a new baseline calibration window for a device."""
    baseline = get_device_baseline(body.device_id)
    baseline.start_calibration()
    get_db().save_baseline(baseline.to_dict())
    return {"message": "Calibration started", "baseline": baseline.to_dict()}

@router.post("/baseline/update")
def update_baseline(reading: SensorReadingSchema):
    """Manually updates the baseline with a specific reading."""
    baseline = get_device_baseline(reading.device_id)
    baseline.update_with_reading(reading.model_dump())
    get_db().save_baseline(baseline.to_dict())
    return {"message": "Baseline updated", "baseline": baseline.to_dict()}

@router.get("/baseline")
def get_baseline(device_id: str = "ESP32-001"):
    """Returns baseline statistics, MAD, medians, and current deviations."""
    baseline = get_device_baseline(device_id)
    return baseline.to_dict()


# --- Caretaker Alert Endpoints ---

@router.post("/alerts")
def create_manual_alert(alert_req: AlertCreateSchema):
    """Manually triggers a caretaker alert."""
    alert_engine = get_alert_engine()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    alert = {
        "alert_id": f"ALT-MANUAL-{datetime.datetime.utcnow().strftime('%H%M%S')}",
        "device_id": alert_req.device_id,
        "patient_id": f"PATIENT-{alert_req.device_id}",
        "timestamp": now,
        "risk_type": alert_req.risk_type,
        "risk_level": alert_req.risk_level,
        "message": alert_req.message,
        "contributing_parameters": alert_req.contributing_parameters,
        "latitude": alert_req.latitude,
        "longitude": alert_req.longitude,
        "acknowledged": False,
        "acknowledged_at": None,
    }
    alert_engine.active_alert = alert
    alert_engine.alerts_history.insert(0, alert)
    get_db().save_alert(alert)
    return alert

@router.get("/alerts")
def get_alerts(limit: int = 50):
    """Retrieves caretaker alert history."""
    alert_engine = get_alert_engine()
    return alert_engine.get_all_alerts(limit=limit)

@router.get("/alerts/latest")
def get_latest_alert():
    """Retrieves the most recent active caretaker alert."""
    alert_engine = get_alert_engine()
    alert = alert_engine.get_latest_alert()
    if not alert:
        db = get_db()
        alert = db.get_latest_alert()
    return alert or {"message": "No active alerts"}

@router.post("/alerts/{id}/acknowledge")
async def acknowledge_alert(id: str):
    """Acknowledges an active caretaker alert."""
    alert_engine = get_alert_engine()
    db = get_db()
    acked = alert_engine.acknowledge_alert(id)
    db.acknowledge_alert(id)
    if not acked:
        raise HTTPException(status_code=404, detail="Alert ID not found")

    # Broadcast updated alert state over WebSocket
    await ws_manager.broadcast({
        "event_type": "ALERT_ACKNOWLEDGED",
        "alert_id": id,
        "acknowledged_at": acked.get("acknowledged_at"),
    })
    return acked


# --- Device Management & System Health ---

@router.post("/device/register")
def register_device(device_req: DeviceRegisterSchema):
    """Registers edge device and patient metadata."""
    db = get_db()
    res = db.register_device(device_req.device_id, device_req.model_dump())
    return {"status": "registered", "device": res}

@router.get("/device/status")
def get_device_status(device_id: str = "ESP32-001"):
    """Returns IoT device connection status, packet count, and individual sensor liveness."""
    last_ts = _last_iot_timestamps.get(device_id)
    status = get_iot_device_status(device_id)
    last_reading = _last_readings.get(device_id, {})
    return {
        "device_id": device_id,
        "device_status": status,
        "is_online": status == "ONLINE",
        "last_iot_timestamp": last_ts.isoformat() + "Z" if last_ts else None,
        "packets_received": _packet_counts.get(device_id, 0),
        "processing_node": "Raspberry Pi 4 / Edge Node",
        "server_status": "ONLINE",
        "sensors": {
            "max30102": "DATA" if last_reading.get("heart_rate") else "NO DATA",
            "adxl345": "DATA" if "accel_z" in last_reading else "NO DATA",
            "body_temp": "DATA" if last_reading.get("body_temperature") else "NO DATA",
            "ambient_temp": "DATA" if "ambient_temperature" in last_reading else "NO DATA",
            "humidity": "DATA" if "humidity" in last_reading else "NO DATA",
            "mq45": "DATA" if "mq45" in last_reading else "NO DATA",
            "gps": "FIX" if last_reading.get("latitude") and last_reading.get("longitude") else "NO FIX",
        },
        "last_reading": last_reading
    }

@router.get("/health")
def system_health():
    """Returns edge system health, ML model versions, and connection states."""
    model_registry = get_model_registry()
    db = get_db()
    return {
        "status": "ONLINE",
        "system": "VITALSYNC Edge-AI",
        "project": "VITALSYNC",
        "processing_node": "Raspberry Pi 4 / Edge Node",
        "device_status": get_iot_device_status("ESP32-001"),
        "models_loaded": model_registry.loaded,
        "model_version": model_registry.version_info.get("version", "1.0.0-edge"),
        "database_connected": True,
        "database_type": "MongoDB Live" if not db.is_mock else "Mongomock In-Memory",
        "websocket_active_clients": len(ws_manager.active_connections),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "medical_disclaimer": "This prototype provides health-risk and anomaly indicators and is not a medical diagnostic device."
    }
