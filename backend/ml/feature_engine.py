"""
AAROGYA-SHIELD: Feature Engineering Engine
Extracts instantaneous, rolling statistics, rate-of-change, motion derivatives,
heat indices, and personal baseline deviations for edge-AI inference.
"""

import math
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from collections import deque
from backend.core.baseline_engine import get_device_baseline

ACTIVITY_NAMES = {
    0: "REST",
    1: "LIGHT",
    2: "MODERATE",
    3: "HIGH",
    4: "FALL_CANDIDATE",
}

class DeviceFeatureBuffer:
    def __init__(self, device_id: str, maxlen: int = 60):
        self.device_id = device_id
        self.maxlen = maxlen
        self.history = deque(maxlen=maxlen)
        self.recent_spike_countdown = 0
        self.spike_orientation = None

    def add(self, reading: Dict[str, Any]):
        self.history.append(reading)

    def get_rolling_stats(self, key: str, window: int = 10) -> Dict[str, float]:
        if not self.history:
            return {"mean": 0.0, "std": 0.0, "roc": 0.0}
        recent = [float(r.get(key, 0.0)) for r in list(self.history)[-window:]]
        mean_val = float(np.mean(recent))
        std_val = float(np.std(recent))
        # Rate of change: delta between current and oldest in window per sample
        roc = float(recent[-1] - recent[0]) / max(len(recent), 1)
        return {
            "mean": round(mean_val, 2),
            "std": round(std_val, 3),
            "roc": round(roc, 3),
        }

    def evaluate_fall_sequence(self, ax: float, ay: float, az: float, mag: float) -> bool:
        """
        Deterministic Fall Detection Layer:
        ADXL345 acceleration vectors:
        Sudden acceleration spike (>2.4g)
        + orientation/motion change
        + subsequent inactivity (<1.15g, low variance)
        = FALL CANDIDATE
        """
        # 1. Detect sudden acceleration spike
        horizontal_component = math.sqrt(ax**2 + ay**2)
        if mag > 2.4 or (horizontal_component > 2.0 and abs(az) < 0.4):
            self.recent_spike_countdown = 4  # Track for next 4 samples
            self.spike_orientation = (ax, ay, az)
            return True

        # 2. Check if we are in post-spike window with subsequent inactivity and tilt
        if self.recent_spike_countdown > 0:
            self.recent_spike_countdown -= 1
            # Inactivity condition: magnitude returns close to 1g (or below) with low movement
            if mag < 1.25:
                # Orientation check: if device is lying tilted (horizontal tilt > 0.4g or az < 0.8g)
                if horizontal_component > 0.4 or abs(az) < 0.8:
                    return True

        return False

_buffers: Dict[str, DeviceFeatureBuffer] = {}

def get_device_buffer(device_id: str) -> DeviceFeatureBuffer:
    if device_id not in _buffers:
        _buffers[device_id] = DeviceFeatureBuffer(device_id)
    return _buffers[device_id]


def calculate_heat_index(temp_c: float, humidity: float) -> float:
    """Computes Heat Index approximation in Celsius."""
    # Simplified Rothfusz equation
    hi = (
        -8.78469475556
        + 1.61139411 * temp_c
        + 2.33854883889 * humidity
        - 0.14611605 * temp_c * humidity
        - 0.012308094 * (temp_c ** 2)
        - 0.0164248277778 * (humidity ** 2)
        + 0.002211732 * (temp_c ** 2) * humidity
        + 0.00072546 * temp_c * (humidity ** 2)
        - 0.000003582 * (temp_c ** 2) * (humidity ** 2)
    )
    return round(float(hi), 2)


def classify_activity(
    accel_x: float,
    accel_y: float,
    accel_z: float,
    buffer: Optional[DeviceFeatureBuffer] = None,
) -> Tuple[int, str]:
    """
    Derives activity state from ADXL345 acceleration vectors:
    REST / LIGHT / MODERATE / HIGH / FALL_CANDIDATE
    """
    mag = math.sqrt(accel_x**2 + accel_y**2 + accel_z**2)

    # 1. Deterministic Fall Candidate Layer
    if buffer and buffer.evaluate_fall_sequence(accel_x, accel_y, accel_z, mag):
        return 4, "FALL_CANDIDATE"

    # Standalone instantaneous high impact fallback
    horizontal_component = math.sqrt(accel_x**2 + accel_y**2)
    if mag > 2.6 or (horizontal_component > 2.2 and abs(accel_z) < 0.4):
        return 4, "FALL_CANDIDATE"

    # 2. Activity thresholds based on standard actigraphy (SVM)
    if mag > 1.65:
        return 3, "HIGH"
    elif mag > 1.25:
        return 2, "MODERATE"
    elif mag > 1.06:
        return 1, "LIGHT"
    else:
        return 0, "REST"


def process_features(raw_reading: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms raw sensor inputs into a complete feature vector
    incorporating personal baseline deviations and rolling dynamics.
    """
    device_id = raw_reading.get("device_id", "ESP32-001")
    buffer = get_device_buffer(device_id)
    baseline = get_device_baseline(device_id)

    # Extract instantaneous values
    hr = float(raw_reading.get("heart_rate", 75.0))
    spo2 = float(raw_reading.get("spo2", 98.0))
    ppg_quality = float(raw_reading.get("ppg_quality", 0.95))
    body_temp = float(raw_reading.get("body_temperature", 36.8))
    amb_temp = float(raw_reading.get("ambient_temperature", 28.0))
    humidity = float(raw_reading.get("humidity", 60.0))
    ax = float(raw_reading.get("accel_x", 0.02))
    ay = float(raw_reading.get("accel_y", 0.01))
    az = float(raw_reading.get("accel_z", 0.98))
    mq45 = float(raw_reading.get("mq45", 210.0))
    lat = float(raw_reading.get("latitude", 10.662))
    lon = float(raw_reading.get("longitude", 76.891))

    # Derived physics features
    acceleration_magnitude = round(math.sqrt(ax**2 + ay**2 + az**2), 3)
    act_state_code, act_state_label = classify_activity(ax, ay, az, buffer=buffer)
    heat_index = calculate_heat_index(amb_temp, humidity)

    # Personal baseline deviations
    deviations = baseline.compute_deviations({
        "heart_rate": hr,
        "spo2": spo2,
        "body_temperature": body_temp,
        "ambient_temperature": amb_temp,
        "humidity": humidity,
        "mq45": mq45,
        "activity_state": act_state_code,
    })

    # Rolling window stats
    buffer.add(raw_reading)
    hr_rolling = buffer.get_rolling_stats("heart_rate", 10)
    spo2_rolling = buffer.get_rolling_stats("spo2", 10)
    temp_rolling = buffer.get_rolling_stats("body_temperature", 10)

    # Relative deviations
    hr_dev = deviations["heart_rate"]["relative_deviation"]
    spo2_dev = deviations["spo2"]["relative_deviation"]
    temp_dev = deviations["body_temperature"]["difference"]

    feature_dict = {
        "device_id": device_id,
        "timestamp": raw_reading.get("timestamp"),
        "heart_rate": hr,
        "spo2": spo2,
        "ppg_quality": ppg_quality,
        "signal_quality": ppg_quality,
        "body_temperature": body_temp,
        "ambient_temperature": amb_temp,
        "humidity": humidity,
        "heat_index": heat_index,
        "accel_x": ax,
        "accel_y": ay,
        "accel_z": az,
        "acceleration_magnitude": acceleration_magnitude,
        "accel_mag": acceleration_magnitude,
        "mq45": mq45,
        "latitude": lat,
        "longitude": lon,
        "activity_state": act_state_code,
        "activity_level": act_state_label,
        "activity_label": act_state_label,
        "is_fall_candidate": act_state_code == 4,
        "fall_candidate": act_state_code == 4,
        "hr_deviation": hr_dev,
        "spo2_deviation": spo2_dev,
        "temp_deviation": temp_dev,
        "hr_z_score": deviations["heart_rate"]["z_score"],
        "spo2_z_score": deviations["spo2"]["z_score"],
        "temp_z_score": deviations["body_temperature"]["z_score"],
        "mq45_z_score": deviations["mq45"]["z_score"],
        "hr_trend": hr_rolling["roc"],
        "spo2_trend": spo2_rolling["roc"],
        "temperature_trend": temp_rolling["roc"],
        "hr_roc": hr_rolling["roc"],
        "spo2_roc": spo2_rolling["roc"],
        "temp_roc": temp_rolling["roc"],
        "baseline_deviation": deviations,
        "baseline_summary": deviations,
    }

    return feature_dict

