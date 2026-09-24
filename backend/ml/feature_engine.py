"""
VITALSYNC: Multimodal Feature Engineering Engine
Fuses sensor quality validation, NTC thermistor calibration, activity actigraphy,
GPS & external weather context, personal baseline deviations, and Tiny TCN temporal embeddings.
"""

import math
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from collections import deque

from backend.core.sensor_quality import get_sensor_quality_engine
from backend.core.ntc_thermistor import get_ntc_engine
from backend.core.activity_engine import get_activity_engine
from backend.core.weather_service import get_weather_engine
from backend.core.baseline_engine import get_device_baseline
from backend.ml.tiny_tcn import get_tiny_tcn_engine

class DeviceTemporalHistory:
    def __init__(self, device_id: str, maxlen: int = 30):
        self.device_id = device_id
        self.history = deque(maxlen=maxlen)
        self.tcn_sequence = deque(maxlen=10)

    def add(self, reading: Dict[str, Any], features: Dict[str, Any]):
        self.history.append({
            "raw": reading,
            "features": features,
        })
        # Sequence row for Tiny TCN: [HR, SpO2, BodyTemp, AccelMag, MQ45, HR_deviation]
        row = [
            float(reading.get("heart_rate", 72.0)) / 100.0,
            float(reading.get("spo2", 98.0)) / 100.0,
            float(reading.get("body_temperature", 36.7)) / 40.0,
            float(features.get("accel_mag", 1.0)),
            float(reading.get("mq45", 180.0)) / 500.0,
            float(features.get("hr_deviation", 0.0)),
        ]
        self.tcn_sequence.append(row)

    def get_rolling_stats(self, key: str, window: int = 10) -> Dict[str, float]:
        if not self.history:
            return {"mean": 0.0, "std": 0.0, "roc": 0.0}
        recent = [float(h["raw"].get(key, 0.0)) for h in list(self.history)[-window:]]
        mean_val = float(np.mean(recent))
        std_val = float(np.std(recent))
        roc = float(recent[-1] - recent[0]) / max(len(recent), 1)
        return {
            "mean": round(mean_val, 2),
            "std": round(std_val, 3),
            "roc": round(roc, 3),
        }

_device_histories: Dict[str, DeviceTemporalHistory] = {}

def get_device_history(device_id: str) -> DeviceTemporalHistory:
    if device_id not in _device_histories:
        _device_histories[device_id] = DeviceTemporalHistory(device_id)
    return _device_histories[device_id]

def process_features(raw_reading: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms raw incoming telemetry into an integrated contextual feature vector.
    """
    device_id = raw_reading.get("device_id", "ESP32-001")
    history = get_device_history(device_id)
    baseline = get_device_baseline(device_id)
    quality_engine = get_sensor_quality_engine()
    ntc_engine = get_ntc_engine()
    act_engine = get_activity_engine()
    weather_engine = get_weather_engine()
    tcn_engine = get_tiny_tcn_engine()

    # 1. Extract raw inputs
    hr = float(raw_reading.get("heart_rate", 75.0))
    spo2 = float(raw_reading.get("spo2", 98.0))
    ppg_q = float(raw_reading.get("ppg_quality", 0.95))
    body_temp = float(raw_reading.get("body_temperature", 36.8))
    amb_temp = float(raw_reading.get("ambient_temperature", 28.0))
    humidity = float(raw_reading.get("humidity", 60.0))
    ax = float(raw_reading.get("accel_x", 0.02)) if raw_reading.get("accel_x") is not None else None
    ay = float(raw_reading.get("accel_y", 0.01)) if raw_reading.get("accel_y") is not None else None
    az = float(raw_reading.get("accel_z", 0.98)) if raw_reading.get("accel_z") is not None else None
    mq45 = float(raw_reading.get("mq45", 180.0))
    lat = raw_reading.get("latitude")
    lon = raw_reading.get("longitude")

    # 2. Sensor Quality Assessment
    temp_rolling = history.get_rolling_stats("body_temperature", 5)
    quality_eval = quality_engine.evaluate_all(raw_reading, temp_roc=temp_rolling["roc"])
    sensor_qualities = quality_eval["qualities"]
    adxl_available = quality_eval["adxl_available"]

    # 3. NTC Thermistor & Contact Disturbance Evaluation
    base_temp = baseline.stats["body_temperature"]["mean"]
    thermal_eval = ntc_engine.evaluate_thermal_reading(
        device_id=device_id,
        current_temp=body_temp,
        ambient_temp=amb_temp,
        heart_rate=hr,
        baseline_temp=base_temp,
    )

    # 4. Motion & Activity Actigraphy
    motion_eval = act_engine.process_motion(
        device_id=device_id,
        ax=ax,
        ay=ay,
        az=az,
        sensor_valid=adxl_available,
    )
    exp_label = raw_reading.get("activity_label")
    exp_state = raw_reading.get("activity_state")
    if exp_label:
        motion_eval["activity_state"] = exp_label
        motion_eval["is_active"] = exp_label in ("WALKING", "RUNNING", "RUNNING_HIGH_ACTIVITY", "EXERCISE", "ACTIVE")
        motion_eval["is_rest"] = exp_label in ("REST", "SITTING")
    elif exp_state is not None:
        try:
            s_int = int(exp_state)
            motion_eval["activity_code"] = s_int
            motion_eval["is_active"] = s_int in (3, 4)
            motion_eval["is_rest"] = s_int in (0, 1)
        except Exception:
            pass

    # 5. External Weather Context (Offline-first)
    weather_context = weather_engine.get_context(lat, lon)

    # 6. Personal Baseline Deviations
    deviations = baseline.compute_deviations({
        "heart_rate": hr,
        "spo2": spo2,
        "body_temperature": body_temp,
        "ambient_temperature": amb_temp,
        "humidity": humidity,
        "mq45": mq45,
        "activity_state": motion_eval["activity_code"],
    })

    # Rolling window dynamics
    hr_rolling = history.get_rolling_stats("heart_rate", 10)
    spo2_rolling = history.get_rolling_stats("spo2", 10)

    # Relative deviations
    hr_dev = deviations["heart_rate"]["relative_deviation"]
    spo2_dev = deviations["spo2"]["relative_deviation"]
    temp_dev = deviations["body_temperature"]["difference"]

    # Heat index calculation
    heat_index = amb_temp + 0.1 * humidity

    feature_dict = {
        "device_id": device_id,
        "timestamp": raw_reading.get("timestamp"),
        # Core Physiological
        "heart_rate": hr,
        "spo2": spo2,
        "ppg_quality": ppg_q,
        "signal_quality": ppg_q,
        "body_temperature": body_temp,
        "skin_contact_temperature": thermal_eval["skin_contact_temp"],
        "estimated_core_temperature": thermal_eval["estimated_core_temp"],
        "is_transient_thermal": thermal_eval["is_transient_disturbance"],
        "thermal_message": thermal_eval["message"],
        # Environmental
        "ambient_temperature": amb_temp,
        "humidity": humidity,
        "heat_index": round(heat_index, 2),
        "mq45": mq45,
        "latitude": lat,
        "longitude": lon,
        "weather_context": weather_context,
        # Motion Dynamics
        "accel_x": ax,
        "accel_y": ay,
        "accel_z": az,
        "acceleration_magnitude": motion_eval["magnitude"],
        "accel_mag": motion_eval["magnitude"],
        "jerk": motion_eval["jerk"],
        "motion_variance": motion_eval["variance"],
        "activity_state": motion_eval["activity_code"],
        "activity_level": motion_eval["activity_state"],
        "activity_label": motion_eval["activity_state"],
        "activity_intensity": motion_eval["intensity"],
        "is_fall_candidate": motion_eval["activity_code"] == 6 or motion_eval.get("fall_candidate", False),
        "fall_candidate": motion_eval["activity_code"] == 6 or motion_eval.get("fall_candidate", False),
        "is_active": motion_eval["is_active"],
        "is_rest": motion_eval["is_rest"],
        # Personal Baseline Deviations
        "hr_deviation": hr_dev,
        "spo2_deviation": spo2_dev,
        "temp_deviation": temp_dev,
        "hr_z_score": deviations["heart_rate"]["z_score"],
        "spo2_z_score": deviations["spo2"]["z_score"],
        "temp_z_score": deviations["body_temperature"]["z_score"],
        "duration_hr_outside_sec": deviations["heart_rate"]["duration_outside_sec"],
        "duration_spo2_outside_sec": deviations["spo2"]["duration_outside_sec"],
        "hr_trend": hr_rolling["roc"],
        "spo2_trend": spo2_rolling["roc"],
        "temp_trend": temp_rolling["roc"],
        "baseline_summary": deviations,
        # Sensor Health & Qualities
        "sensor_qualities": sensor_qualities,
        "overall_sensor_confidence": quality_eval["overall_sensor_confidence"],
        "adxl_available": adxl_available,
        "ppg_available": quality_eval["ppg_available"],
        "ntc_available": quality_eval["ntc_available"],
    }

    # 7. Update Temporal Sequence and compute Tiny TCN embedding
    history.add(raw_reading, feature_dict)
    tcn_seq = list(history.tcn_sequence)
    tcn_embedding = tcn_engine.extract_temporal_embedding(tcn_seq)
    feature_dict["tcn_embedding"] = [round(float(v), 4) for v in tcn_embedding]

    return feature_dict
