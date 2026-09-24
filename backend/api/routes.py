"""
VITALSYNC: FastAPI REST & Streaming Routes
Executes the unified edge-AI inference pipeline across 8 decoupled risk domains.
Enforces symmetric execution between real ESP32 sensors and browser simulator.
"""

import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks

from backend.api.schemas import (
    SensorReadingSchema,
    DeviceRegisterSchema,
    BaselineStartSchema,
    AlertCreateSchema,
    HealthProfileSchema,
)
from backend.ml.feature_engine import process_features
from backend.ml.model_registry import get_model_registry
from backend.core.baseline_engine import get_device_baseline
from backend.core.early_warning_engine import get_early_warning_state
from backend.core.alert_engine import get_alert_engine
from backend.core.weather_service import get_weather_engine
from backend.core.communication_manager import get_communication_manager
from backend.core.risk_fusion import get_risk_fusion_engine
from backend.core.spike_detector import get_spike_detector
from backend.core.patient_profile import get_patient_profile_manager, AVAILABLE_CONDITIONS
from backend.core.threshold_engine import get_threshold_engine
from backend.db.database import get_db
from backend.api.websocket_manager import ws_manager

router = APIRouter(prefix="/api")

_last_iot_timestamps: Dict[str, datetime.datetime] = {}
_packet_counts: Dict[str, int] = {}
_last_readings: Dict[str, Dict[str, Any]] = {}
_last_fused_risk: Dict[str, Dict[str, Any]] = {}
_global_sequence_id: int = 1000

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
    Every reading passes through this exact logic:
    Raw -> Sensor Quality -> Features -> Baseline Deviations -> Tiny TCN -> 8-Domain ML -> Spike Detector -> State Machine -> Alerts -> WS.
    """
    global _global_sequence_id
    _global_sequence_id += 1
    current_seq_id = _global_sequence_id

    db = get_db()
    model_registry = get_model_registry()
    device_id = reading_dict.get("device_id", "ESP32-001")

    _packet_counts[device_id] = _packet_counts.get(device_id, 0) + 1
    _last_readings[device_id] = dict(reading_dict)

    if origin == "IOT" and not reading_dict.get("is_simulator"):
        _last_iot_timestamps[device_id] = datetime.datetime.utcnow()

    if "timestamp" not in reading_dict or not reading_dict["timestamp"]:
        reading_dict["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"

    # 1. Store raw sensor reading
    reading_id = db.insert_sensor_reading(reading_dict)

    # 2. Extract features, sensor quality, actigraphy, and temporal embeddings
    features = process_features(reading_dict)
    db.insert_feature_vector(reading_id, features)

    # 3. Dynamic baseline reference
    baseline = get_device_baseline(device_id)

    # 4. Multi-modal ML inference across 8 decoupled domains
    ml_preds = model_registry.predict_all(features)
    db.insert_prediction(reading_id, ml_preds)

    # 5. Dedicated Spike & Recovery Detector (e.g. HR 80 -> 198, temp jump, recovery)
    spike_detector = get_spike_detector()
    spike_eval = spike_detector.evaluate(
        device_id=device_id,
        vitals={
            "heart_rate": features.get("heart_rate", 75.0),
            "spo2": features.get("spo2", 98.0),
            "body_temperature": features.get("body_temperature", 36.7),
        },
        baseline=baseline.to_dict().get("statistics", {}),
        signal_qualities=features.get("sensor_qualities", {}),
        activity=features.get("activity_level", "REST"),
    )

    # 6. Early-Warning & Alert State Machine with Hysteresis
    ew_state = get_early_warning_state(device_id)
    escalated_eval = ew_state.evaluate(ml_preds, features)

    # Section 14: Safe Baseline Learning (Rejects abnormal events & degraded sensor quality)
    baseline.update_with_reading(
        reading_dict,
        nominal_only=True,
        risk_level=escalated_eval["escalated_level"],
        sensor_quality=features.get("overall_sensor_confidence", 0.95),
    )
    db.save_baseline(baseline.to_dict())

    # 7. Dynamic 3-Level Threshold & Sensitivity Engine (Personalized Profile Context)
    threshold_engine = get_threshold_engine()
    threshold_eval = threshold_engine.evaluate_vitals(
        vitals={
            "heart_rate": features.get("heart_rate", 75.0),
            "spo2": features.get("spo2", 98.0),
            "body_temperature": features.get("body_temperature", 36.7),
            "ambient_temperature": features.get("ambient_temperature", 28.0),
            "mq45": features.get("mq45", 180.0),
        },
        baseline_stats=baseline.to_dict().get("statistics", {}),
        ml_predictions=ml_preds,
        sensor_qualities={
            **features.get("sensor_qualities", {}),
            "ppg_quality": features.get("ppg_quality", 0.95),
        },
        activity_context={
            "state": features.get("activity_level", "REST"),
            "intensity": features.get("acceleration_magnitude", 0.98),
        },
        device_id=device_id,
    )

    # Prepend any newly generated spike / recovery events to the timeline
    if spike_eval.get("events_emitted"):
        for sp_ev in spike_eval["events_emitted"]:
            escalated_eval.setdefault("timeline", []).insert(0, {
                "time": datetime.datetime.utcnow().strftime("%H:%M:%S"),
                "timestamp": sp_ev["timestamp"],
                "from_state": sp_ev.get("previous", "SPIKE"),
                "to_state": sp_ev["status"],
                "domain": sp_ev["domain"],
                "reason": sp_ev["message"],
                "score": 0.50 if sp_ev["type"] == "SPIKE_EVENT" else 0.10,
            })

    risk_event = {
        "device_id": device_id,
        "timestamp": reading_dict["timestamp"],
        "overall_score": ml_preds["overall_health_risk"]["score"],
        "raw_level": escalated_eval["raw_level"],
        "escalated_level": escalated_eval["escalated_level"],
        "state_machine": escalated_eval.get("state_machine", {}),
        "primary_domain": escalated_eval.get("primary_domain"),
        "reasons": escalated_eval["reasons"],
        "ml_outputs": ml_preds,
    }
    db.insert_risk_event(reading_id, risk_event)

    # 7. Caretaker Alert Engine (with SIM800L SMS and auto-clearing)
    alert_engine = get_alert_engine()
    created_alert = alert_engine.check_and_create_alert(
        device_id=device_id,
        escalated_eval=escalated_eval,
        ml_predictions=ml_preds,
        features=features,
    )
    if created_alert:
        db.save_alert(created_alert)

    # 8. Multi-Signal Evidence Fusion & Deterministic Clinical-Context Reasoning
    risk_fusion_engine = get_risk_fusion_engine()
    fused_risk = risk_fusion_engine.fuse(
        features=features,
        ml_predictions=ml_preds,
        escalated_eval=escalated_eval,
        alert_info=alert_engine.get_latest_alert(),
        reading_dict=reading_dict,
    )
    _last_fused_risk[device_id] = fused_risk

    # 9. Construct complete authoritative live payload (Section 3 specification + extended debug)
    payload = {
        # Section 3 Authoritative State Schema:
        "timestamp": reading_dict["timestamp"],
        "sequence_id": current_seq_id,
        "vitals": {
            "heart_rate": round(features.get("heart_rate", 75.0), 1),
            "spo2": round(features.get("spo2", 98.0), 1),
            "temperature": round(features.get("body_temperature", 36.7), 1),
            "ambient_temperature": round(features.get("ambient_temperature", 28.0), 1),
        },
        "activity": {
            "state": features.get("activity_level", "REST"),
            "intensity": round(features.get("acceleration_magnitude", 0.98), 2),
        },
        "environment": {
            "gas_index": round(features.get("mq45", 180.0) / 1000.0, 3),
            "raw_mq45": round(features.get("mq45", 180.0), 1),
        },
        "gps": {
            "lat": round(features.get("latitude", 10.662), 4),
            "lon": round(features.get("longitude", 76.891), 4),
            "valid": True,
        },
        "weather": features.get("weather_context", {}),
        "risk": {
            "overall_score": round(ml_preds["overall_health_risk"]["score"], 3),
            "overall_level": escalated_eval["escalated_level"],
            "primary_domain": escalated_eval.get("primary_domain", "Normal Physiology"),
            "domains": {
                k: {
                    "score": v.get("score", 0.95 if v.get("is_confirmed") else (0.65 if v.get("is_candidate") else 0.05)),
                    "level": v.get("level", "CRITICAL" if v.get("is_confirmed") else ("ELEVATED" if v.get("is_candidate") else "LOW")),
                }
                for k, v in ml_preds.get("risk_domains", {}).items()
            },
        },
        "alert": {
            "active": alert_engine.get_latest_alert() is not None,
            "level": escalated_eval["escalated_level"],
            "state": escalated_eval.get("state_machine", {}).get("current_state", "NORMAL"),
            "reason": escalated_eval.get("reasons", ["All parameters normal"])[0] if escalated_eval.get("reasons") else "All parameters normal",
            "latest": alert_engine.get_latest_alert(),
        },
        "spike": spike_eval,
        "patient_profile": get_patient_profile_manager(device_id).get_profile(),
        "threshold_assessment": threshold_eval,
        "decision_sources": threshold_eval.get("decision_sources", ["NOMINAL_TRACKING"]),
        "active_condition_contexts": threshold_eval.get("active_condition_contexts", []),
        "personalized": True,
        "special_notices": threshold_eval.get("special_notices", []),

        # Extended Engineering & Diagnostic Fields:
        "event_type": "TELEMETRY_UPDATE",
        "origin": origin,
        "reading_id": reading_id,
        "device_id": device_id,
        "device_status": get_iot_device_status(device_id),
        "packets_received": _packet_counts.get(device_id, 0),
        "raw_sensors": reading_dict,
        "features": features,
        "ml_predictions": ml_preds,
        "escalation": escalated_eval,
        "state_machine": escalated_eval.get("state_machine", {}),
        "timeline": escalated_eval.get("timeline", []),
        "baseline_summary": features.get("baseline_summary", {}),
        "active_alert": alert_engine.get_latest_alert(),
        "qualities": features.get("sensor_qualities", {}),
        "root_cause_analysis": fused_risk.get("root_cause", {}),
        "clinical_context": fused_risk.get("clinical_answers", {}),
        "fused_risk": fused_risk,
    }

    # 10. Broadcast over WebSocket to all active dashboard clients
    await ws_manager.broadcast(payload)

    return payload


# --- Sensor Telemetry Endpoints ---

@router.post("/sensors/readings")
async def ingest_iot_reading(reading: SensorReadingSchema):
    """IoT Live Mode endpoint: ESP32 sends real sensor readings here."""
    data = reading.model_dump()
    data["is_simulator"] = False
    return await _execute_unified_pipeline(data, origin="IOT")

@router.post("/simulator/readings")
async def ingest_simulator_reading(reading: SensorReadingSchema):
    """Simulator Mode endpoint: Manually adjusted values from browser or test runner."""
    data = reading.model_dump()
    data["is_simulator"] = True
    return await _execute_unified_pipeline(data, origin="SIMULATOR")

@router.get("/sensors/latest")
def get_latest_sensor_reading(device_id: str = "ESP32-001"):
    db = get_db()
    doc = db.get_latest_reading(device_id)
    if not doc:
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


# --- Unified ML Prediction Endpoint ---

@router.post("/ml/predict")
async def predict_ml(reading: SensorReadingSchema):
    data = reading.model_dump()
    return await _execute_unified_pipeline(data, origin="ML_PREDICT")

@router.get("/ml/latest")
def get_latest_ml_prediction(device_id: str = "ESP32-001"):
    db = get_db()
    pred = db.get_latest_prediction(device_id)
    if not pred:
        features = process_features({"device_id": device_id, "heart_rate": 75, "spo2": 98, "body_temperature": 36.8, "ambient_temperature": 28, "humidity": 60, "mq45": 180})
        return get_model_registry().predict_all(features)
    return pred


# --- Risk & State Machine Endpoints ---

@router.get("/risk/current")
def get_current_risk(device_id: str = "ESP32-001"):
    ew_state = get_early_warning_state(device_id)
    alert_engine = get_alert_engine()
    db = get_db()
    latest_pred = db.get_latest_prediction(device_id) or {}
    
    return {
        "device_id": device_id,
        "device_status": get_iot_device_status(device_id),
        "packets_received": _packet_counts.get(device_id, 0),
        "current_escalated_level": ew_state.sm._states.get(device_id, {}).get("current_state", "NORMAL"),
        "state_machine": ew_state.sm._states.get(device_id, {}),
        "persistence_count": ew_state.consecutive_abnormal_count,
        "active_alert": alert_engine.get_latest_alert(),
        "latest_prediction": latest_pred,
        "timeline": ew_state.sm._states.get(device_id, {}).get("state_timeline", []),
        "medical_disclaimer": "This prototype provides health-risk and anomaly indicators and is not a medical diagnostic device.",
    }


# --- Weather & GPS Context Endpoints ---

@router.get("/weather/current")
def get_weather_current(lat: float = 10.662, lon: float = 76.891):
    """Returns current external weather context based on GPS coordinates."""
    weather_engine = get_weather_engine()
    return weather_engine.get_context(lat, lon)

@router.post("/weather/toggle-offline")
def toggle_weather_offline(offline: bool):
    """Enables or disables offline local sensor mode for weather context."""
    weather_engine = get_weather_engine()
    weather_engine.set_forced_offline(offline)
    return {"forced_offline": offline, "mode": "LOCAL_SENSOR_MODE" if offline else "WEATHER_AUGMENTED"}


# --- Communication & SIM800L Endpoints ---

@router.get("/communication/status")
def get_communication_status():
    comm = get_communication_manager()
    return comm.get_network_status()

@router.post("/communication/toggle-offline")
def toggle_communication_offline(offline: bool):
    comm = get_communication_manager()
    comm.set_module_available(not offline)
    return {"sim800l_available": not offline}


# --- Personal Baseline Endpoints ---

@router.post("/baseline/start")
def start_baseline_calibration(body: BaselineStartSchema):
    baseline = get_device_baseline(body.device_id)
    baseline.start_calibration()
    get_db().save_baseline(baseline.to_dict())
    return {"message": "Calibration started", "baseline": baseline.to_dict()}

@router.get("/baseline")
def get_baseline(device_id: str = "ESP32-001"):
    baseline = get_device_baseline(device_id)
    return baseline.to_dict()


# --- Caretaker Alert Endpoints ---

@router.post("/alerts")
def create_manual_alert(alert_req: AlertCreateSchema):
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
        "status": "ACTIVE",
    }
    alert_engine.active_alert = alert
    alert_engine.alerts_history.insert(0, alert)
    get_db().save_alert(alert)
    return alert

@router.get("/alerts")
def get_alerts(limit: int = 50):
    alert_engine = get_alert_engine()
    return alert_engine.get_all_alerts(limit=limit)

@router.get("/alerts/latest")
def get_latest_alert():
    alert_engine = get_alert_engine()
    alert = alert_engine.get_latest_alert()
    return alert or {"message": "No active alerts"}

@router.post("/alerts/{id}/acknowledge")
async def acknowledge_alert(id: str):
    alert_engine = get_alert_engine()
    db = get_db()
    acked = alert_engine.acknowledge_alert(id)
    db.acknowledge_alert(id)
    if not acked:
        raise HTTPException(status_code=404, detail="Alert ID not found")

    await ws_manager.broadcast({
        "event_type": "ALERT_ACKNOWLEDGED",
        "alert_id": id,
        "acknowledged_at": acked.get("acknowledged_at"),
    })
    return acked


# --- Device Management & System Health ---

@router.post("/device/register")
def register_device(device_req: DeviceRegisterSchema):
    db = get_db()
    res = db.register_device(device_req.device_id, device_req.model_dump())
    return {"status": "registered", "device": res}

@router.get("/device/status")
def get_device_status(device_id: str = "ESP32-001"):
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
        "sensors": {
            "max30102": "DATA" if last_reading.get("heart_rate") else "NO DATA",
            "adxl345": "DATA" if last_reading.get("accel_z") is not None else "NO DATA",
            "ntc_temp": "DATA" if last_reading.get("body_temperature") else "NO DATA",
            "ambient_temp": "DATA" if "ambient_temperature" in last_reading else "NO DATA",
            "humidity": "DATA" if "humidity" in last_reading else "NO DATA",
            "mq45": "DATA" if "mq45" in last_reading else "NO DATA",
            "gps": "FIX" if last_reading.get("latitude") and last_reading.get("longitude") else "NO FIX",
            "sim800l": "READY" if get_communication_manager().sim800l_available else "OFFLINE",
        },
        "last_reading": last_reading
    }

@router.get("/health")
def system_health():
    model_registry = get_model_registry()
    db = get_db()
    return {
        "status": "ONLINE",
        "system": "VITALSYNC Edge-AI",
        "project": "VITALSYNC",
        "processing_node": "Raspberry Pi 4 / Edge Node",
        "device_status": get_iot_device_status("ESP32-001"),
        "models_loaded": model_registry.loaded,
        "model_version": model_registry.version_info.get("version", "2.0.0-contextual"),
        "domains": model_registry.version_info.get("domains", []),
        "database_connected": True,
        "database_type": "MongoDB Live" if not db.is_mock else "Mongomock In-Memory",
        "websocket_active_clients": len(ws_manager.active_connections),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "medical_disclaimer": "This prototype provides health-risk and anomaly indicators and is not a medical diagnostic device."
    }

@router.get("/reasoning/latest")
def get_latest_reasoning(device_id: str = "ESP32-001"):
    """
    Returns the latest Root-Cause Analysis and Clinical-Context Reasoning
    answering the 8 core clinical questions deterministically.
    """
    return _last_fused_risk.get(device_id) or {
        "status": "AWAITING_TELEMETRY",
        "message": "Send a sensor packet or simulator reading to generate root-cause analysis.",
        "domains": {},
        "evidence": [],
        "contradicting_evidence": [],
        "clinical_answers": {},
    }


# --- Patient Health Profile & Clinical Threshold Endpoints ---

@router.get("/profile")
def get_health_profile(device_id: str = "ESP32-001"):
    mgr = get_patient_profile_manager(device_id)
    return {
        "profile": mgr.get_profile(),
        "active_contexts": mgr.get_active_condition_contexts(),
        "available_conditions": AVAILABLE_CONDITIONS,
    }

@router.post("/profile")
async def update_health_profile(profile_req: HealthProfileSchema):
    mgr = get_patient_profile_manager(profile_req.device_id or "ESP32-001")
    data = profile_req.model_dump()
    updated = mgr.set_profile(data)
    
    # Broadcast profile update to connected frontends
    await ws_manager.broadcast({
        "event_type": "PROFILE_UPDATED",
        "profile": updated,
        "active_contexts": mgr.get_active_condition_contexts(),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    })
    return {
        "status": "SUCCESS",
        "profile": updated,
        "active_contexts": mgr.get_active_condition_contexts(),
    }

@router.get("/profile/conditions")
def get_available_conditions():
    return AVAILABLE_CONDITIONS

@router.get("/thresholds")
def get_clinical_thresholds(profile_name: str = "default"):
    engine = get_threshold_engine()
    return engine.get_clinical_references(profile_name)


