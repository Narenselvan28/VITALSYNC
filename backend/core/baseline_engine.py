"""
VITALSYNC: Personal Baseline Engine
Computes and tracks personalized physiological baselines for individual users/devices.
Maintains resting vs active baselines, mean, median, standard deviation, MAD (Median Absolute Deviation),
and tracks duration outside baseline to distinguish transient spikes from sustained shifts.
Avoids reliance solely on universal fixed thresholds.
"""

import time
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

        # Buffers of historical nominal readings for baseline calculation (up to 500 samples)
        self.hr_rest_buffer = deque([72.0 + float(np.random.normal(0, 1.8)) for _ in range(50)], maxlen=500)
        self.hr_active_buffer = deque([110.0 + float(np.random.normal(0, 5.0)) for _ in range(30)], maxlen=300)
        self.spo2_buffer = deque([98.0 + float(np.random.normal(0, 0.4)) for _ in range(50)], maxlen=500)
        self.body_temp_buffer = deque([36.7 + float(np.random.normal(0, 0.15)) for _ in range(50)], maxlen=500)
        self.ambient_temp_buffer = deque([28.0 + float(np.random.normal(0, 1.0)) for _ in range(50)], maxlen=500)
        self.humidity_buffer = deque([60.0 + float(np.random.normal(0, 2.0)) for _ in range(50)], maxlen=500)
        self.mq45_buffer = deque([180.0 + float(np.random.normal(0, 15.0)) for _ in range(50)], maxlen=500)
        self.activity_buffer = deque([0.0 for _ in range(50)], maxlen=500)

        # Duration outside baseline tracking (timestamps)
        self.abnormal_start_times: Dict[str, Optional[float]] = {
            "heart_rate": None,
            "spo2": None,
            "body_temperature": None,
        }

        # Baseline statistics cache
        self.stats: Dict[str, Dict[str, float]] = {}
        self._recompute_stats()

    def start_calibration(self):
        """Starts a clean baseline calibration period."""
        self.is_calibrating = True
        self.is_calibrated = False
        self.calibration_start_time = datetime.datetime.utcnow().isoformat() + "Z"
        self.samples_collected = 0
        self.hr_rest_buffer.clear()
        self.hr_active_buffer.clear()
        self.spo2_buffer.clear()
        self.body_temp_buffer.clear()
        self.ambient_temp_buffer.clear()
        self.humidity_buffer.clear()
        self.mq45_buffer.clear()
        self.activity_buffer.clear()

    def update_with_reading(
        self,
        reading: Dict[str, Any],
        nominal_only: bool = True,
        risk_level: Optional[str] = None,
        sensor_quality: Optional[float] = None,
    ) -> bool:
        """
        Updates baseline buffers with valid incoming readings.
        Section 14: Rejects baseline learning during acute emergencies (ELEVATED / CRITICAL)
        and poor sensor quality (<0.70). Only updates from NORMAL + GOOD_SENSOR_QUALITY data.
        """
        hr = float(reading.get("heart_rate", 72.0))
        spo2 = float(reading.get("spo2", 98.0))
        body_temp = float(reading.get("body_temperature", 36.7))
        amb_temp = float(reading.get("ambient_temperature", 28.0))
        humidity = float(reading.get("humidity", 60.0))
        mq45 = float(reading.get("mq45", 180.0))
        act = float(reading.get("activity_state", 0))

        # Section 14: Safety guard - Reject abnormal events or degraded sensor quality
        if nominal_only:
            if risk_level in ("ELEVATED", "CRITICAL", "HIGH_RISK"):
                return False
            if sensor_quality is not None and sensor_quality < 0.70:
                return False
            if hr > 160 or hr < 45 or spo2 < 90 or body_temp > 38.5:
                return False

        # Segregate HR into resting vs active
        if act in (0, 1):  # Rest / Sitting
            if 45 <= hr <= 120:
                self.hr_rest_buffer.append(hr)
        else:  # Active
            if 70 <= hr <= 190:
                self.hr_active_buffer.append(hr)

        if 85 <= spo2 <= 100:
            self.spo2_buffer.append(spo2)
        if 35.0 <= body_temp <= 38.5:
            self.body_temp_buffer.append(body_temp)
        if -10.0 <= amb_temp <= 60.0:
            self.ambient_temp_buffer.append(amb_temp)
        if 0.0 <= humidity <= 100.0:
            self.humidity_buffer.append(humidity)
        if 0.0 <= mq45 <= 1500.0:
            self.mq45_buffer.append(mq45)
        if 0 <= act <= 4:
            self.activity_buffer.append(act)

        self.samples_collected += 1

        if self.is_calibrating and self.samples_collected >= 30:
            self.is_calibrating = False
            self.is_calibrated = True

        self._recompute_stats()
        return True

    def _calc_stats(self, values: List[float], fallback_mean: float, fallback_std: float) -> Dict[str, Any]:
        if not values or len(values) < 3:
            return {
                "mean": fallback_mean,
                "baseline_mean": fallback_mean,
                "median": fallback_mean,
                "baseline_median": fallback_mean,
                "std": fallback_std,
                "baseline_std": fallback_std,
                "variance": round(fallback_std ** 2, 4),
                "mad": round(fallback_std * 0.7979, 3),
                "min": fallback_mean - 2 * fallback_std,
                "max": fallback_mean + 2 * fallback_std,
                "percentiles": {
                    "p10": round(fallback_mean - 1.28 * fallback_std, 2),
                    "p25": round(fallback_mean - 0.67 * fallback_std, 2),
                    "p50": round(fallback_mean, 2),
                    "p75": round(fallback_mean + 0.67 * fallback_std, 2),
                    "p90": round(fallback_mean + 1.28 * fallback_std, 2),
                },
                "rolling": fallback_mean,
                "trend": 0.0,
            }
        arr = np.array(values)
        median = float(np.median(arr))
        mad = float(np.median(np.abs(arr - median)))
        std = float(np.std(arr)) if np.std(arr) > 1e-4 else fallback_std
        variance = float(np.var(arr))
        mean_val = float(np.mean(arr))
        rolling = float(np.mean(arr[-10:])) if len(arr) >= 10 else mean_val
        trend = float(arr[-1] - arr[-5]) / 5.0 if len(arr) >= 5 else 0.0

        p10, p25, p50, p75, p90 = np.percentile(arr, [10, 25, 50, 75, 90])

        return {
            "mean": round(mean_val, 2),
            "baseline_mean": round(mean_val, 2),
            "median": round(median, 2),
            "baseline_median": round(median, 2),
            "std": round(std, 3),
            "baseline_std": round(std, 3),
            "variance": round(variance, 4),
            "mad": round(mad, 3),
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
            "percentiles": {
                "p10": round(float(p10), 2),
                "p25": round(float(p25), 2),
                "p50": round(float(p50), 2),
                "p75": round(float(p75), 2),
                "p90": round(float(p90), 2),
            },
            "rolling": round(rolling, 2),
            "trend": round(trend, 3),
        }

    def _recompute_stats(self):
        self.stats = {
            "heart_rate": self._calc_stats(list(self.hr_rest_buffer), 72.0, 5.0),
            "heart_rate_rest": self._calc_stats(list(self.hr_rest_buffer), 72.0, 5.0),
            "heart_rate_active": self._calc_stats(list(self.hr_active_buffer), 110.0, 10.0),
            "spo2": self._calc_stats(list(self.spo2_buffer), 98.0, 0.7),
            "body_temperature": self._calc_stats(list(self.body_temp_buffer), 36.7, 0.25),
            "ambient_temperature": self._calc_stats(list(self.ambient_temp_buffer), 28.0, 2.5),
            "humidity": self._calc_stats(list(self.humidity_buffer), 60.0, 5.0),
            "mq45": self._calc_stats(list(self.mq45_buffer), 180.0, 25.0),
            "activity": self._calc_stats(list(self.activity_buffer), 0.0, 0.5),
        }

    def compute_deviations(self, reading: Dict[str, Any]) -> Dict[str, Any]:
        """
        Computes current deviation from personal baseline including duration outside baseline.
        """
        now = time.time()
        deviations = {}
        act_state = int(reading.get("activity_state", 0))
        is_active = act_state in (3, 4)

        for param in ["heart_rate", "spo2", "body_temperature", "ambient_temperature", "humidity", "mq45"]:
            val = float(reading.get(param, self.stats[param]["mean"]))
            
            # Select appropriate baseline based on activity state for HR
            if param == "heart_rate" and is_active:
                baseline_mean = self.stats["heart_rate_active"]["mean"]
                baseline_std = max(self.stats["heart_rate_active"]["std"], 1.0)
            else:
                baseline_mean = self.stats[param]["mean"]
                baseline_std = max(self.stats[param]["std"], 0.1)

            baseline_rolling = self.stats[param].get("rolling", baseline_mean)

            diff = val - baseline_mean
            rel_dev = diff / baseline_mean if baseline_mean != 0 else 0.0
            z_score = diff / baseline_std
            rolling_diff = val - baseline_rolling

            # Track duration outside baseline (significant deviation)
            is_outside = abs(z_score) > 2.0 or (param == "heart_rate" and abs(diff) > 25) or (param == "spo2" and diff < -3)
            duration_outside = 0.0

            if param in self.abnormal_start_times:
                if is_outside:
                    if self.abnormal_start_times[param] is None:
                        self.abnormal_start_times[param] = now
                    duration_outside = now - self.abnormal_start_times[param]
                else:
                    self.abnormal_start_times[param] = None

            deviations[param] = {
                "current": round(val, 2),
                "baseline_mean": baseline_mean,
                "baseline_median": self.stats[param]["median"],
                "baseline_std": baseline_std,
                "baseline_variance": self.stats[param].get("variance", round(baseline_std ** 2, 4)),
                "baseline_mad": self.stats[param]["mad"],
                "rolling_baseline": baseline_rolling,
                "difference": round(diff, 2),
                "rolling_difference": round(rolling_diff, 2),
                "relative_deviation": round(rel_dev, 4),
                "z_score": round(z_score, 2),
                "trend": self.stats[param].get("trend", 0.0),
                "duration_outside_sec": round(duration_outside, 1),
            }

        # Activity baseline
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

_baseline_instances: Dict[str, PersonalBaseline] = {}

def get_device_baseline(device_id: str = "ESP32-001") -> PersonalBaseline:
    if device_id not in _baseline_instances:
        _baseline_instances[device_id] = PersonalBaseline(device_id)
    return _baseline_instances[device_id]
