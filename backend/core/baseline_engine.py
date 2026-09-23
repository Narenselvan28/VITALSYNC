"""
AAROGYA-SHIELD: Personal Baseline Engine
Computes and tracks personalized physiological baselines for individual users/devices.
Stores mean, median, standard deviation, variance, MAD (Median Absolute Deviation), min, max,
rolling baselines, and computes real-time deviations from individual norms.
Avoids reliance solely on universal fixed thresholds.
"""

import numpy as np
import datetime
from typing import Dict, Any, List, Optional
from collections import deque

class PersonalBaseline:
    def __init__(self, device_id: str = "ESP32-001"):
        self.device_id = device_id
        self.is_calibrating = False
        self.is_calibrated = True  # Seeded with clinical physiological default norms
        self.calibration_start_time: Optional[str] = None
        self.samples_collected = 100

        # Buffer of historical nominal readings for baseline calculation (up to 500 samples)
        self.hr_buffer = deque([72.0 + float(np.random.normal(0, 2)) for _ in range(50)], maxlen=500)
        self.spo2_buffer = deque([98.0 + float(np.random.normal(0, 0.4)) for _ in range(50)], maxlen=500)
        self.body_temp_buffer = deque([36.7 + float(np.random.normal(0, 0.15)) for _ in range(50)], maxlen=500)
        self.ambient_temp_buffer = deque([28.0 + float(np.random.normal(0, 1.0)) for _ in range(50)], maxlen=500)
        self.humidity_buffer = deque([60.0 + float(np.random.normal(0, 2.0)) for _ in range(50)], maxlen=500)
        self.mq45_buffer = deque([180.0 + float(np.random.normal(0, 15.0)) for _ in range(50)], maxlen=500)
        self.activity_buffer = deque([0.0 for _ in range(50)], maxlen=500)

        # Baseline statistics cache
        self.stats: Dict[str, Dict[str, float]] = {}
        self._recompute_stats()

    def start_calibration(self):
        """Starts a clean baseline calibration period."""
        self.is_calibrating = True
        self.is_calibrated = False
        self.calibration_start_time = datetime.datetime.utcnow().isoformat() + "Z"
        self.samples_collected = 0
        self.hr_buffer.clear()
        self.spo2_buffer.clear()
        self.body_temp_buffer.clear()
        self.ambient_temp_buffer.clear()
        self.humidity_buffer.clear()
        self.mq45_buffer.clear()
        self.activity_buffer.clear()

    def update_with_reading(self, reading: Dict[str, Any], nominal_only: bool = True):
        """Updates baseline buffers with a valid incoming reading."""
        hr = float(reading.get("heart_rate", 72.0))
        spo2 = float(reading.get("spo2", 98.0))
        body_temp = float(reading.get("body_temperature", 36.7))
        amb_temp = float(reading.get("ambient_temperature", 28.0))
        humidity = float(reading.get("humidity", 60.0))
        mq45 = float(reading.get("mq45", 180.0))
        act = float(reading.get("activity_state", 0))

        # Basic validity checks
        if 40 <= hr <= 200:
            self.hr_buffer.append(hr)
        if 70 <= spo2 <= 100:
            self.spo2_buffer.append(spo2)
        if 34.0 <= body_temp <= 42.0:
            self.body_temp_buffer.append(body_temp)
        if -10.0 <= amb_temp <= 60.0:
            self.ambient_temp_buffer.append(amb_temp)
        if 0.0 <= humidity <= 100.0:
            self.humidity_buffer.append(humidity)
        if 0.0 <= mq45 <= 2000.0:
            self.mq45_buffer.append(mq45)
        if 0 <= act <= 4:
            self.activity_buffer.append(act)

        self.samples_collected += 1

        if self.is_calibrating and self.samples_collected >= 30:
            self.is_calibrating = False
            self.is_calibrated = True

        self._recompute_stats()

    def _calc_stats(self, values: List[float], fallback_mean: float, fallback_std: float) -> Dict[str, float]:
        if not values or len(values) < 3:
            return {
                "mean": fallback_mean,
                "median": fallback_mean,
                "std": fallback_std,
                "variance": round(fallback_std ** 2, 4),
                "mad": round(fallback_std * 0.7979, 3),
                "min": fallback_mean - 2 * fallback_std,
                "max": fallback_mean + 2 * fallback_std,
                "rolling": fallback_mean,
                "trend": 0.0,
            }
        arr = np.array(values)
        median = float(np.median(arr))
        mad = float(np.median(np.abs(arr - median)))
        std = float(np.std(arr)) if np.std(arr) > 1e-4 else fallback_std
        variance = float(np.var(arr))
        rolling = float(np.mean(arr[-10:])) if len(arr) >= 10 else float(np.mean(arr))
        
        # Calculate recent trend slope (change over last 5-10 samples)
        if len(arr) >= 5:
            trend = float(arr[-1] - arr[-5]) / 5.0
        else:
            trend = 0.0

        return {
            "mean": round(float(np.mean(arr)), 2),
            "median": round(median, 2),
            "std": round(std, 3),
            "variance": round(variance, 4),
            "mad": round(mad, 3),
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
            "rolling": round(rolling, 2),
            "trend": round(trend, 3),
        }

    def _recompute_stats(self):
        self.stats = {
            "heart_rate": self._calc_stats(list(self.hr_buffer), 72.0, 6.0),
            "spo2": self._calc_stats(list(self.spo2_buffer), 98.0, 0.8),
            "body_temperature": self._calc_stats(list(self.body_temp_buffer), 36.7, 0.3),
            "ambient_temperature": self._calc_stats(list(self.ambient_temp_buffer), 28.0, 2.5),
            "humidity": self._calc_stats(list(self.humidity_buffer), 60.0, 5.0),
            "mq45": self._calc_stats(list(self.mq45_buffer), 180.0, 30.0),
            "activity": self._calc_stats(list(self.activity_buffer), 0.0, 0.5),
        }

    def compute_deviations(self, reading: Dict[str, Any]) -> Dict[str, Any]:
        """
        Computes current deviation from personal baseline:
        - raw difference
        - relative ratio deviation (val - mean) / mean
        - Z-score deviation (val - mean) / std
        - rolling difference
        - trend
        """
        deviations = {}
        for param in ["heart_rate", "spo2", "body_temperature", "ambient_temperature", "humidity", "mq45"]:
            val = float(reading.get(param, self.stats[param]["mean"]))
            baseline_mean = self.stats[param]["mean"]
            baseline_std = max(self.stats[param]["std"], 0.1)
            baseline_rolling = self.stats[param].get("rolling", baseline_mean)

            diff = val - baseline_mean
            rel_dev = diff / baseline_mean if baseline_mean != 0 else 0.0
            z_score = diff / baseline_std
            rolling_diff = val - baseline_rolling

            deviations[param] = {
                "current": round(val, 2),
                "baseline_mean": baseline_mean,
                "baseline_median": self.stats[param]["median"],
                "baseline_std": self.stats[param]["std"],
                "baseline_variance": self.stats[param].get("variance", round(baseline_std ** 2, 4)),
                "baseline_mad": self.stats[param]["mad"],
                "rolling_baseline": baseline_rolling,
                "difference": round(diff, 2),
                "rolling_difference": round(rolling_diff, 2),
                "relative_deviation": round(rel_dev, 4),
                "z_score": round(z_score, 2),
                "trend": self.stats[param].get("trend", 0.0),
            }

        # Activity baseline deviation
        act_val = float(reading.get("activity_state", 0))
        act_base = self.stats["activity"]["mean"]
        deviations["activity"] = {
            "current": act_val,
            "baseline_mean": act_base,
            "baseline_median": self.stats["activity"]["median"],
            "difference": round(act_val - act_base, 2),
            "z_score": round((act_val - act_base) / max(self.stats["activity"]["std"], 0.1), 2),
        }

        return deviations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "is_calibrating": self.is_calibrating,
            "is_calibrated": self.is_calibrated,
            "calibration_start_time": self.calibration_start_time,
            "samples_collected": self.samples_collected,
            "statistics": self.stats,
        }

# Global registry of active device baselines
_baseline_instances: Dict[str, PersonalBaseline] = {}

def get_device_baseline(device_id: str = "ESP32-001") -> PersonalBaseline:
    if device_id not in _baseline_instances:
        _baseline_instances[device_id] = PersonalBaseline(device_id)
    return _baseline_instances[device_id]

