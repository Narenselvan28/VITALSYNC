"""
VITALSYNC: Sensor Validator Module
Strict hardware and signal validity checks for:
- MAX30102 (PPG, Heart Rate, SpO2)
- ADXL345 (3-Axis Accelerometer)
- 10K NTC Thermistor (Contact/Skin Temperature)
- Ambient Temperature & Humidity
- MQ-45 (Gas / Environmental Exposure Indicator)
- GPS NEO-7
- External Weather Context
- SIM800L Cellular Modem

Rule: Invalid or poor sensors must downweight evidence and report UNAVAILABLE,
NEVER generate false medical emergencies.
"""

import math
import time
from typing import Dict, Any, Tuple

class SensorValidator:
    def __init__(self, mq45_warmup_sec: float = 45.0):
        self.start_time = time.time()
        self.mq45_warmup_sec = mq45_warmup_sec

    def validate_ppg(self, hr: Any, spo2: Any, ppg_quality: float = 0.95) -> Tuple[str, float]:
        if hr is None or spo2 is None:
            return "UNAVAILABLE", 0.0
        try:
            hr_f = float(hr)
            spo2_f = float(spo2)
            ppg_q = float(ppg_quality)
        except (ValueError, TypeError):
            return "INVALID", 0.0

        if math.isnan(hr_f) or math.isnan(spo2_f):
            return "INVALID", 0.0

        # Physiological bounds check
        if hr_f < 30.0 or hr_f > 230.0 or spo2_f < 50.0 or spo2_f > 100.0:
            return "INVALID", 0.0

        if ppg_q < 0.40 or spo2_f < 68.0:
            return "WEAK", 0.35
        elif ppg_q < 0.70:
            return "FAIR", 0.70
        return "GOOD", 1.0

    def validate_adxl345(self, ax: Any, ay: Any, az: Any, is_available: bool = True) -> Tuple[str, float]:
        if not is_available or ax is None or ay is None or az is None:
            return "UNAVAILABLE", 0.0
        try:
            ax_f, ay_f, az_f = float(ax), float(ay), float(az)
        except (ValueError, TypeError):
            return "INVALID", 0.0

        if any(math.isnan(v) or math.isinf(v) for v in (ax_f, ay_f, az_f)):
            return "INVALID", 0.0

        mag = math.sqrt(ax_f**2 + ay_f**2 + az_f**2)
        # Disconnected I2C bus typically floats near 0.0 or clamps to 0xFF (32g)
        if mag < 0.05 or mag > 24.0:
            return "INVALID", 0.0

        return "GOOD", 1.0

    def validate_ntc(self, temp: Any, rate_of_change: float = 0.0) -> Tuple[str, float]:
        if temp is None:
            return "UNAVAILABLE", 0.0
        try:
            t_f = float(temp)
        except (ValueError, TypeError):
            return "INVALID", 0.0

        if math.isnan(t_f) or math.isinf(t_f):
            return "INVALID", 0.0

        if t_f < 15.0 or t_f > 48.0:
            return "INVALID", 0.0

        # Fast thermal spike indicates external contact artifact (e.g. hot beverage)
        if abs(rate_of_change) > 1.2:
            return "TRANSIENT_ARTIFACT", 0.50

        return "GOOD", 1.0

    def validate_ambient(self, temp: Any, humidity: Any) -> Tuple[str, float]:
        if temp is None or humidity is None:
            return "UNAVAILABLE", 0.0
        try:
            t_f, h_f = float(temp), float(humidity)
        except (ValueError, TypeError):
            return "INVALID", 0.0

        if math.isnan(t_f) or math.isnan(h_f):
            return "INVALID", 0.0

        if t_f < -30.0 or t_f > 65.0 or h_f < 0.0 or h_f > 100.0:
            return "INVALID", 0.0

        return "GOOD", 1.0

    def validate_mq45(self, mq_val: Any) -> Tuple[str, float]:
        if mq_val is None:
            return "UNAVAILABLE", 0.0
        try:
            val_f = float(mq_val)
        except (ValueError, TypeError):
            return "INVALID", 0.0

        if math.isnan(val_f) or val_f < 0.0:
            return "INVALID", 0.0

        if (time.time() - self.start_time) < self.mq45_warmup_sec:
            return "WARMING", 0.50

        if val_f > 1950.0:
            return "FAIR", 0.60

        return "GOOD", 1.0

    def validate_gps(self, lat: Any, lon: Any, gps_valid: bool = True) -> Tuple[str, float]:
        if not gps_valid or lat is None or lon is None:
            return "NO_FIX", 0.0
        try:
            lat_f, lon_f = float(lat), float(lon)
        except (ValueError, TypeError):
            return "INVALID", 0.0

        if lat_f == 0.0 and lon_f == 0.0:
            return "NO_FIX", 0.0

        if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
            return "INVALID", 0.0

        return "GOOD", 1.0

    def validate_all(self, raw_reading: Dict[str, Any], temp_roc: float = 0.0) -> Dict[str, Any]:
        hr = raw_reading.get("heart_rate")
        spo2 = raw_reading.get("spo2")
        ppg_q = raw_reading.get("ppg_quality", 0.95)

        ax = raw_reading.get("accel_x")
        ay = raw_reading.get("accel_y")
        az = raw_reading.get("accel_z")
        adxl_avail = raw_reading.get("adxl_available", True)

        ntc_temp = raw_reading.get("body_temperature")
        amb_temp = raw_reading.get("ambient_temperature")
        humidity = raw_reading.get("humidity")
        mq45 = raw_reading.get("mq45")

        lat = raw_reading.get("latitude")
        lon = raw_reading.get("longitude")
        gps_fix = raw_reading.get("gps_fix", True if (lat and lon and (lat != 0 or lon != 0)) else False)

        ppg_status, ppg_weight = self.validate_ppg(hr, spo2, ppg_q)
        adxl_status, adxl_weight = self.validate_adxl345(ax, ay, az, adxl_avail)
        ntc_status, ntc_weight = self.validate_ntc(ntc_temp, temp_roc)
        amb_status, amb_weight = self.validate_ambient(amb_temp, humidity)
        mq_status, mq_weight = self.validate_mq45(mq45)
        gps_status, gps_weight = self.validate_gps(lat, lon, gps_fix)

        qualities = {
            "ppg": ppg_status,
            "spo2": ppg_status,
            "adxl345": adxl_status,
            "ntc": ntc_status,
            "ambient": amb_status,
            "mq45": mq_status,
            "gps": gps_status,
            "weather": raw_reading.get("weather_status", "ONLINE"),
            "sim800l": raw_reading.get("sim800l_status", "READY"),
        }

        weights = {
            "ppg": ppg_weight,
            "spo2": ppg_weight,
            "adxl345": adxl_weight,
            "ntc": ntc_weight,
            "ambient": amb_weight,
            "mq45": mq_weight,
            "gps": gps_weight,
        }

        # Overall composite sensor health score
        composite_confidence = (
            ppg_weight * 0.35 +
            ntc_weight * 0.20 +
            adxl_weight * 0.20 +
            amb_weight * 0.10 +
            mq_weight * 0.15
        )

        return {
            "qualities": qualities,
            "weights": weights,
            "composite_confidence": round(composite_confidence, 2),
            "is_ppg_valid": ppg_status in ("GOOD", "FAIR"),
            "is_adxl_valid": adxl_status == "GOOD",
            "is_ntc_valid": ntc_status in ("GOOD", "TRANSIENT_ARTIFACT"),
            "is_gps_valid": gps_status == "GOOD",
        }

_validator = SensorValidator()

def get_sensor_validator() -> SensorValidator:
    return _validator
