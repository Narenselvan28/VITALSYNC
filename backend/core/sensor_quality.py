"""
VITALSYNC: Sensor Quality Layer
Evaluates the physical signal validity, noise levels, and operational states
of all connected hardware sensors (MAX30102, ADXL345, 10K NTC, MQ-45, GPS NEO-7, SIM800L).
Ensures bad sensor data reduces model weight rather than generating false emergencies.
"""

import math
import time
from typing import Dict, Any, Tuple

class SensorQualityEngine:
    def __init__(self):
        self.mq45_start_time = time.time()
        self.warmup_seconds = 45.0  # Warmup period for MQ-45 heater

    def evaluate_max30102(self, hr: float, spo2: float, ppg_q: float) -> Tuple[str, float]:
        """
        Evaluates MAX30102 pulse oximeter quality.
        Returns: (status: GOOD | FAIR | WEAK | INVALID, confidence_weight: 0.0 - 1.0)
        """
        if hr is None or spo2 is None:
            return "INVALID", 0.0
        
        # Physiological limits
        if hr < 30 or hr > 230 or spo2 < 55 or spo2 > 100:
            return "INVALID", 0.0
            
        if ppg_q < 0.40 or spo2 < 70:
            return "WEAK", 0.35
        elif ppg_q < 0.70:
            return "FAIR", 0.70
        else:
            return "GOOD", 1.0

    def evaluate_adxl345(self, ax: float, ay: float, az: float) -> Tuple[str, float]:
        """
        Evaluates ADXL345 3-axis accelerometer health.
        Detects disconnects, NaNs, zero-clamping, and physical faults.
        """
        if ax is None or ay is None or az is None:
            return "OFFLINE", 0.0
        
        if any(math.isnan(v) or math.isinf(v) for v in (ax, ay, az)):
            return "INVALID", 0.0
            
        mag = math.sqrt(ax**2 + ay**2 + az**2)
        
        # Disconnected I2C bus usually reads 0, 0, 0 or saturated 0xFF (32.7g)
        if mag < 0.05 or mag > 24.0:
            return "INVALID", 0.0
            
        return "GOOD", 1.0

    def evaluate_ntc(self, temp: float, rate_of_change: float = 0.0) -> Tuple[str, float]:
        """
        Evaluates 10K NTC contact thermistor health.
        Detects open/short circuits and sudden sensor detachment or disturbance.
        """
        if temp is None or math.isnan(temp):
            return "INVALID", 0.0
            
        # Clinical skin contact limits: 20°C (detached) to 45°C
        if temp < 15.0 or temp > 46.0:
            return "INVALID", 0.0
            
        # Very high rate of change (>1.5°C/s) indicates thermal contact disturbance (e.g. hot mug)
        if abs(rate_of_change) > 1.2:
            return "TRANSIENT", 0.50
            
        return "GOOD", 1.0

    def evaluate_mq45(self, mq_val: float) -> Tuple[str, float]:
        """
        Evaluates MQ-45 environmental exposure indicator.
        Handles heater warm-up phase.
        """
        if mq_val is None or math.isnan(mq_val) or mq_val < 0:
            return "INVALID", 0.0
            
        elapsed = time.time() - self.mq45_start_time
        if elapsed < self.warmup_seconds:
            return "WARMING", 0.50
            
        if mq_val > 1950:  # ADC saturation
            return "FAIR", 0.60
            
        return "GOOD", 1.0

    def evaluate_ambient(self, amb_temp: float, humidity: float) -> Tuple[str, float]:
        """Evaluates ambient temperature and humidity sensor."""
        if amb_temp is None or humidity is None or math.isnan(amb_temp) or math.isnan(humidity):
            return "INVALID", 0.0
        if amb_temp < -25 or amb_temp > 65 or humidity < 0 or humidity > 100:
            return "INVALID", 0.0
        return "GOOD", 1.0

    def evaluate_gps(self, lat: float, lon: float, fix_status: bool = True) -> Tuple[str, float]:
        """Evaluates GPS NEO-7 fix status."""
        if not fix_status or lat is None or lon is None or (lat == 0.0 and lon == 0.0):
            return "NO_FIX", 0.0
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return "INVALID", 0.0
        return "GOOD", 1.0

    def evaluate_all(self, raw_reading: Dict[str, Any], temp_roc: float = 0.0) -> Dict[str, Any]:
        """Runs quality checks across all sensors and outputs structured quality map."""
        hr = raw_reading.get("heart_rate")
        spo2 = raw_reading.get("spo2")
        ppg_q = raw_reading.get("ppg_quality", 0.95)
        
        ax = raw_reading.get("accel_x")
        ay = raw_reading.get("accel_y")
        az = raw_reading.get("accel_z")
        
        ntc_temp = raw_reading.get("body_temperature")
        amb_temp = raw_reading.get("ambient_temperature")
        humidity = raw_reading.get("humidity")
        mq45 = raw_reading.get("mq45")
        
        lat = raw_reading.get("latitude")
        lon = raw_reading.get("longitude")
        gps_fix = raw_reading.get("gps_fix", True if (lat and lon and (lat != 0 or lon != 0)) else False)

        ppg_status, ppg_weight = self.evaluate_max30102(hr, spo2, ppg_q)
        adxl_status, adxl_weight = self.evaluate_adxl345(ax, ay, az)
        ntc_status, ntc_weight = self.evaluate_ntc(ntc_temp, temp_roc)
        mq_status, mq_weight = self.evaluate_mq45(mq45)
        amb_status, amb_weight = self.evaluate_ambient(amb_temp, humidity)
        gps_status, gps_weight = self.evaluate_gps(lat, lon, gps_fix)
        weather_status = raw_reading.get("weather_status", "ONLINE")

        quality_map = {
            "ppg": ppg_status,
            "spo2": ppg_status,
            "adxl345": adxl_status,
            "ntc": ntc_status,
            "mq45": mq_status,
            "ambient": amb_status,
            "gps": gps_status,
            "weather": weather_status,
            "sim800l": raw_reading.get("sim800l_status", "READY"),
        }

        # Overall sensor health confidence (0.0 to 1.0)
        overall_confidence = (
            ppg_weight * 0.35 +
            ntc_weight * 0.20 +
            adxl_weight * 0.20 +
            amb_weight * 0.10 +
            mq_weight * 0.15
        )

        return {
            "qualities": quality_map,
            "weights": {
                "ppg": ppg_weight,
                "adxl345": adxl_weight,
                "ntc": ntc_weight,
                "mq45": mq_weight,
                "ambient": amb_weight,
                "gps": gps_weight,
            },
            "overall_sensor_confidence": round(overall_confidence, 2),
            "adxl_available": adxl_status == "GOOD",
            "ppg_available": ppg_status in ("GOOD", "FAIR"),
            "ntc_available": ntc_status in ("GOOD", "TRANSIENT"),
        }

_sensor_quality_engine = SensorQualityEngine()

def get_sensor_quality_engine() -> SensorQualityEngine:
    return _sensor_quality_engine
